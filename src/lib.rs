#![feature(const_type_id)] // for type_id exclude list

pub mod aabb;
pub mod levels;
pub mod lighting;
pub mod materials;

mod assets;
pub use assets::*;

pub use lighting::*;

pub mod blueprints;
pub use blueprints::*;
pub use levels::*;

#[cfg(feature = "physics")]
pub mod physics;

#[cfg(feature = "registry")]
pub mod registry;
use physics::ProxyCollider;
#[cfg(feature = "registry")]
pub use registry::*;

pub mod animation;
pub use animation::*;

use core::fmt;
use std::path::PathBuf;

use bevy::{
    gltf::GltfExtras, prelude::*, render::primitives::Aabb, transform::TransformSystem,
    utils::HashMap,
};

mod ronstring_to_reflect_component;
pub use ronstring_to_reflect_component::*;

pub mod prelude {
    pub use crate::{
        assets::*, blueprints::*, levels::*, materials::*, BlenderPlugin, GltfBlueprintsSet,
        GltfFormat,
    };

    #[cfg(feature = "registry")]
    pub use crate::registry::*;
}

#[derive(SystemSet, Debug, Hash, PartialEq, Eq, Clone)]
/// set for the two stages of blueprint based spawning :
pub enum GltfBlueprintsSet {
    Injection,
    Spawn,
    Extras,
}

#[derive(Debug, Clone)]
/// Plugin for gltf blueprints
pub struct BlenderPlugin {
    pub format: GltfFormat,

    /// The base folder where library/blueprints assets are loaded from, relative to the executable.
    pub blueprint_folder: PathBuf,
    pub level_folder: PathBuf,
    pub material_folder: PathBuf,

    /// Automatically generate aabbs for the blueprints root objects
    pub aabbs: bool,

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
            aabbs: false,
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

    pub aabbs: bool,
    pub aabb_cache: HashMap<String, Aabb>, // cache for aabbs

    // registry config
    pub(crate) save_path: PathBuf,
    #[allow(dead_code)]
    pub(crate) component_filter: SceneFilter,
    #[allow(dead_code)]
    pub(crate) resource_filter: SceneFilter,
}

#[derive(Event, Debug, Clone)]
pub struct BlueprintSpawned(pub Entity);

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
            lighting::plugin, // custom lighting
            #[cfg(feature = "physics")]
            physics::plugin,
        ))
        // rest
        .register_type::<BlueprintName>()
        .register_type::<materials::MaterialName>()
        .register_type::<BlueprintAnimations>()
        .register_type::<SceneAnimations>()
        .register_type::<AnimationInfo>()
        .register_type::<AnimationInfos>()
        .register_type::<Vec<AnimationInfo>>()
        .register_type::<AnimationMarkers>()
        .register_type::<HashMap<u32, Vec<String>>>()
        .register_type::<HashMap<String, HashMap<u32, Vec<String>>>>()
        .add_event::<AnimationMarkerReached>()
        .add_event::<BlueprintSpawned>()
        .register_type::<HashMap<String, Vec<String>>>()
        .insert_resource(BlenderPluginConfig {
            format: self.format,
            blueprint_folder: self.blueprint_folder.clone(),
            level_folder: self.level_folder.clone(),
            materials_library: self.material_folder.clone(),
            aabbs: self.aabbs,
            aabb_cache: HashMap::new(),

            save_path: self.save_path.clone(),
            component_filter: self.component_filter.clone(),
            resource_filter: self.resource_filter.clone(),
        })
        .configure_sets(
            Update,
            (
                GltfBlueprintsSet::Injection,
                GltfBlueprintsSet::Spawn,
                GltfBlueprintsSet::Extras,
            )
                .chain(),
        )
        .add_systems(
            Update,
            (
                (
                    // Spawn by names
                    spawn_from_level_name,
                    spawn_from_blueprint_name,
                    apply_deferred,
                    // spawn from gltf
                    spawn_level_from_gltf,
                    apply_deferred,
                    spawn_blueprint_from_gltf,
                    apply_deferred,
                )
                    .chain(),
                (aabb::compute_scene_aabbs, apply_deferred)
                    .chain()
                    .run_if(aabbs_enabled.and_then(on_event::<BlueprintSpawned>())),
                materials::materials_inject.run_if(resource_exists::<BlenderAssets>),
            )
                .chain()
                .in_set(GltfBlueprintsSet::Spawn),
        )
        .add_systems(
            Update,
            (
                trigger_instance_animation_markers_events,
                trigger_blueprint_animation_markers_events,
            ),
        )
        .add_systems(Update, gltf_extras.in_set(GltfBlueprintsSet::Extras));

        app.register_type::<ProxyCollider>().add_systems(
            Update,
            (physics::physics_replace_proxies)
                .after(TransformSystem::TransformPropagate)
                .in_set(GltfBlueprintsSet::Extras),
        );
    }
}

#[derive(Debug, Clone, Copy, Eq, PartialEq, Hash, Default)]
pub enum GltfFormat {
    #[default]
    GLB,
    GLTF, // TODO: test, been using
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

// parse gltf extras on added and spawn the components
// note: using world so we can make use of ReflectComponent::insert
fn gltf_extras(world: &mut World) {
    // get the added extras
    let extras = world
        .query::<(Entity, &GltfExtras)>()
        //.query_filtered::<(Entity, &GltfExtras), Added<GltfExtras>>()
        .iter(world)
        .map(|(entity, extra)| (entity.clone(), extra.clone()))
        .collect::<Vec<(Entity, GltfExtras)>>();

    if !extras.is_empty() {
        // add the components
        world.resource_scope(|world, type_registry: Mut<AppTypeRegistry>| {
            let type_registry = type_registry.read();
            for (entity, extra) in &extras {
                let reflect_components =
                    ronstring_to_reflect_component(&extra.value, &type_registry);

                for (component, type_registration) in reflect_components {
                    //dbg!(entity, &component);
                    let mut entity_mut = world.entity_mut(*entity);
                    type_registration
                        .data::<ReflectComponent>()
                        .expect("Unable to reflect component")
                        .insert(&mut entity_mut, &*component, &type_registry);
                }
            }
        });
        //dbg!(&extras);
    }

    // remove the extras
    for (entity, _) in &extras {
        world.entity_mut(*entity).remove::<GltfExtras>();
    }
}
