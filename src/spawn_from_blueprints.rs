use std::{
    any::TypeId, ops::Deref, path::{Path, PathBuf}
};

use bevy::{
    ecs::{entity::EntityHashMap, reflect::ReflectMapEntities, system::Command}, gltf::Gltf, prelude::*, scene::SceneInstance, utils::{dbg, smallvec::SmallVec, HashMap}
};

use crate::{BlenderPluginConfig, BlueprintAnimations};

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

#[derive(Component)]
/// flag component for dynamically spawned scenes
pub struct Spawned;


#[derive(Component, Reflect, Default, Debug)]
#[reflect(Component)]
// this allows overriding the default library path for a given entity/blueprint
pub struct Library(pub PathBuf);

#[derive(Component, Reflect, Default, Debug)]
#[reflect(Component)]
/// flag component to force adding newly spawned entity as child of game world
pub struct AddToGameWorld;

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
            Option<&Library>,
            Option<&Name>,
            Option<&BlueprintsList>,
        ),
        (Added<BlueprintName>, Added<SpawnHere>, Without<Spawned>),
    >,

    mut commands: Commands,
    asset_server: Res<AssetServer>,
    blueprints_config: Res<BlenderPluginConfig>,
) {
    for (entity, blupeprint_name, original_parent, library_override, name, blueprints_list) in
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
            let library_path =
                library_override.map_or_else(|| &blueprints_config.library_folder, |l| &l.0);
            for (blueprint_name, _) in blueprints_list.0.iter() {
                let model_file_name = format!("{}.{}", &blueprint_name, &blueprints_config.format);
                let model_path = Path::new(&library_path).join(Path::new(model_file_name.as_str()));

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
    spawn_placeholders: Query<
        (
            Entity,
            &BlueprintName,
            Option<&Transform>,
            Option<&Parent>,
            Option<&Library>,
            Option<&AddToGameWorld>,
            Option<&Name>,
        ),
        (
            With<BlueprintAssetsLoaded>,
            Added<BlueprintAssetsLoaded>,
            Without<BlueprintAssetsNotLoaded>,
        ),
    >,

    mut commands: Commands,
    //mut game_world: Query<Entity, With<GameWorldTag>>,
    assets_gltf: Res<Assets<Gltf>>,
    asset_server: Res<AssetServer>,
    blueprints_config: Res<BlenderPluginConfig>,

    children: Query<&Children>,
) {
    for (
        entity,
        blupeprint_name,
        transform,
        original_parent,
        library_override,
        add_to_world,
        name,
    ) in spawn_placeholders.iter()
    {
        info!(
            "attempting to spawn {:?} for entity {:?}, id: {:?}, parent:{:?}",
            blupeprint_name.0, name, entity, original_parent
        );

        let what = &blupeprint_name.0;
        let model_file_name = format!("{}.{}", &what, &blueprints_config.format);

        // library path is either defined at the plugin level or overriden by optional Library components
        let library_path =
            library_override.map_or_else(|| &blueprints_config.library_folder, |l| &l.0);
        let model_path = Path::new(&library_path).join(Path::new(model_file_name.as_str()));

        // info!("attempting to spawn {:?}", model_path);
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

        commands.entity(entity).insert((
            Spawned,            
            #[cfg(feature = "animation")]
            BlueprintAnimations {
                 // these are animations specific to the inside of the blueprint
                 named_animations: gltf.named_animations.clone(),
            },
        ));

        commands.add(SpawnBlueprint {
            handle: scene.clone(),
            root: entity,
        });

        // if add_to_world.is_some() {
        //     dbg!("STOP THIS: add to game world");
        //     let world = game_world
        //         .get_single_mut()
        //         .expect("there should be a game world present");
        //     commands.entity(world).add_child(entity);
        // }
    }
}

// This is an attemp to flatten entities, it is based on the scene bundle,
// but we do everything directy since we can assume everything is loaded,
// coping logic is from bevy_scene::scene::write_to_world_with
pub struct SpawnBlueprint {
    handle: Handle<Scene>,
    root: Entity,
}

const SCENE_ROOT: Entity = Entity::from_raw(0);
const SCENE_NEW_ROOT: Entity = Entity::from_raw(1);
const COMPONENT_EXCLUDE: [TypeId; 2] = [TypeId::of::<Parent>(), TypeId::of::<Children>()];

impl Command for SpawnBlueprint {
    fn apply(self, world: &mut World) {
        let id = self.handle.id();
        let no_name = Name::new("None");
        world.resource_scope(|world, mut scenes: Mut<Assets<Scene>>| {
            // cache the root parent
            let root_parent = world.entity(self.root).get::<Parent>().unwrap().get();
            let root_parent_parent = world.entity(root_parent).get::<Parent>().unwrap().get();

            // get the scene
            let Some(scene) = scenes.get_mut(id) else {
                error!(
                    "Failed to get scene with id {:?}, make sure its loaded first",
                    id
                );
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

            // let mut query = scene.world.query::<Entity>();
            // let scene_entities = query.iter(&scene.world).collect::<Vec<_>>();

            // let blueprint_root_name = scene.world.get::<Name>(Entity::from_raw(1)).unwrap();
            // dbg!(blueprint_root_name, scene_entities.len());

            // Copy entities with components
            let mut entity_map = EntityHashMap::default();    
            // Would like to map both:
            //   -- SCENE_ROOT - root entity created by gltf loader root and its child to same scene
            // entity_map.insert(SCENE_ROOT, self.root); // this would break map_all_entities
            //   -- SCENE_NEW_ROOT its only child 
            entity_map.insert(SCENE_ROOT, self.root);            

            for archetype in scene.world.archetypes().iter() {
                for scene_entity in archetype.entities() {
                    // skip the root entity, it will be g
                    let skip = scene_entity.id() == SCENE_ROOT;
     
                    // lookup or create new entity to copy to
                    let entity = entity_map
                        .entry(scene_entity.id())
                        .or_insert_with(|| world.spawn_empty().id());

                    // copy components
                    for component_id in archetype.components() {
                        let component_info = scene
                            .world
                            .components()
                            .get_info(component_id)
                            .expect("component_ids in archetypes should have ComponentInfo");

                        let component_name = component_info.name().to_string();
                        // if component_name.contains("Ship") {
                        let entity_name = scene.world.get::<Name>(scene_entity.id()).unwrap_or(&no_name);
                        warn!("entity {:?} {:?} , scene_entity: {:?}, name: {}", entity, entity_name, scene_entity.id(), component_name);

                        let Some(reflect_component_type_id) =
                            type_registry.get(component_info.type_id().unwrap())
                        else {
                            error!(
                                "Failed to get reflect component: {}",
                                component_info.name().to_string()
                            );
                            continue;
                        };
                        let Some(reflect_component) =
                            reflect_component_type_id.data::<ReflectComponent>()
                        else {
                            error!(
                                "Failed to get reflect component: {}",
                                reflect_component_type_id
                                    .type_info()
                                    .type_path()
                                    .to_string()
                            );
                            continue;
                        };

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

            // before we could update the map on all entities, but since we are using the root entity from the command
            // this doesnt work, so only updating children of the root entity, and we update root manually

            // Map Entities, this fixes any references to entities in the copy
            for registration in type_registry.iter() {
                if let Some(map_entities_reflect) = registration.data::<ReflectMapEntities>() {
                    // cant use map_all_entities, as some parenting is already set
                    //map_entities_reflect.map_entities(world, &mut entity_map, &non_root_entites);
                    map_entities_reflect.map_all_entities(world, &mut entity_map);
                }
            }

            let root_parent2 = world.entity(self.root).get::<Parent>().unwrap().get();
            info!("root_parent: {:?}, root_parent2: {:?}, fixing", root_parent, root_parent2);

            // Fix Parenting
            world.entity_mut(self.root)
                .set_parent(root_parent);


            // let root_parent_parent2 = world.entity(root_parent).get::<Parent>().unwrap().get();
            // info!("root_parent_parent: {:?}, root_parent_parent2: {:?}, fixing", root_parent_parent,  root_parent_parent2);
        
            //world.entity_mut(root_parent).set_parent(root_parent_parent);
        })
    }
}

pub(crate) fn spawned_blueprint_post_process(
    unprocessed_entities: Query<
        (
            Entity,
            Option<&Name>,
        ),
        (With<SpawnHere>, With<SceneInstance>, With<Spawned>),
    >,
    mut commands: Commands,
) {
    for (original, name) in
        unprocessed_entities.iter()
    {
        commands.entity(original).remove::<SpawnHere>();
        commands.entity(original).remove::<Spawned>();
        commands.entity(original).remove::<Handle<Scene>>();
        commands.entity(original).remove::<AssetsToLoad<Gltf>>(); // also clear the sub assets tracker to free up handles, perhaps just freeing up the handles and leave the rest would be better ?
        commands.entity(original).remove::<BlueprintAssetsLoaded>();
        info!("post processing blueprint for entity: {:?}", name);

        // savign this code, but not using right now
        #[cfg(feature = "animation")] 
        {
            let mut root_entity = Entity::PLACEHOLDER;
            if animations.named_animations.keys().len() > 0 {
                for (added, parent) in added_animation_players.iter() {
                    if parent.get() == root_entity {
                        // FIXME: stopgap solution: since we cannot use an AnimationPlayer at the root entity level
                        // and we cannot update animation clips so that the EntityPaths point to one level deeper,
                        // BUT we still want to have some marker/control at the root entity level, we add this
                        commands
                            .entity(original)
                            .insert(BlueprintAnimationPlayerLink(added));
                    }
                }
            }
            commands.entity(root_entity).despawn_recursive();
        }



    }
}
