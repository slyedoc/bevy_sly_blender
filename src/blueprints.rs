use bevy::{
    ecs::{entity::EntityHashMap, reflect::ReflectMapEntities, world::Command},
    gltf::{Gltf, GltfExtras},
    prelude::*,
};
#[cfg(feature = "physics")]
use bevy_xpbd_3d::plugins::collision::ColliderParent;
use core::panic;
use std::any::TypeId;

use crate::{BlenderPluginConfig, BlueprintSpawned, GltfFormat};

/// Helper to spawn from name blueprints
#[derive(Component, Reflect, Default, Debug)]
#[reflect(Component)]
pub struct BlueprintName(pub String);

// what we really use, full path to loaded gltf or glb file
#[derive(Component, Reflect, Default, Debug, Deref, DerefMut)]
#[reflect(Component)]
pub struct BlueprintGltf(pub Handle<Gltf>);

pub(crate) fn spawn_from_blueprint_name(
    mut commands: Commands,
    query: Query<(Entity, &BlueprintName), Added<BlueprintName>>,
    config: Res<BlenderPluginConfig>,
    asset_server: Res<AssetServer>,
) {
    for (e, name) in query.iter() {
        let path = format!(
            "{}/{}.{}",
            config.blueprint_folder.to_string_lossy(),
            name.0,
            match config.format {
                GltfFormat::GLB => "glb",
                GltfFormat::GLTF => "gltf",
            }
        );
        // warn!("requesting to spawn {:?} for {:?}", path, e);
        let path: Handle<Gltf> = asset_server.load(path);
        commands.entity(e).insert(BlueprintGltf(path));
    }
}

pub(crate) fn spawn_blueprint_from_gltf(
    mut commands: Commands,
    spawn_placeholders: Query<(Entity, &BlueprintGltf), Added<BlueprintGltf>>,
    assets_gltf: Res<Assets<Gltf>>,
) {
    for (entity, gltf) in spawn_placeholders.iter() {
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

        // new way
        #[cfg(not(feature = "nested"))]
        commands.add(SpawnBlueprint {
            handle: scene.clone(),
            root: entity,
        });

        // simplefied old way, leaving for comparisons
        #[cfg(feature = "nested")]
        commands
            .entity(entity)
            // need extra child to avoid loosing this entities transform
            .with_children(|parent| {
                parent.spawn(SceneBundle {
                    scene: scene.clone(),
                    ..Default::default()
                });
            });
    }
}

// This is an attemp to flatten entities
// tons of the orginal code was trying to clean up after bevy_scene and io_scene_gltf2 and gltf parser created heirarchies
// this instead bypasses scene bundle and copies the entities directly to the app world, directly from loaded gltf
// coping logic is based on bevy_scene::scene::write_to_world_with
// we make some assumptions about gltf parser inserts entities in order
// by heirarchy and assume root entity is always 0v1 and never has anything useful on it, so we skip it
// we also assume 0v1 only has one child, making 1v1 the entity we want as new root entity
// we make this last assumption because component_meta has to be on object instead of collection, so if we want
// to be able to set component on the blueprint entity there cant be many children
const SCENE_ROOT: Entity = Entity::from_raw(0); // the root entity in the scene
const SCENE_NEW_ROOT: Entity = Entity::from_raw(1); // the only child of that root entity

pub struct SpawnBlueprint {
    pub root: Entity,
    pub handle: Handle<Scene>,
}

