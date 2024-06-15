use bevy::{
    ecs::{entity::EntityHashMap, reflect::ReflectMapEntities, system::Command},
    gltf::Gltf,
    prelude::*,
};
use std::any::TypeId;

use crate::{BlenderPluginConfig, GltfFormat};

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
) {
    for (e, gltf) in spawn_placeholders.iter() {
        commands.add(SpawnLevel::<LevelMarker> {
            handle: gltf.0.clone(),
            root: Some(e),
            ..default()
        });
    }
}

// This is an attemp to flatten entities
// tons of the orginal code was trying to clean up after bevy_scene and gltf parser created heirarchies
// this instead bypasses scene bundle and copies the entities directly to the app world, directly from loaded gltf
// coping logic is based on bevy_scene::scene::write_to_world_with
// we make some assumptions about gltf parser inserts entities in order
// by heirarchy and assume root entity is always 0v1 and never has anything useful on it, so we skip it
// we also assume 0v1 only hase one child, making 1v1 the entity we want as new root entity
const SCENE_ROOT: Entity = Entity::from_raw(0); // the root entity in the scene

#[derive(Debug, Default)]
pub struct SpawnLevel<T: Component + Default> {
    pub handle: Handle<Gltf>,
    pub root: Option<Entity>,
    pub _marker: std::marker::PhantomData<T>,    
}

impl<T: Component + Default> Command for SpawnLevel<T> {
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
            // cache the parent
            // let parent = match self.root {
            //     Some(e) => match world.entity(e).get::<Parent>() {
            //         Some(p) => Some((p.get(), e)),
            //         None => None,
            //     },
            //     None => None,
            // };

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
                reflect_resource.copy(&scene.world, world);
            }

            // map of scene to app world entities
            let mut entity_map = EntityHashMap::default();
            if let Some(e) = self.root {
                entity_map.insert(SCENE_ROOT, e);
            }

            let mut new_roots: Vec<Entity> = Vec::new();

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

                            // flatten
                            if self.root.is_none() {
                                // children of the scene root will be new roots, save them
                                if type_id == TypeId::of::<Children>() {
                                    let children = scene.world.get::<Children>(e).unwrap();
                                    for child in children.iter() {
                                        new_roots.push(*child);
                                    }
                                    //dbg!(&new_roots);
                                }
                                // dont copy root entity if we are not given't one to map it too
                                continue;
                            }
                        }

                        if new_roots.contains(&e) {
                            // dont copy parent for new root entities
                            if type_id == TypeId::of::<Parent>() {
                                continue;
                            }
                            // if type_id == TypeId::of::<GlobalTransform>() {
                            //     continue;
                            // }
                            if type_id == TypeId::of::<InheritedVisibility>() {
                                // TODO: do i need to add visibility to new roots?
                                continue;
                            }
                        }

                        // get or create app world entity
                        // entry already exsits for SCENE_NEW_ROOT
                        let entity = entity_map
                            .entry(scene_entity.id())
                            .or_insert_with(|| world.spawn_empty().id());

                        // copy the component from scene to world
                        reflect_component.copy(
                            &scene.world,
                            world,
                            scene_entity.id(),
                            *entity,
                            &type_registry,
                        );

                        // dont copy parent for new root entities
                        // let unnamed = Name::new("unnamed");
                        // if type_id == TypeId::of::<Parent>() || type_id == TypeId::of::<Children>() {
                        //     let name = scene.world.get::<Name>(e).unwrap_or_else(|| &unnamed);
 
                        // }

                        // if e == SCENE_NEW_ROOT {
                        //     // copy components from root entity except the following

                        //     // dont overwrite name with blueprint's name
                        //     if type_id == TypeId::of::<Name>() {
                        //         let name = scene.world.get::<Name>(e).unwrap().clone();
                        //         //dbg!(name);
                        //         continue;
                        //     }
                        //     // dont overwrite the parent
                        //     if type_id == TypeId::of::<Parent>() {
                        //         continue;
                        //     }
                        //     // apply the root entity's transform to existing entity
                        //     // but dont copy it
                        //     if type_id == TypeId::of::<Transform>() {
                        //         let scene_trans = scene.world.get::<Transform>(e).unwrap().clone();
                        //         let mut trans = world.get_mut::<Transform>(*entity).unwrap();

                        //         trans.translation += scene_trans.translation;
                        //         trans.rotation *= scene_trans.rotation;
                        //         trans.scale *= scene_trans.scale;
                        //         continue;
                        //     }
                        // }
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

            // remove parent from new root entities
            for r in new_roots.iter().map(|e| entity_map.get(e).unwrap()) {
                // add marker
                world.entity_mut(*r).insert(T::default());
            }
        })
    }
}
