use bevy::{
    ecs::{entity::EntityHashMap, reflect::ReflectMapEntities, world::Command},
    gltf::Gltf,
    prelude::*,
    utils::HashSet,
};
use std::any::TypeId;

use crate::{print_debug_list, BlenderPluginConfig, GltfFormat, SCENE_ROOT};

/// Helper to spawn from name blueprints
#[derive(Component, Reflect, Default, Debug)]
#[reflect(Component)]
pub struct LevelName(pub String);

// what we really use, full path to loaded gltf or glb file
#[derive(Component, Reflect, Default, Debug, Deref, DerefMut)]
#[reflect(Component)]
pub struct LevelGltf(pub Handle<Gltf>);

pub(crate) fn spawn_from_level_name(
    mut commands: Commands,
    query: Query<(Entity, &LevelName), Added<LevelName>>,
    config: Res<BlenderPluginConfig>,
    asset_server: Res<AssetServer>,
) {
    for (e, name) in query.iter() {
        let path = format!(
            "{}/{}.{}",
            config.level_folder.to_string_lossy(),
            name.0,
            match config.format {
                GltfFormat::GLB => "glb",
                GltfFormat::GLTF => "gltf",
            }
        );
        // warn!("requesting to spawn {:?} for {:?}", path, e);
        let path: Handle<Gltf> = asset_server.load(path);
        commands.entity(e).insert(LevelGltf(path));
    }
}

#[derive(Component, Reflect, Default, Debug)]
pub struct LevelMarker;

pub(crate) fn spawn_level_from_gltf(
    mut commands: Commands,
    spawn_placeholders: Query<(Entity, &LevelGltf), Added<LevelGltf>>,
    assets_gltf: Res<Assets<Gltf>>,
) {
    for (e, gltf) in spawn_placeholders.iter() {
        let gltf = assets_gltf
        .get(&gltf.0)
        .unwrap_or_else(|| panic!("gltf file {:?} should have been loaded", &gltf.0));

    // WARNING we work under the assumtion that there is ONLY ONE named scene, and that the first one is the right one
    let main_scene_name = gltf
        .named_scenes
        .keys()
        .next()
        .expect("there should be at least one named scene in the gltf file to spawn");

    let scene = &gltf.named_scenes[main_scene_name];

        #[cfg(not(feature = "nested"))]
        commands.add(SpawnLevel {
            handle: gltf.0.clone(),
            root: e,
        });
        
        #[cfg(feature = "nested")]
        commands.entity(e).insert(SceneBundle {
            scene: scene.clone(),
            ..Default::default()
        });
        
    }
}
#[cfg(not(feature = "nested"))]

/// Command a level to be spawned
#[derive(Debug)]
pub struct SpawnLevel {
    pub handle: Handle<Gltf>,
    pub root: Entity,
}