impl Command for SpawnBlueprint {
    fn apply(self, world: &mut World) {
        let id = self.handle.id();

        world.resource_scope(|world, mut scenes: Mut<Assets<Scene>>| {
            // cache the parent
            let parent = {
                let p = world.entity(self.root).get::<Parent>();
                if let Some(p) = p {
                    Some(p.get().clone())
                } else {
                    None
                }
            };

            let Some(scene) = scenes.get_mut(id) else {
                error!("Failed to get scene with id {:?}", id);
                return;
            };

            let type_registry = world.resource::<AppTypeRegistry>().clone();
            let type_registry = type_registry.read();

            // TODO: Haven't seen any use of resources in blueprints yet
            for (_component_id, _resource_data) in scene.world.storages().resources.iter() {
                panic!("What used this?");
                //     dbg!(&component_id);
                //     if !resource_data.is_present() {
                //         continue;
                //     }

                //     let component_info = scene
                //         .world
                //         .components()
                //         .get_info(component_id)
                //         .expect("component_ids in archetypes should have ComponentInfo");

                //     let type_id = component_info
                //         .type_id()
                //         .expect("reflected resources must have a type_id");

                //     let Some(registration) = type_registry.get(type_id) else {
                //         error!(
                //             "Failed to get type registry: {}",
                //             component_info.name().to_string()
                //         );
                //         continue;
                //     };
                //     let Some(reflect_resource) = registration.data::<ReflectResource>() else {
                //         error!(
                //             "Failed to get reflect resource: {}",
                //             registration.type_info().type_path().to_string()
                //         );
                //         continue;
                //     };
                //     reflect_resource.copy(&scene.world, world);
            }

            // map of scene to app world entities
            let mut entity_map = EntityHashMap::default();
            entity_map.insert(SCENE_NEW_ROOT, self.root);

            // create entities and copy components
            for archetype in scene.world.archetypes().iter() {
                for scene_entity in archetype.entities() {
                    let e = scene_entity.id();
                    for component_id in archetype.components() {
                        let component_info = scene
                            .world
                            .components()
                            .get_info(component_id)
                            .expect("component_ids in archetypes should have ComponentInfo");
                        let type_id = component_info.type_id().unwrap();
                        let reflect_component = type_registry
                            .get(type_id)
                            .expect("Failed to get reflect component type id:")
                            .data::<ReflectComponent>()
                            .expect("Failed to get reflect component");

                        // skip if root entity, nothing useful on it
                        if e == SCENE_ROOT {
                            // sanity checks
                            if type_id == TypeId::of::<Transform>() {
                                let scene_trans = scene.world.get::<Transform>(e).unwrap();
                                assert!(scene_trans.translation == Vec3::ZERO);
                                assert!(scene_trans.scale == Vec3::ONE);
                                assert!(scene_trans.rotation == Quat::IDENTITY);
                            }
                            if type_id == TypeId::of::<Children>() {
                                let children = scene.world.get::<Children>(e).unwrap();
                                // all my blueprints have only one child, this may change
                                let name = world.entity(self.root).get::<Name>()
                                    .unwrap_or(&Name::default())
                                    .to_string();
                                
                                if children.iter().len() != 1 {
                                    error!("name: {:?}, children: {:?}", name, children);
                                }
                                assert!(children.iter().len() == 1);
                            }
                            if type_id == TypeId::of::<GltfExtras>() {
                                panic!("GltfExtras should have been copied to the app world");
                            }
                            continue;
                        }

                        // get or create app world entity
                        // entry already exsits for SCENE_NEW_ROOT
                        let entity = entity_map
                            .entry(scene_entity.id())
                            .or_insert_with(|| world.spawn_empty().id());

                        // dont overwrite the parent
                        #[cfg(feature = "physics")]
                        if type_id == TypeId::of::<ColliderParent>() {
                            error!("Parent should have been fixed");
                        }

                        

                        if e == SCENE_NEW_ROOT {
                            // copy components from root entity except the following

                            // dont overwrite name with blueprint's name
                            if type_id == TypeId::of::<Name>() {
                                continue;
                            }
                            // dont overwrite the parent
                            if type_id == TypeId::of::<Parent>() {
                                continue;
                            }
                            // if type_id == TypeId::of::<GlobalTransform>() {
                            //     continue;
                            // }

                            // apply the root entity's transform to existing entity
                            // but dont copy it

                            if type_id == TypeId::of::<Transform>() {
                                let name = scene
                                    .world
                                    .get::<Name>(e)
                                    .unwrap_or(&Name::default())
                                    .to_string();

                                let scene_trans = scene.world.get::<Transform>(e).unwrap().clone();
                                let mut trans =
                                    world.get_mut::<Transform>(*entity).unwrap_or_else(|| {
                                        panic!("Failed to get transform for entity {:?}", name)
                                    });

                                let new_trans =  trans.mul_transform(scene_trans);
                                //if name.contains("Tia") {
                                //    error!("name: {:?}: existing: {:?}, scene: {:?}, new: {:?}", name, trans, scene_trans, new_trans);
                                //}
                                
                                *trans = new_trans;

                                continue;
                            }
                        }

                        // copy the component from scene to world
                        reflect_component.copy(
                            &scene.world,
                            world,
                            scene_entity.id(),
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
                map_entities_reflect.map_all_entities(world, &mut entity_map);
            }

            // TODO: still not happy with this
            // info!(
            //     "parent: {:?}, current_parent: {:?}, fixing",
            //     parent,
            //     world.entity(self.root).get::<Parent>().unwrap().get()
            // );
            // Fix Parenting, we cached the correct parent entity at the start
            if let Some(p) = parent {
                world.entity_mut(self.root).set_parent(p);
            }

            // notify anyone that cares that the blueprint has been spawned
            world.send_event(BlueprintSpawned(self.root)); // used by aabb generation
        })
    }
}
