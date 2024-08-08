//#![feature(const_type_id)] // for type_id exclude list

pub mod aabb;

pub mod lighting;
//pub use lighting::*;


#[cfg(feature = "registry")]
pub mod registry;
#[cfg(feature = "registry")]
pub use registry::*;

use core::fmt;
use std::path::PathBuf;

use bevy::{prelude::*, utils::HashMap};

mod ronstring_to_reflect_component;
pub use ronstring_to_reflect_component::*;

pub mod prelude {
    pub use crate::{
        BlenderPlugin, GltfFormat,
    };

    #[cfg(feature = "registry")]
    pub use crate::registry::*;
}

// #[derive(SystemSet, Debug, Hash, PartialEq, Eq, Clone)]
// /// set for the two stages of blueprint based spawning :
// pub enum BlenderSet {
//     //Spawn,
//     Injection,
// }



#[derive(Debug, Clone)]
/// Plugin for gltf blueprints
pub struct BlenderPlugin {
    pub format: GltfFormat,

    /// The base folder where library/blueprints assets are loaded from, relative to the executable.
    pub blueprint_folder: PathBuf,
    pub level_folder: PathBuf,
    pub material_folder: PathBuf,

    /// Automatically generate aabbs for the blueprints root objects
    //pub aabbs: bool,

    // registry
    pub save_path: PathBuf,
    pub component_filter: SceneFilter,
    pub resource_filter: SceneFilter,
}

impl Default for BlenderPlugin { 
    fn default() -> Self {
        Self {
            format: GltfFormat::GLB,
            blueprint_folder: PathBuf::from("blueprints"),
            level_folder: PathBuf::from("levels"),
            material_folder: PathBuf::from("materials"),
            save_path: PathBuf::from("registry.json"), // relative to assets folder
            //aabbs: false,
            component_filter: SceneFilter::default(),
            resource_filter: SceneFilter::default(),
        }
    }
}

#[derive(Clone, Resource)]
pub struct BlenderPluginConfig {
    pub format: GltfFormat,

    pub blueprint_folder: PathBuf,
    pub level_folder: PathBuf,
    pub materials_library: PathBuf,

    //pub aabbs: bool,
    //pub aabb_cache: HashMap<String, Aabb>, // cache for aabbs

    // registry config
    #[allow(dead_code)]
    pub(crate) save_path: PathBuf,
    #[allow(dead_code)]
    pub(crate) component_filter: SceneFilter,
    #[allow(dead_code)]
    pub(crate) resource_filter: SceneFilter,
}

// #[derive(Event, Debug, Clone)]
// pub struct BlueprintSpawned(pub Entity);

impl Plugin for BlenderPlugin {
    fn build(&self, app: &mut App) {
        #[cfg(feature = "registry")]
        {
            // hack to get the asset path, could be removed?
            let asset_plugins: Vec<&AssetPlugin> = app.get_added_plugins();
            let asset_plugin = asset_plugins.into_iter().next().expect(
                "Asset plugin required. Please add `ExportRegistryPlugin` after `AssetPlugin`",
            );
            let path_str = asset_plugin.file_path.clone();
            let path = PathBuf::from(path_str);

            app.insert_resource(AssetRoot(path))
                .add_systems(Startup, export_types);
        }

        app.add_plugins((
            //lighting::plugin, // custom lighting
        ))
        // rest
        // .register_type::<BlueprintName>()
        // .register_type::<MaterialName>()
        // .add_event::<BlueprintSpawned>()
        .register_type::<HashMap<String, Vec<String>>>()
        .insert_resource(BlenderPluginConfig {
            format: self.format,
            blueprint_folder: self.blueprint_folder.clone(),
            level_folder: self.level_folder.clone(),
            materials_library: self.material_folder.clone(),
            //aabbs: self.aabbs,
            //aabb_cache: HashMap::new(),

            save_path: self.save_path.clone(),
            component_filter: self.component_filter.clone(),
            resource_filter: self.resource_filter.clone(),
        });
        // .configure_sets(
        //     PostUpdate,
        //     (
        //         BlenderSet::Injection,
        //     )
        //         .chain(),
        // )

        // .add_systems(
        //     PostUpdate,
        //     (
        //         //spawn_gltf_extras,
        //         //aabb::compute_scene_aabbs.run_if(aabbs_enabled), // .and_then(on_event::<BlueprintSpawned>())
        //     )
        //         .chain()
        //         .in_set(BlenderSet::Injection),
        // );
    }
}

// Helper to spawn from name blueprints
// #[derive(Component, Reflect, Default, Debug)]
// #[reflect(Component)]
// pub struct BlueprintName(pub String);

// Requires [glTF-Blender-IO](https://github.com/slyedoc/glTF-Blender-IO/tree/material-info) branch so MaterialName is added
// #[derive(Component, Reflect, Default, Debug, Deref, DerefMut)]
// #[reflect(Component)]
// /// struct containing the name & source of the material to apply
// pub struct MaterialName(pub String);


#[derive(Debug, Clone, Copy, Eq, PartialEq, Hash, Default)]
pub enum GltfFormat {
    #[default]
    GLB,
    //GLTF, // TODO: test, been using
}

impl fmt::Display for GltfFormat {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            GltfFormat::GLB => {
                write!(f, "glb",)
            }
            // GltfFormat::GLTF => {
            //     write!(f, "gltf")
            // }
        }
    }
}

// fn aabbs_enabled(blueprints_config: Res<BlenderPluginConfig>) -> bool {
//     blueprints_config.aabbs
// }

