use bevy::{app::PluginGroupBuilder, prelude::*};

mod blueprints;
mod components;
#[cfg(feature = "registry")]
mod registry;

pub mod prelude {
    pub use crate::{blueprints::*, components::*, BlenderPlugins};
    #[cfg(feature = "registry")]
    pub use crate::registry::*;    
}

pub struct BlenderPlugins;

impl PluginGroup for BlenderPlugins {
    fn build(self) -> PluginGroupBuilder {
        let mut group = PluginGroupBuilder::start::<Self>();
        group = group            
            .add(components::ComponentsFromGltfPlugin::default())
            .add(blueprints::BlueprintsPlugin::default());

        #[cfg(feature = "registry")] {
            group = group.add(registry::ExportRegistryPlugin::default());
        }

        group
    }
}
