use bevy::prelude::*;
use bevy_asset_loader::prelude::*;
use bevy_inspector_egui::quick::WorldInspectorPlugin;
use bevy_sly_blender::prelude::*;

// TODO: this works with art/basic.blend, but you have to run this first to generate the registry, which works but errors due to missing assets.
// then save that art/basic.blend then run this again
// what would be ideal

use bevy::{gltf::Gltf, prelude::*, utils::HashMap};
use bevy_asset_loader::prelude::*;

#[derive(AssetCollection, Resource, Debug, Reflect)]
pub struct GameAssets {
    #[asset(path = "blueprints", collection(typed, mapped))]
    pub blueprints: HashMap<String, Handle<Gltf>>,

    #[asset(path = "levels", collection(typed, mapped))]
    pub levels: HashMap<String, Handle<Gltf>>,

    #[asset(path = "materials", collection(typed, mapped))]
    pub materials: HashMap<String, Handle<Gltf>>,
}

// App state to manage loading
#[derive(Default, States, Debug, Hash, PartialEq, Eq, Clone)]
pub enum AppState {
    #[default]
    Loading, // Load all asets
    Playing, // Primary State, most systems run while in this state
}

fn main() {
    App::new()
        .add_plugins((
            DefaultPlugins,
            avian3d::PhysicsPlugins::default(),
            // our plugin, can use set to customize if needed
            WorldInspectorPlugin::default(),
            BlenderPlugin {
                save_path: "../art/basic-registry.json".into(),
                ..default()
            },
        ))
        .init_state::<AppState>()
        .add_loading_state(
            LoadingState::new(AppState::Loading)
                .continue_to_state(AppState::Playing)
                // load all blueprints, levels, and materials
                .load_collection::<GameAssets>(),
        )
        .add_systems(Startup, setup)
        .add_systems(OnEnter(AppState::Playing), (cleanup, setup_playing).chain())
        .add_systems(Update, update_material.run_if(resource_exists::<GameAssets>))
        .run();
}

fn update_material(
    mut commands: Commands,
    mut load_event: EventReader<LoadMaterial>,
    assets: Res<GameAssets>,
    assets_gltf: Res<Assets<Gltf>>,
) {
    // get first material gltf
    let gltf = assets
        .materials
        .values()
        .next()
        .expect("only expect one material library right now");

    let mat_gltf = assets_gltf
        .get(gltf.id())
        .expect("gltf should have been loaded");

    for event in load_event.read() {
        if let Some(mat) = mat_gltf.named_materials.get(event.material_name.as_str()) {
            info!("material found - {:?}", &event.material_name);
            commands.entity(event.entity).insert(mat.clone());
        } else {
            panic!("material should have been found - {:?}", &event.material_name);
        }        
    }
}

// Something to add
#[allow(dead_code)]
#[derive(Component, Default)]
struct TestComponent(u8);

// Cleanup the loading screen
#[derive(Component, Default)]
struct CleanupMarker;

fn cleanup(mut commands: Commands, query: Query<Entity, With<CleanupMarker>>) {
    for e in query.iter() {
        commands.entity(e).despawn_recursive();
    }
}

// Setup the loading screen
fn setup(mut commands: Commands) {
    commands.spawn((
        Camera2dBundle::default(),
        Name::new("MainCamera"),
        CleanupMarker,
    ));

    commands.spawn((
        Text2dBundle {
            text: Text {
                sections: vec![TextSection {
                    value: "Loading".to_string(),
                    style: TextStyle {
                        font_size: 40.0,
                        color: Color::WHITE,
                        ..default()
                    },
                }],
                ..Default::default()
            },
            ..Default::default()
        },
        CleanupMarker,
    ));
}

// Setup the playing screen
fn setup_playing(
    mut commands: Commands,
    blender_assets: Res<GameAssets>,
    assets_gltf: Res<Assets<Gltf>>,
) {
    let gltf_handle = blender_assets
        .levels
        .values()
        .next()
        .expect("no levels loaded")
        .clone();

    let gltf = assets_gltf
        .get(&gltf_handle)
        .expect("gltf file should have been loaded");

    // WARNING we work under the assumtion that there is ONLY ONE named scene, and that the first one is the right one
    let main_scene_name = gltf
        .named_scenes
        .keys()
        .next()
        .expect("there should be at least one named scene in the gltf file to spawn");

    // let scene  = assets_scene.get(scene_handle).expect("scene should have been loaded");
    // let dyn_scene = assets_dyn_scene.add(DynamicScene::from_world(&scene.world));

    let s = gltf.named_scenes[main_scene_name].clone();
    #[cfg(feature = "nested")]
    commands.spawn((
        Name::new("basic-level"),
        TransformBundle::default(),
        VisibilityBundle::default(),
        s,
    ));

    #[cfg(not(feature = "nested"))]
    commands.spawn(SpawnLevel {
        handle: blender_assets
            .levels
            .values()
            .next()
            .expect("no levels loaded")
            .clone(),
        root: level,
    });
}
