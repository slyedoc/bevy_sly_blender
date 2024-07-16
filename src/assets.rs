use bevy::{gltf::Gltf, prelude::*, utils::HashMap};
use bevy_asset_loader::prelude::*;

#[derive(AssetCollection, Resource, Debug, Reflect)]
pub struct BlenderAssets {
    #[asset(path = "blueprints", collection(typed, mapped))]
    pub blueprints: HashMap<String, Handle<Gltf>>,

    #[asset(path = "levels", collection(typed, mapped))]
    pub levels: HashMap<String, Handle<Gltf>>,

    #[asset(path = "materials", collection(typed, mapped))]
    pub materials: HashMap<String, Handle<Gltf>>,
}
