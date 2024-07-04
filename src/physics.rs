use bevy::{
    math::vec3,
    prelude::*,
    render::mesh::{MeshVertexAttributeId, PrimitiveTopology, VertexAttributeValues},
    transform::TransformSystem::TransformPropagate,
};
use bevy_xpbd_3d::{
    parry::{
        na::{Const, OPoint},
        shape::SharedShape,
    },
    prelude::*,
};

pub(super) fn plugin(app: &mut App) {
    app.register_type::<ProxyCollider>().add_systems(
        PostUpdate,
        (physics_replace_proxies).after(TransformPropagate),
    );
}

#[derive(Component, Reflect, Default, Debug)]
#[reflect(Component)]
pub enum ProxyCollider {
    Halfspace(Vec3),
    Ball(f32),
    Cuboid(Vec3),
    Capsule(f32, f32),
    #[default]
    Mesh,
}

// replaces all physics stand-ins with the actual xpbd types
pub(super) fn physics_replace_proxies(
    meshes: Res<Assets<Mesh>>,
    mesh_handles: Query<&Handle<Mesh>>,
    mut proxy_colliders: Query<
        (Entity, &ProxyCollider, Option<&Name>),
        (Without<Collider>, Added<ProxyCollider>),
    >,
    children: Query<&Children>,
    global_transforms: Query<&GlobalTransform>,    
    mut commands: Commands,
) {
    let tmp = Name::new("none");
    for (entity, collider_proxy, name_maybe) in proxy_colliders.iter_mut() {
        let name = name_maybe.unwrap_or_else(|| &tmp).to_string();

        // Compute the inverse translation and rotation
        let p_global = global_transforms.get(entity).unwrap();
        let root = p_global.compute_transform();
        let inverse_rotation = root.rotation.conjugate(); 
        let inverse_scale = 1.0 / root.scale;
        

        debug!(
            "generating collider for {:?}: {:?}",
            name,
            collider_proxy
        );
        let collider = match collider_proxy {
            ProxyCollider::Ball(radius) => {
                let size = radius.max(0.1);
                let msg= format!("Ball collider with radius: {}", size);
                dbg!(msg);
                Collider::sphere(size)
            },
            ProxyCollider::Cuboid(size) => Collider::cuboid(size.x, size.y, size.z),
            ProxyCollider::Capsule(height, radius) => Collider::capsule(*height, *radius),
            ProxyCollider::Mesh => {
                // collect all vertices from children and calculate the convex hull from them
                // in order to handle nesting we use there global transforms project to world space 
                // then back to local space relative entity with ProxyCollider::Mesh
                let mut vertices: Vec<OPoint<f32, Const<3>>> = Vec::new();

                let mut sub_meshes = Mesh::search_in_children(entity, &children, &meshes, &mesh_handles);
                // check self for mesh, not used currently
                if let Ok(handle) = mesh_handles.get(entity) {
                    if let Some(mesh) = meshes.get(handle) {                        
                        sub_meshes.push((entity, mesh));
                    }
                }
                
                for (e, mesh) in sub_meshes {
                    let child_global_transform = global_transforms.get(e).unwrap();
                    
                    for v in mesh.read_coords(Mesh::ATTRIBUTE_POSITION) {
                        let mut pos = vec3(v[0], v[1], v[2]);

                        // convert to world space
                        pos = child_global_transform.transform_point(pos);

                        // convert to local space realive to entity
                        pos = inverse_rotation * (pos - root.translation);                        
                        pos *= inverse_scale;
                                            
                        vertices.push(pos.into());
                    }
                }

                let convex: Collider = if let Some(shape) = SharedShape::convex_hull(&vertices) {
                    shape.into()
                } else {
                    error!("failed to create convex hull from vertices: {}", name);                    
                    Collider::sphere(1.0)
                };
                //let convex: Collider = SharedShape::convex_hull(&vertices).unwrap().into();
                convex
            }
            ProxyCollider::Halfspace(v) => {                
                Collider::halfspace(*v)
            }
        };
        commands.entity(entity).insert(collider);
    }
}

pub trait MeshExt {
    fn transform(&mut self, transform: Transform);
    fn transformed(&self, transform: Transform) -> Mesh;
    fn read_coords(&self, id: impl Into<MeshVertexAttributeId>) -> &Vec<[f32; 3]>;
    fn read_coords_mut(&mut self, id: impl Into<MeshVertexAttributeId>) -> &mut Vec<[f32; 3]>;
    fn search_in_children<'a>(
        parent: Entity,
        children: &'a Query<&Children>,
        meshes: &'a Assets<Mesh>,
        mesh_handles: &'a Query<&Handle<Mesh>>,
    ) -> Vec<(Entity, &'a Mesh)>;
}

