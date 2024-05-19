use bevy::prelude::*;

mod components;
mod registry;
mod blueprints;

pub mod prelude {
    
    pub use crate::{
        BlenderPlugin,
        components::*,registry::*,blueprints::*};
}


pub struct BlenderPlugin;
impl Plugin for BlenderPlugin {
    fn build(&self, app: &mut App) {
        app.add_plugins((
            registry::ExportRegistryPlugin::default(),
            components::ComponentsFromGltfPlugin::default(),
            blueprints::BlueprintsPlugin::default(),
        ));
    }
}