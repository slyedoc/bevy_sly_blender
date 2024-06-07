pub mod aabb;
pub mod components;
pub mod lighting;
pub mod materials;

pub use lighting::*;

pub mod spawn_from_blueprints;
pub use self::spawn_from_blueprints::*;

pub mod spawn_post_process;
pub(crate) use spawn_post_process::*;

#[cfg(feature = "registry")]
pub mod registry;
#[cfg(feature = "registry")]
pub use registry::*;

pub mod animation;
pub use animation::*;

pub mod copy_components;
pub use copy_components::*;

use core::fmt;
use std::path::PathBuf;

use bevy::{prelude::*, render::primitives::Aabb, utils::HashMap};

mod ronstring_to_reflect_component;
pub use ronstring_to_reflect_component::*;

const ASSET_ERROR: &str = "Bevy_registry_export requires access to the Bevy asset plugin. \
    Please add `ExportRegistryPlugin` after `AssetPlugin`, which is commonly added as part of the `DefaultPlugins`";

pub mod prelude {
    #[cfg(feature = "registry")]
    pub use crate::registry::*;
    pub use crate::{
        BlenderPlugin,
        GltfFormat,
        GltfBlueprintsSet,
        BluePrintBundle,
        BlueprintName,
        components::*, materials::*,};
}

#[derive(SystemSet, Debug, Hash, PartialEq, Eq, Clone)]
/// set for the two stages of blueprint based spawning :
pub enum GltfBlueprintsSet {
    Injection,
    Spawn,
    AfterSpawn,
}


#[derive(Debug, Clone)]
/// Plugin for gltf blueprints
pub struct BlenderPlugin {
    pub format: GltfFormat,
    /// The base folder where library/blueprints assets are loaded from, relative to the executable.
    pub library_folder: PathBuf,

    /// Automatically generate aabbs for the blueprints root objects
    pub aabbs: bool,
    ///
    pub material_library: bool,
    pub material_library_folder: PathBuf,

    // registry
    pub save_path: PathBuf,
    pub component_filter: SceneFilter,
    pub resource_filter: SceneFilter,
    
}

impl Default for BlenderPlugin {
    fn default() -> Self {
        Self {
            format: GltfFormat::GLB,
            library_folder: PathBuf::from("blueprints"),
            aabbs: false,
            material_library: false,
            material_library_folder: PathBuf::from("materials"),

            component_filter: SceneFilter::default(),
            resource_filter: SceneFilter::default(),
            save_path: PathBuf::from("registry.json"), // relative to assets folder
        }
    }
}


impl Plugin for BlenderPlugin {
    fn build(&self, app: &mut App) {

        #[cfg(feature = "registry")]
        {
            // hack to get the asset path, could be removed?
            let asset_plugins: Vec<&AssetPlugin> = app.get_added_plugins();
            let asset_plugin = asset_plugins.into_iter().next().expect(ASSET_ERROR);
            let path_str = asset_plugin.file_path.clone();
            let path = PathBuf::from(path_str);

            app.insert_resource(AssetRoot(path))
                .add_systems(Startup, export_types);
        }

        app
            .add_plugins((
                lighting::plugin, // custom lighting 
                components::plugin, // spawn components from gltf extras
            ))
            // rest
            .register_type::<BlueprintName>()
            .register_type::<materials::MaterialInfo>()
            .register_type::<SpawnHere>()
            .register_type::<BlueprintAnimations>()
            .register_type::<SceneAnimations>()
            .register_type::<AnimationInfo>()
            .register_type::<AnimationInfos>()
            .register_type::<Vec<AnimationInfo>>()
            .register_type::<AnimationMarkers>()
            .register_type::<HashMap<u32, Vec<String>>>()
            .register_type::<HashMap<String, HashMap<u32, Vec<String>>>>()
            .add_event::<AnimationMarkerReached>()
            .register_type::<BlueprintsList>()
            .register_type::<HashMap<String, Vec<String>>>()
            .insert_resource(BlenderPluginConfig {
                format: self.format,
                library_folder: self.library_folder.clone(),

                aabbs: self.aabbs,
                aabb_cache: HashMap::new(),

                material_library: self.material_library,
                material_library_folder: self.material_library_folder.clone(),
                material_library_cache: HashMap::new(),

                save_path: self.save_path.clone(),
                component_filter: self.component_filter.clone(),
                resource_filter: self.resource_filter.clone(),
            })
            .configure_sets(
                Update,
                (
                    GltfBlueprintsSet::Injection,
                    GltfBlueprintsSet::Spawn,
                    GltfBlueprintsSet::AfterSpawn,
                )
                    .chain(),
            )
            .add_systems(
                Update,
                (
                    (
                        prepare_blueprints,
                        check_for_loaded,
                        spawn_from_blueprints,
                        apply_deferred,
                    )
                        .chain(),
                    (aabb::compute_scene_aabbs, apply_deferred)
                        .chain()
                        .run_if(aabbs_enabled),
                    // apply_deferred, think this dupicate was an error
                    (
                        materials::materials_inject,
                        materials::check_for_material_loaded,
                        materials::materials_inject2,
                    )
                        .chain()
                        .run_if(materials_library_enabled),
                )
                    .chain()
                    .in_set(GltfBlueprintsSet::Spawn),
            )
            .add_systems(
                Update,
                (spawned_blueprint_post_process, apply_deferred)
                    .chain()
                    .in_set(GltfBlueprintsSet::AfterSpawn),
            )
            .add_systems(
                Update,
                (
                    trigger_instance_animation_markers_events,
                    trigger_blueprint_animation_markers_events,
                ),
            );
    }
}


#[derive(Bundle)]
pub struct BluePrintBundle {
    pub blueprint: BlueprintName,
    pub spawn_here: SpawnHere,
}
impl Default for BluePrintBundle {
    fn default() -> Self {
        BluePrintBundle {
            blueprint: BlueprintName("default".into()),
            spawn_here: SpawnHere,
        }
    }
}

#[derive(Clone, Resource)]
pub struct BlenderPluginConfig {
    pub format: GltfFormat,
    pub library_folder: PathBuf,
    pub aabbs: bool,
    pub aabb_cache: HashMap<String, Aabb>, // cache for aabbs

    pub material_library: bool,
    pub material_library_folder: PathBuf,
    pub material_library_cache: HashMap<String, Handle<StandardMaterial>>,

    // registry config
    pub(crate) save_path: PathBuf,
    #[allow(dead_code)]
    pub(crate) component_filter: SceneFilter,
    #[allow(dead_code)]
    pub(crate) resource_filter: SceneFilter,
}

#[derive(Debug, Clone, Copy, Eq, PartialEq, Hash, Default)]
pub enum GltfFormat {
    #[default]
    GLB,
    GLTF,
}

impl fmt::Display for GltfFormat {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            GltfFormat::GLB => {
                write!(f, "glb",)
            }
            GltfFormat::GLTF => {
                write!(f, "gltf")
            }
        }
    }
}


fn aabbs_enabled(blueprints_config: Res<BlenderPluginConfig>) -> bool {
    blueprints_config.aabbs
}

fn materials_library_enabled(blueprints_config: Res<BlenderPluginConfig>) -> bool {
    blueprints_config.material_library
}
