//#[cfg(feature = "physics")]
//use avian3d::collision::ColliderParent;
use bevy::{
    ecs::{entity::EntityHashMap, reflect::ReflectMapEntities, world::Command},
    gltf::Gltf,
    prelude::*,
};
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
            let mut entities: Vec<Entity> = vec![];
            let mut new_roots: Vec<Entity> = Vec::new();

            entity_map.insert(SCENE_NEW_ROOT, self.root);

            // create entities and copy components
            for archetype in scene.world.archetypes().iter() {
                for scene_entity_arch in archetype.entities() {
                    let scene_entity = scene_entity_arch.id();

                    // TODO: remove this, dbg only
                    let name = world
                        .get::<Name>(self.root)
                        .map(|n| format!("{:?}", n.to_string()))
                        .unwrap_or("N/A".to_owned());

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

                            // flatten the scene
                            if type_id == TypeId::of::<Children>() {
                                let children = scene.world.get::<Children>(scene_entity).unwrap();
                                for child in children.iter() {
                                    new_roots.push(*child);
                                }
                                assert!(children.iter().len() == 1);
                            }
                            continue;
                        }

                        // get or create app world entity
                        let entity = entity_map
                            .entry(scene_entity)
                            .or_insert_with(|| world.spawn_empty().id());

                        if new_roots.contains(&scene_entity) {
                            // copy components from root entity except the following

                            // dont overwrite name with blueprint's name
                            if type_id == TypeId::of::<Name>() {
                                continue;
                            }

                            // dont overwrite name with blueprint's parent
                            if type_id == TypeId::of::<Parent>() {
                                continue;
                            }

                            if type_id == TypeId::of::<Children>() {                                
                                continue;
                            }

                            // apply the root entity's transform to existing entity
                            // but dont copy it
                            if type_id == TypeId::of::<Transform>() {
                                let scene_trans =
                                    scene.world.get::<Transform>(scene_entity).unwrap();
                                let mut trans =
                                    world.get_mut::<Transform>(*entity).unwrap_or_else(|| {
                                        panic!("Failed to get transform for entity {:?}", name)
                                    });
                                let new_trans = trans.mul_transform(*scene_trans);
                                *trans = new_trans;

                                continue;
                            }
                        } else {
                            if type_id == TypeId::of::<Parent>() {
                                let parent = scene.world.get::<Parent>(scene_entity).unwrap().0;
                                if new_roots.contains(&parent) {
                                    dbg!("fix blueprint parent");
                                    //world.entity_mut(*entity).insert(Parent(self.root));
                                    //continue;
                                }
                            }

                            if registration.data::<ReflectMapEntities>().is_some() {
                                if !entities.contains(&entity) {
                                    entities.push(*entity);
                                }
                            }
                        }

                        // dont overwrite the parent
                        // #[cfg(feature = "physics")]
                        // if type_id == TypeId::of::<ColliderParent>() {
                        //     error!("Parent should have been fixed");
                        // }

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
                map_entities_reflect.map_entities(world, &mut entity_map, &entities);
            }

            let world_new_roots = new_roots
                .iter()
                .map(|e| entity_map.get(e))
                .filter(|e| e.is_some())
                .map(|e| *e.unwrap())
                .collect::<Vec<_>>();

            //dbg!(&world_new_roots, new_roots);
                //info!("blueprints new roots: {}", world_new_roots.iter().map(|e| format!("{}", e)).collect::<Vec<_>>().join(", "))    ;
            

            for e in world_new_roots.iter() {
                let name = world
                    .get::<Name>(*e)
                    .map(|n| format!("{:?}", n.to_string()))
                    .unwrap_or("N/A".to_owned());
                let parent = world
                    .get::<Parent>(*e)
                    .map(|n| format!("{}", n.0))
                    .unwrap_or("N/A".to_owned());

                // let p_e = world
                //     .get::<Parent>(*e)
                //     .unwrap().0;

                 let parent_name = world
                     .get::<Name>(self.root)
                     .map(|n| format!("{}", n))
                     .unwrap_or("N/A".to_owned());

                let translate = world
                    .get::<Transform>(*e)
                    .map(|n| format!("{:?}", n.translation))
                    .unwrap_or("N/A".to_owned());
                let children = world
                    .get::<Children>(*e)
                    .map(|c| {
                        let x =
                            c.0.iter()
                                .map(|e| format!("{}", e))
                                .collect::<Vec<_>>()
                                .join(", ");
                        x
                    })
                    .unwrap_or_else(|| "N/A".to_owned());

                info!("blueprint roots: {e} - {name}, parent: {parent} - {parent_name}, pos: {translate},  children: {children}");
            }

            
            let name = world
                .get::<Name>(self.root)
                .map(|n| format!("{:?}", n.to_string()))
                .unwrap_or("N/A".to_owned());

            match world.get_mut::<Children>(self.root) {
                Some(mut c) => {
                    let new_children = world_new_roots.iter().map(|e| format!("{}", e)).collect::<Vec<_>>().join(", ");
                    
                    let children = c.0.iter()
                        .map(|e| format!("{}", e))
                        .collect::<Vec<_>>()
                        .join(", ");
                    warn!("blueprint: {}, name:  {name}, new_children: {new_children}, children: {children}", self.root);
                }
                None => {
                    error!(
                        "blueprint parent none - name: {name}",
                    );
                    // root entity has no children, so we need to add one
                     world
                         .entity_mut(self.root)
                         .insert(Children(smallvec::SmallVec::from_slice(&world_new_roots)));
                }
            }

            // notify anyone that cares that the blueprint has been spawned
            world.send_event(BlueprintSpawned(self.root)); // used by aabb generation
        })
    }
}
