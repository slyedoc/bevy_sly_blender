use std::{any::TypeId, path::Path};

use bevy::{
    ecs::{entity::EntityHashMap, reflect::ReflectMapEntities, system::Command},
    gltf::Gltf,
    prelude::*,
    utils::HashMap,
};

use crate::{BlenderPluginConfig, BlueprintSpawned};

/// this is a flag component for our levels/game world
#[derive(Component)]
pub struct GameWorldTag;

/// Main component for the blueprints
#[derive(Component, Reflect, Default, Debug)]
#[reflect(Component)]
pub struct BlueprintName(pub String);

/// flag component needed to signify the intent to spawn a Blueprint
#[derive(Component, Reflect, Default, Debug)]
#[reflect(Component)]
pub struct SpawnHere;

// #[derive(Component, Reflect, Default, Debug)]
// #[reflect(Component)]
// // this allows overriding the default library path for a given entity/blueprint
// pub struct Library(pub PathBuf);

/// helper component, is used to store the list of sub blueprints to enable automatic loading of dependend blueprints
#[derive(Component, Reflect, Default, Debug)]
#[reflect(Component)]
pub struct BlueprintsList(pub HashMap<String, Vec<String>>);

/// helper component, for tracking loaded assets's loading state, id , handle etc
#[derive(Default, Debug)]
pub(crate) struct AssetLoadTracker<T: bevy::prelude::Asset> {
    #[allow(dead_code)]
    pub name: String,
    pub id: AssetId<T>,
    pub loaded: bool,
    #[allow(dead_code)]
    pub handle: Handle<T>,
}

/// helper component, for tracking loaded assets
#[derive(Component, Debug)]
pub(crate) struct AssetsToLoad<T: bevy::prelude::Asset> {
    pub all_loaded: bool,
    pub asset_infos: Vec<AssetLoadTracker<T>>,
    pub progress: f32,
}
impl<T: bevy::prelude::Asset> Default for AssetsToLoad<T> {
    fn default() -> Self {
        Self {
            all_loaded: Default::default(),
            asset_infos: Default::default(),
            progress: Default::default(),
        }
    }
}

/// flag component, usually added when a blueprint is loaded
#[derive(Component)]
pub(crate) struct BlueprintAssetsLoaded;
/// flag component
#[derive(Component)]
pub(crate) struct BlueprintAssetsNotLoaded;

/// spawning prepare function,
/// * also takes into account the already exisiting "override" components, ie "override components" > components from blueprint
pub(crate) fn prepare_blueprints(
    spawn_placeholders: Query<
        (
            Entity,
            &BlueprintName,
            Option<&Parent>,
            //Option<&Library>,
            Option<&Name>,
            Option<&BlueprintsList>,
        ),
        (Added<BlueprintName>, Added<SpawnHere>),
    >,

    mut commands: Commands,
    asset_server: Res<AssetServer>,
    blueprints_config: Res<BlenderPluginConfig>,
) {
    for (entity, blupeprint_name, original_parent, name, blueprints_list) in
        spawn_placeholders.iter()
    {
        info!(
            "requesting to spawn {:?} for entity {:?}, id: {:?}, parent:{:?}",
            blupeprint_name.0, name, entity, original_parent
        );

        // println!("main model path {:?}", model_path);
        if blueprints_list.is_some() {
            let blueprints_list = blueprints_list.unwrap();
            // println!("blueprints list {:?}", blueprints_list.0.keys());
            let mut asset_infos: Vec<AssetLoadTracker<Gltf>> = vec![];
            for (blueprint_name, _) in blueprints_list.0.iter() {
                let model_file_name = format!("{}.{}", &blueprint_name, &blueprints_config.format);
                let model_path = Path::new(&blueprints_config.library_folder)
                    .join(Path::new(model_file_name.as_str()));

                let model_handle: Handle<Gltf> = asset_server.load(model_path.clone());
                let model_id = model_handle.id();
                let loaded = asset_server.is_loaded_with_dependencies(model_id);
                if !loaded {
                    asset_infos.push(AssetLoadTracker {
                        name: model_path.to_string_lossy().into(),
                        id: model_id,
                        loaded: false,
                        handle: model_handle.clone(),
                    });
                }
            }
            // if not all assets are already loaded, inject a component to signal that we need them to be loaded
            if !asset_infos.is_empty() {
                commands
                    .entity(entity)
                    .insert(AssetsToLoad {
                        all_loaded: false,
                        asset_infos,
                        ..Default::default()
                    })
                    .insert(BlueprintAssetsNotLoaded);
            } else {
                commands.entity(entity).insert(BlueprintAssetsLoaded);
            }
        } else {
            // in case there are no blueprintsList, we revert back to the old behaviour
            commands.entity(entity).insert(BlueprintAssetsLoaded);
        }
    }
}

pub(crate) fn check_for_loaded(
    mut blueprint_assets_to_load: Query<
        (Entity, &mut AssetsToLoad<Gltf>),
        With<BlueprintAssetsNotLoaded>,
    >,
    asset_server: Res<AssetServer>,
    mut commands: Commands,
) {
    for (entity, mut assets_to_load) in blueprint_assets_to_load.iter_mut() {
        let mut all_loaded = true;
        let mut loaded_amount = 0;
        let total = assets_to_load.asset_infos.len();
        for tracker in assets_to_load.asset_infos.iter_mut() {
            let asset_id = tracker.id;
            let loaded = asset_server.is_loaded_with_dependencies(asset_id);
            tracker.loaded = loaded;
            if loaded {
                loaded_amount += 1;
            } else {
                all_loaded = false;
            }
        }
        let progress: f32 = loaded_amount as f32 / total as f32;
        // println!("progress: {}",progress);
        assets_to_load.progress = progress;

        if all_loaded {
            assets_to_load.all_loaded = true;
            commands
                .entity(entity)
                .insert(BlueprintAssetsLoaded)
                .remove::<BlueprintAssetsNotLoaded>();
        }
    }
}

