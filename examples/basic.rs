use bevy::{gltf::Gltf, prelude::*};
use bevy_asset_loader::prelude::*;
use bevy_sly_blender::prelude::*;

// TODO: this works with art/basic.blend, but you have to run this first to generate the registry, which works but errors due to missing assets.
// then save that art/basic.blend then run this again
// what would be ideal 

// App state to manage loading
#[derive(Default, States, Debug, Hash, PartialEq, Eq, Clone)]
pub enum AppState {
    #[default]
    Loading, // Load all asets
    Playing, // Primary State, most systems run while in this state
}

// Assets we want loaded
#[derive(AssetCollection, Resource, Debug, Reflect)]
pub struct LevelAssets {
    #[asset(path = "levels/Basic.glb")]
    pub basic: Handle<Gltf>,
}

fn main() {
    App::new()
        .add_plugins((
            DefaultPlugins,
            // our plugin, can use set to customize if needed
            BlenderPlugin {
                save_path: "../art/basic-registry.json".into(),
                ..default()
            },
        ))
        .init_state::<AppState>()
        .add_loading_state(
            LoadingState::new(AppState::Loading)
                .continue_to_state(AppState::Playing)
                .load_collection::<LevelAssets>(),
        )
        .add_systems(Startup, setup)
        .add_systems(OnEnter(AppState::Playing), (cleanup, setup_playing).chain())
        .run();
}

// Cleanup the loading screen
#[derive(Component)]
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
fn setup_playing(mut commands: Commands, models: Res<Assets<Gltf>>, levels: Res<LevelAssets>) {
    commands.spawn((
        SceneBundle {
            scene: models
                .get(levels.basic.id())
                .expect("level should have been loaded")
                .scenes[0]
                .clone(),
            ..default()
        },
        Name::new("basic"),
    ));
}
