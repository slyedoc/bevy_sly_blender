use bevy::{gltf::Gltf, prelude::*, reflect::Reflect};

use crate::BlenderAssets;

// Requires [glTF-Blender-IO](https://github.com/slyedoc/glTF-Blender-IO/tree/material-info) branch so MaterialName is added

#[derive(Component, Reflect, Default, Debug, Deref, DerefMut)]
#[reflect(Component)]
/// struct containing the name & source of the material to apply
pub struct MaterialName(pub String);

/// system that injects / replaces materials from material library
pub(crate) fn materials_inject(
    mut commands: Commands,
    material_infos: Query<(Entity, &MaterialName), (Added<MaterialName>,)>,
    assets_gltf: Res<Assets<Gltf>>,
    blender_assets: Res<BlenderAssets>,
) {
    for (e, material_name) in material_infos.iter() {
        // get first material gltf
        let gltf = blender_assets
            .materials
            .values()
            .next()
            .expect("only expect one material library right now");

        let mat_gltf = assets_gltf
            .get(gltf.id())
            .expect("gltf should have been loaded");

        if let Some(mat) = mat_gltf.named_materials.get(&material_name.0) {
            commands.entity(e).insert(mat.clone());            
        } else {
            info!("material should have been found - {:?}", &material_name.0);
        }
    }
}
