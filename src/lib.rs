use bevy::{app::PluginGroupBuilder, prelude::*};

mod blueprints;
mod components;
mod registry;

pub mod prelude {
    pub use crate::{blueprints::*, components::*, registry::*, BlenderPlugins};
}

pub struct BlenderPlugins;

impl PluginGroup for BlenderPlugins {
    fn build(self) -> PluginGroupBuilder {
        let mut group = PluginGroupBuilder::start::<Self>();
        group = group
            .add(registry::ExportRegistryPlugin::default())
            .add(components::ComponentsFromGltfPlugin::default())
            .add(blueprints::BlueprintsPlugin::default());
        group
    }
}
