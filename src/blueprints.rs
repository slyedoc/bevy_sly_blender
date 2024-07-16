//#[cfg(feature = "physics")]
//use avian3d::collision::ColliderParent;
use crate::{BlenderPluginConfig, BlueprintSpawned, GltfFormat, SCENE_NEW_ROOT, SCENE_ROOT};
use bevy::{
    ecs::{entity::EntityHashMap, reflect::ReflectMapEntities, world::Command},
    gltf::Gltf,
    prelude::*,
    utils::HashSet,
};
use core::panic;
use std::any::TypeId;

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
            }

            info!(
                "Spawning blueprint from {:?}",
                world
                    .get::<Name>(self.root)
                    .map(|n| n.to_string())
                    .unwrap_or("N/A".to_owned())
            );

            // map of scene to app world entities
            let mut entity_map = EntityHashMap::default();
            entity_map.insert(SCENE_NEW_ROOT, self.root);

            // list of world entities that are not children
            let mut update_list: HashSet<Entity> = HashSet::default();

            // get the children, for now there should just be 1
            // for now we force a single root entity, that can have many children, this is due to
            // component_meta needing to be on object instead of collection
            // if that chagnes remove this assert

            // skip SCENE_ROOT, its just a placeholder
            let scene_roots = scene
                .world
                .get::<Children>(SCENE_ROOT)
                .map(|c| c.0.to_vec())
                .unwrap();
            assert!(scene_roots.iter().len() == 1);

            // get the children of that scene_child, those will be the new children of self.root
            let scene_children: Vec<Entity> = scene_roots
                .iter()
                .map(|c| {
                    scene
                        .world
                        .get::<Children>(*c)
                        .map(|c| c.0.to_vec())
                        .unwrap_or_else(|| vec![])
                })
                .flatten()
                .collect();

            // dbg!(&scene_roots);
            // dbg!(&scene_children);

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
                            //dbg!(&component_info.name());
                            continue;
                        }

                        // get or create world entity
                        let entity = entity_map
                            .entry(scene_entity)
                            .or_insert_with(|| world.spawn_empty().id());

                        // if at new root level, dont overwrite a few things
                        if scene_roots.contains(&scene_entity) {
                            // dont overwrite a few things
                            if (type_id == TypeId::of::<Name>()
                                && world.get_mut::<Name>(*entity).is_some())
                                || type_id == TypeId::of::<Parent>()
                                || type_id == TypeId::of::<Children>()
                                || type_id == TypeId::of::<Transform>()
                            {
                                continue;
                            }
                            // could apply the root entity's transform to existing entity
                            // if type_id == TypeId::of::<Transform>() {
                            //  let scene_trans =scene.world.get::<Transform>(scene_entity).unwrap();
                            //  let mut trans = world.get_mut::<Transform>(*entity).unwrap();
                            //  let new_trans = trans.mul_transform(*scene_trans);
                            //  *trans = new_trans;
                            //}
                            // copy the rest
                        } else {
                            update_list.insert(*entity); // add to map list
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
                let x = update_list.iter().map(|x| *x).collect::<Vec<_>>();
                map_entities_reflect.map_entities(world, &mut entity_map, &x);
            }

            let new_children = scene_children
                .iter()
                .map(|e| entity_map.get(e).unwrap().clone())
                .collect::<Vec<_>>();

            match world.get_mut::<Children>(self.root) {
                Some(mut c) => {
                    c.0.extend(new_children.clone());
                }
                None => {
                    // create new children
                    world
                        .entity_mut(self.root)
                        .insert(Children(smallvec::SmallVec::from_slice(&new_children)));
                }
            }

            print_debug_list(&[self.root], world, "blueprint root ");
            print_debug_list(&new_children, world, "blueprint child");

            // notify anyone that cares that the blueprint has been spawned
            world.send_event(BlueprintSpawned(self.root)); // used by aabb generation
        })
    }
}

pub fn print_debug_list(debug_list: &[Entity], world: &mut World, title: &str) {
    // let debug_list_str =  debug_list.iter().map(|e| format!("{}", e)).collect::<Vec<_>>().join(", ");
    // info!("{title}: {debug_list_str}");

    for e in debug_list.iter() {
        let name = world
            .get::<Name>(*e)
            .map(|n| format!("{:?}", n.to_string()))
            .unwrap_or("N/A".to_owned());
        let parent = world
            .get::<Parent>(*e)
            .map(|n| format!("{}", n.0))
            .unwrap_or("N/A".to_owned());

        let translation = world
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

        info!("{title}: {e} - {name}, parent: {parent}, pos: {translation},  children: {children}");
    }
}