#[cfg(not(feature = "nested"))]
impl Command for SpawnLevel {
    fn apply(self, world: &mut World) {
        let assets_gltf = world.resource::<Assets<Gltf>>();

        let gltf = assets_gltf
            .get(&self.handle)
            .unwrap_or_else(|| panic!("gltf file {:?} should have been loaded", &self.handle));

        // WARNING we work under the assumtion that there is ONLY ONE named scene, and that the first one is the right one
        let main_scene_name = gltf
            .named_scenes
            .keys()
            .next()
            .expect("there should be at least one named scene in the gltf file to spawn");
        let scene = &gltf.named_scenes[main_scene_name];
        let scene_id = scene.id();

        world.resource_scope(|world, mut scenes: Mut<Assets<Scene>>| {
            let Some(scene) = scenes.get_mut(scene_id) else {
                error!("Failed to get scene with id {:?}", scene_id);
                return;
            };

            let type_registry = world.resource::<AppTypeRegistry>().clone();
            let type_registry = type_registry.read();

            // Copy Resources
            for (component_id, resource_data) in scene.world.storages().resources.iter() {
                if !resource_data.is_present() {
                    continue;
                }

                let component_info = scene
                    .world
                    .components()
                    .get_info(component_id)
                    .expect("component_ids in archetypes should have ComponentInfo");

                let type_id = component_info
                    .type_id()
                    .expect("reflected resources must have a type_id");

                let Some(registration) = type_registry.get(type_id) else {
                    error!(
                        "Failed to get type registry: {}",
                        component_info.name().to_string()
                    );
                    continue;
                };
                let Some(reflect_resource) = registration.data::<ReflectResource>() else {
                    error!(
                        "Failed to get reflect resource: {}",
                        registration.type_info().type_path().to_string()
                    );
                    continue;
                };
                reflect_resource.copy(&scene.world, world, &type_registry);
            }

            // map of scene to app world entities
            let mut entity_map = EntityHashMap::default();
            entity_map.insert(SCENE_ROOT, self.root);

            // list of world entities that are not children
            let mut entities: HashSet<Entity> = HashSet::default();

            let scene_roots = scene
                .world
                .get::<Children>(SCENE_ROOT)                
                .unwrap();

            // create entities and copy components
            for archetype in scene.world.archetypes().iter() {
                for scene_entity_arch in archetype.entities() {
                    let scene_entity = scene_entity_arch.id();

                    for component_id in archetype.components() {
                        let component_info = scene
                            .world
                            .components()
                            .get_info(component_id)
                            .expect("component_ids in archetypes should have ComponentInfo");
                        let type_id = component_info.type_id().unwrap();
                        let registration = type_registry
                            .get(type_id)
                            .expect("Failed to get type registration");

                        let reflect_component = registration
                            .data::<ReflectComponent>()
                            .expect("Failed to get reflect component");

                        // skip if root entity, nothing useful on it
                        if scene_entity == SCENE_ROOT {
                            // sanity checks
                            if type_id == TypeId::of::<Transform>() {
                                let scene_trans =
                                    scene.world.get::<Transform>(scene_entity).unwrap();
                                assert!(scene_trans.translation == Vec3::ZERO);
                                assert!(scene_trans.scale == Vec3::ONE);
                                assert!(scene_trans.rotation == Quat::IDENTITY);
                            }
                            continue;
                        }

                        // get or create app world entity
                        let entity = entity_map
                            .entry(scene_entity)
                            .or_insert_with(|| world.spawn_empty().id());

                        // if a new root node, just add it
                        if scene_roots.contains(&scene_entity) {
                            // dont copy parent component of root entity
                            if type_id == TypeId::of::<Parent>()
                                || type_id == TypeId::of::<Children>()
                            {
                                continue;
                            }
                        } else {
                            entities.insert(*entity); // add to map list
                        }

                        // copy the component from scene to world
                        reflect_component.copy(
                            &scene.world,
                            world,
                            scene_entity,
                            *entity,
                            &type_registry,
                        );
                    }
                }
            }

            // Reflect Map Entities, this fixes any references to entities in the copy
            for registration in type_registry.iter() {
                let Some(map_entities_reflect) = registration.data::<ReflectMapEntities>() else {
                    continue;
                };
                let x = entities.iter().map(|x| x.clone()).collect::<Vec<_>>();
                map_entities_reflect.map_entities(world, &mut entity_map, &x);
            }

            // let new_children = scene_roots
            //     .iter()
            //     .map(|e| entity_map.get(e).unwrap().clone())
            //     .collect::<Vec<_>>();

            // match world.get_mut::<Children>(self.root) {
            //     Some(mut c) => {
            //         c.extend(new_children.clone());
            //     }
            //     None => {
            //         // create new children
            //         world
            //             .entity_mut(self.root)
            //             .insert(Children(smallvec::SmallVec::from_slice(&new_children)));
            //     }
            // }

            // call bundle fn
            // for e in new_children.iter() {
            //     (self.bundle_fn)(&mut world.entity_mut(*e));
            // }

            //print_debug_list(&[self.root], world, "level root");
            //print_debug_list(&new_children, world, "level child");
        })
    }
}
