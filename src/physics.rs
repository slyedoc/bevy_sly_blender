use bevy::{
    math::vec3,
    prelude::*,
    render::mesh::{MeshVertexAttributeId, PrimitiveTopology, VertexAttributeValues},
    transform::TransformSystem,
};
use bevy_xpbd_3d::{
    parry::{
        na::{Const, OPoint},
        shape::SharedShape,
    },
    prelude::*,
};

use crate::GltfBlueprintsSet;

// use crate::prelude::*;
// use crate::utils::traits::*;

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

pub(super) fn plugin(app: &mut App) {
    app.register_type::<ProxyCollider>().add_systems(
        Update,
        (physics_replace_proxies)
            .after(TransformSystem::TransformPropagate)
            .after(GltfBlueprintsSet::Spawn),
    );
}

// replaces all physics stand-ins with the actual xpbd types
fn physics_replace_proxies(
    meshes: Res<Assets<Mesh>>,
    mesh_handles: Query<&Handle<Mesh>>,
    mut proxy_colliders: Query<
        (Entity, &ProxyCollider, Option<&Name>,),
        (Without<Collider>, Added<ProxyCollider>),
    >,
    // needed for tri meshes
    children: Query<&Children>,
    global_transforms: Query<&GlobalTransform>,
    mut commands: Commands,
) {
    
    for (entity, collider_proxy, name_maybe) in proxy_colliders.iter_mut() {
        let msg = format!("generating collider from proxy on {:?}: {:?}", name_maybe, collider_proxy);
        dbg!(msg);
        match collider_proxy {
            ProxyCollider::Ball(radius) => {
                commands.entity(entity)
                    .insert(Collider::sphere(*radius))
                    //.insert(ActiveEvents::COLLISION_EVENTS)  // FIXME: this is just for demo purposes (also is there something like that in xpbd ?) !!!
                    ;
            }
            ProxyCollider::Cuboid(size) => {
                commands
                    .entity(entity)
                    .insert(Collider::cuboid(size.x, size.y, size.z));
                //.insert(ActiveEvents::COLLISION_EVENTS)  // FIXME: this is just for demo purposes (also is there something like that in xpbd ?) !!!
            }
            ProxyCollider::Capsule(height, radius) => {
                commands.entity(entity)
                    .insert(Collider::capsule( *height, *radius))
                    //.insert(ActiveEvents::COLLISION_EVENTS)  // FIXME: this is just for demo purposes (also is there something like that in xpbd ?) !!!
                    ;
            }
            ProxyCollider::Mesh => {
                let mut vertices: Vec<OPoint<f32, Const<3>>> = Vec::new();

                // Compute the inverse translation and rotation
                let p_global = global_transforms.get(entity).unwrap();
                let root = p_global.compute_transform();
                let inverse_rotation = root.rotation.conjugate(); // In Bevy, rotation.conjugate() should give you the inverse for unit quaternions.

                let mut sub_meshes =
                    Mesh::search_in_children(entity, &children, &meshes, &mesh_handles);
                // check self for mesh
                if let Ok(handle) = mesh_handles.get(entity) {
                    if let Some(mesh) = meshes.get(handle) {
                        error!("mesh found in entity: {:?}", entity);
                        sub_meshes.push((entity, mesh));
                    }
                }

                for (e, mesh) in sub_meshes {
                    let c_global = global_transforms.get(e).unwrap();

                    // Apply inverse rotation and then inverse translation
                    //dbg!(p_trans.translation);
                    for v in mesh.read_coords(Mesh::ATTRIBUTE_POSITION) {
                        let p = vec3(v[0], v[1], v[2]);

                        // in vert in world space
                        let world_pos = c_global.transform_point(p);

                        // apply inverse rotation then inverse translation, to get the vert in local space
                        let rotated_pos = inverse_rotation * (world_pos - root.translation);

                        vertices.push(rotated_pos.into());
                    }
                }
                let convex: Collider = SharedShape::convex_hull(&vertices).unwrap().into();
                commands.entity(entity).insert(convex);
            }
            ProxyCollider::Halfspace(v) => {
                info!("generating collider from proxy: halfspace");
                commands.entity(entity)
                    .insert(Collider::halfspace(*v))
                    //.insert(ActiveEvents::COLLISION_EVENTS)  // FIXME: this is just for demo purposes (also is there something like that in xpbd ?) !!!
                    ;
            }
        }
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