impl MeshExt for Mesh {
    fn transform(&mut self, transform: Transform) {
        for coords in self.read_coords_mut(Mesh::ATTRIBUTE_POSITION.clone()) {
            let vec3 = (*coords).into();
            let transformed = transform.transform_point(vec3);
            *coords = transformed.into();
        }
        for normal in self.read_coords_mut(Mesh::ATTRIBUTE_NORMAL.clone()) {
            let vec3 = (*normal).into();
            let transformed = transform.rotation.mul_vec3(vec3);
            *normal = transformed.into();
        }
    }

    fn transformed(&self, transform: Transform) -> Mesh {
        let mut mesh = self.clone();
        mesh.transform(transform);
        mesh
    }

    fn read_coords_mut(&mut self, id: impl Into<MeshVertexAttributeId>) -> &mut Vec<[f32; 3]> {
        // Guaranteed by Bevy for the current usage
        match self
            .attribute_mut(id)
            .expect("Failed to read unknown mesh attribute")
        {
            VertexAttributeValues::Float32x3(values) => values,
            // Guaranteed by Bevy for the current usage
            _ => unreachable!(),
        }
    }

    fn read_coords(&self, id: impl Into<MeshVertexAttributeId>) -> &Vec<[f32; 3]> {
        // Guaranteed by Bevy for the current usage
        match self
            .attribute(id)
            .expect("Failed to read unknown mesh attribute")
        {
            VertexAttributeValues::Float32x3(values) => values,
            // Guaranteed by Bevy for the current usage
            _ => unreachable!(),
        }
    }

    fn search_in_children<'a>(
        parent: Entity,
        children_query: &'a Query<&Children>,
        meshes: &'a Assets<Mesh>,
        mesh_handles: &'a Query<&Handle<Mesh>>,
    ) -> Vec<(Entity, &'a Mesh)> {
        if let Ok(children) = children_query.get(parent) {
            let mut result: Vec<_> = children
                .iter()
                .filter_map(|entity| mesh_handles.get(*entity).ok().map(|mesh| (*entity, mesh)))
                .map(|(entity, mesh_handle)| {
                    (
                        entity,
                        meshes
                            .get(mesh_handle)
                            .expect("Failed to get mesh from handle"),
                    )
                })
                .map(|(entity, mesh)| {
                    assert_eq!(mesh.primitive_topology(), PrimitiveTopology::TriangleList);
                    (entity, mesh)
                })
                .collect();
            let mut inner_result = children
                .iter()
                .flat_map(|entity| {
                    Self::search_in_children(*entity, children_query, meshes, mesh_handles)
                })
                .collect();
            result.append(&mut inner_result);
            result
        } else {
            Vec::new()
        }
    }
}

// pub(super) fn plugin(app: &mut App) {
//     app.register_type::<Collider>().add_systems(
//         Update,
//         spawn
//             .after(TransformPropagate)
//             .run_if(in_state(AppState::Playing)),
//     );
//}

// #[sysfail(Log<anyhow::Error, Error>)]
// fn spawn(
//     collider_marker: Query<Entity, With<Collider>>,
//     mut commands: Commands,
//     children: Query<&Children>,
//     meshes: Res<Assets<Mesh>>,
//     mesh_handles: Query<&Handle<Mesh>, Without<RigidBody>>,
//     global_transforms: Query<&GlobalTransform>,
// ) {
//     #[cfg(feature = "tracing")]
//     let _span = info_span!("read_colliders").entered();
//     for entity in collider_marker.iter() {
//         let mut all_children_loaded = true;
//         for child in children.iter_descendants(entity) {
//             if let Ok(mesh_handle) = mesh_handles.get(child) {
//                 if let Some(mesh) = meshes.get(mesh_handle) {
//                     let global_transform = global_transforms
//                         .get(child)
//                         .context("Failed to get global transform while reading collider")?
//                         .compute_transform();
//                     let scaled_mesh = mesh.clone().scaled_by(global_transform.scale);
//                     let collider = XpbdCollider::trimesh_from_mesh(&scaled_mesh)
//                         .context("Failed to create collider from mesh")?;
//                     commands.entity(child).insert((
//                         collider,
//                         RigidBody::Static,
//                         CollisionLayers::new(
//                             [CollisionLayer::Terrain, CollisionLayer::CameraObstacle],
//                             [CollisionLayer::Character],
//                         ),
//                         NavMeshAffector,
//                     ));
//                 } else {
//                     all_children_loaded = false;
//                 }
//             }
//         }
//         if all_children_loaded {
//             commands.entity(entity).remove::<Collider>();
//         }
//     }
// }