pub(crate) fn spawn_from_blueprints(
    mut commands: Commands,
    spawn_placeholders: Query<
        (Entity, &BlueprintName, Option<&Name>),
        (
            Added<BlueprintAssetsLoaded>,
            With<BlueprintAssetsLoaded>,
            Without<BlueprintAssetsNotLoaded>,
        ),
    >,
    assets_gltf: Res<Assets<Gltf>>,
    asset_server: Res<AssetServer>,
    blueprints_config: Res<BlenderPluginConfig>,
) {
    for (entity, blupeprint_name, name) in spawn_placeholders.iter() {
        info!(
            "attempting to spawn {:?} for entity {:?}, id: {:?}",
            blupeprint_name.0, name, entity,
        );

        let model_path = Path::new(&blueprints_config.library_folder).join(format!(
            "{}.{}",
            blupeprint_name.0, &blueprints_config.format
        ));
        let model_handle: Handle<Gltf> = asset_server.load(model_path.clone()); // FIXME: kinda weird now
        let gltf = assets_gltf.get(&model_handle).unwrap_or_else(|| {
            panic!(
                "gltf file {:?} should have been loaded",
                model_path.to_str()
            )
        });

        // WARNING we work under the assumtion that there is ONLY ONE named scene, and that the first one is the right one
        let main_scene_name = gltf
            .named_scenes
            .keys()
            .next()
            .expect("there should be at least one named scene in the gltf file to spawn");

        let scene = &gltf.named_scenes[main_scene_name];

        // simplefied old way
        // commands.entity(entity).insert(SceneBundle {
        //     scene: scene.clone(),
        //     ..Default::default()
        // });

        // new way
        commands.add(SpawnBlueprint {
            handle: scene.clone(),
            root: entity,
        });
    }
}

// This is an attemp to flatten entities, it is based on the scene bundle
// coping logic is from bevy_scene::scene::write_to_world_with
// basiclly we copy from scene world to app world, flatten it by assuming gltf parser inserts entities in order
// in heirarchy order so root entity is always 0v1, it never has anything useful on it, so we skip it
// we also assume 0v1 only hase one child, making 1v1 the entity we want as new root node
const SCENE_ROOT: Entity = Entity::from_raw(0); // the root entity in the scene
const SCENE_NEW_ROOT: Entity = Entity::from_raw(1); // the only child of that root entity
                                                    //const COMPONENT_EXCLUDE: [TypeId; 1] = [TypeId::of::<Name>()];

pub struct SpawnBlueprint {
    handle: Handle<Scene>,
    root: Entity,
}

impl Command for SpawnBlueprint {
    fn apply(self, world: &mut World) {
        let id = self.handle.id();

        world.resource_scope(|world, mut scenes: Mut<Assets<Scene>>| {
            // cache the parent
            let parent = world.entity(self.root).get::<Parent>().unwrap().get();

            let Some(scene) = scenes.get_mut(id) else {
                error!("Failed to get scene with id {:?}", id);
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
            entity_map.insert(SCENE_NEW_ROOT, self.root);

            // copy entities
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
                            continue;
                        }

                        if e == SCENE_NEW_ROOT {
                            // dont overwrite name with blueprint's name
                            if type_id == TypeId::of::<Name>() {
                                continue;
                            }
                            // apply the root entity's transform to existing entity
                            if type_id == TypeId::of::<Transform>() {
                                let scene_trans = scene.world.get::<Transform>(e).unwrap().clone();
                                let mut trans = world.get_mut::<Transform>(e).unwrap();
                                trans.translation += scene_trans.translation;
                                trans.rotation *= scene_trans.rotation;
                                trans.scale *= scene_trans.scale;
                                dbg!(&trans);
                                //assert!(trans.translation == Vec3::ZERO, "root entity should have no translation");
                                continue;
                            }
                            // overwrite the parent
                            if type_id == TypeId::of::<Parent>() {
                               
                            }
                        }

                        // get or create app world entity
                        let entity = entity_map
                            .entry(scene_entity.id())
                            .or_insert_with(|| world.spawn_empty().id());

                        // copy the component to the app world entity
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

            // Map Entities, this fixes any references to entities in the copy
            for registration in type_registry.iter() {
                let Some(map_entities_reflect) = registration.data::<ReflectMapEntities>() else {
                    continue;
                };
                map_entities_reflect.map_all_entities(world, &mut entity_map);
            }

            // The post proccessing
            // Fix Parenting, we cached the correct parent entity at the start
            info!(
                "parent: {:?}, current: {:?}, restoring",
                parent,
                world.entity(self.root).get::<Parent>().unwrap().get()
            );

            world
                .entity_mut(self.root)
                .set_parent(parent)
                .remove::<BlueprintAssetsLoaded>();

            world.send_event(BlueprintSpawned(self.root));
        })
    }
}
