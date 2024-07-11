use bevy::{
    ecs::{entity::EntityHashMap, reflect::ReflectMapEntities, world::Command},
    gltf::Gltf,
    prelude::*,
};
#[allow(unused_imports)]
use smallvec::smallvec;
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
        commands.add(SpawnLevel {
            handle: gltf.0.clone(),
            root: Some(e),
            bundle_fn: |e| {
                e.insert(LevelMarker);
            },
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

//type SpawnFn = FnOnce(&mut EntityWorldMut) + Send + Sync;

#[derive(Debug, Default)]
pub struct SpawnLevel<F>
where
    F: Fn(&mut EntityWorldMut) + Send + Sync + 'static,
{
    pub handle: Handle<Gltf>,
    pub root: Option<Entity>,
    pub bundle_fn: F,
}

impl<B: Fn(&mut EntityWorldMut) + Send + Sync> Command for SpawnLevel<B> {
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
            let mut entities = Vec::<Entity>::new();

            if let Some(e) = self.root {
                entity_map.insert(SCENE_ROOT, e);                
            }

            let mut new_roots: Vec<Entity> = Vec::new();

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

                            // flatten
                            if type_id == TypeId::of::<Children>() {
                                let children = scene.world.get::<Children>(scene_entity).unwrap();
                                for child in children.iter() {
                                    new_roots.push(*child);
                                }
                            }

                            // dont copy root entity if we are not given't one to map it too
                            continue;
                        }

                        // get or create app world entity
                        let entity = entity_map
                            .entry(scene_entity)
                            .or_insert_with(|| world.spawn_empty().id());

                        // If this component references entities in the scene, track it
                        // so we can update it to the entity in the world.

                        // if a new root node, just add it
                        if new_roots.contains(&scene_entity) {
                            // dont copy parent component of root entity
                            if type_id == TypeId::of::<Parent>() {
                                // set if we have a root entity
                                if let Some(parent) = self.root {
                                    //dbg!(scene_entity, parent);
                                    world.entity_mut(*entity).insert(Parent(parent));
                                }
                                continue;
                            }

                            if type_id == TypeId::of::<Children>() {                                
                                continue;
                            }

                        } else {
                            if registration.data::<ReflectMapEntities>().is_some() {
                                if !entities.contains(&entity) {
                                    entities.push(*entity);
                                }
                            }

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
                map_entities_reflect.map_entities(world, &mut entity_map, &entities);
            }

            let world_new_roots = new_roots
                .iter()
                .map(|e| entity_map.get(e).unwrap().clone())
                .collect::<Vec<_>>();
                //info!("level new roots: {}", world_new_roots.iter().map(|e| format!("{}", e)).collect::<Vec<_>>().join(", "))    ;
            

            for e in world_new_roots.iter() {
                let name = world
                .get::<Name>(*e)
                .map(|n| format!("{:?}", n.to_string()))
                .unwrap_or("N/A".to_owned());
            let parent = world
                .get::<Parent>(*e)
                .map(|n| format!("{}", n.0))
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
                info!("level roots: {e} - {name}, parent: {parent}, pos: {translate},  children: {children}");                
            }

            // call bundle fn
            for e in world_new_roots.iter() {
                (self.bundle_fn)(&mut world.entity_mut(*e));
                // add marker with bundle fn
            }

            // fix children of root entity
            if let Some(parent_e) = self.root {
                let mut parent_cmd = world.entity_mut(parent_e);
                let name = {
                    let x = parent_cmd.get_mut::<Name>().unwrap();
                    &x.to_string()
                };
                match parent_cmd.get_mut::<Children>() {
                    Some(mut c) => {
                        warn!("level parent name: {:?} - {:?}", name, c);
                        for re in world_new_roots.iter() {
                            c.0.push(*re);
                        }
                    }
                    None => {
                        warn!(
                            "level parent none - name: {:?} - {:?}",
                            name,
                            world_new_roots.len()
                        );
                        // root entity has no children, so we need to add one
                        parent_cmd
                            .insert(Children(smallvec::SmallVec::from_slice(&world_new_roots)));
                    }
                }
            }
        })
    }
}
