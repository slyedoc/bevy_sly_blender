use bevy::prelude::*;
use bevy_sly_blender::*;
fn main() {
    App::new()
        .add_plugins((DefaultPlugins, BlenderPlugin))
        .add_systems(Startup, setup)
        .run();
}

fn setup(
    mut commands: Commands,
    asset_server: Res<AssetServer>,
    mut materials: ResMut<Assets<StandardMaterial>>,
) {
    commands.spawn((Camera2dBundle::default(), Name::new("MainCamera")));

    // add text with the font
    //commands.spawn();
}
