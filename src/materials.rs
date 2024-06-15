use std::path::Path;

use bevy::{gltf::Gltf, prelude::*, reflect::Reflect};

use crate::{BlenderAssets, BlenderPluginConfig};

#[derive(Component, Reflect, Default, Debug)]
#[reflect(Component)]
/// struct containing the name & source of the material to apply
pub struct MaterialInfo {
    pub name: String,
    pub path: String,
}

/// system that injects / replaces materials from material library
pub(crate) fn materials_inject(
    mut blueprints_config: ResMut<BlenderPluginConfig>,
    material_infos: Query<(&MaterialInfo, &Children), (Added<MaterialInfo>,)>,
    with_materials_and_meshes: Query<
        (),
        (
            With<Parent>,
            With<Handle<StandardMaterial>>,
            With<Handle<Mesh>>,
        ),
    >,
    assets_gltf: Res<Assets<Gltf>>,
    asset_server: Res<AssetServer>,
    blender_assets: Res<BlenderAssets>,
    mut commands: Commands,
) {
    for (material_info, children) in material_infos.iter() {
        info!("material_info: {:?}", material_info);
        let gltf = blender_assets.materials.get(&material_info.path).unwrap();
        let material_full_path = format!("{}#{}" , &material_info.path, &material_info.name); 

        let mut material_found: Option<&Handle<StandardMaterial>> = None;

        if blueprints_config
            .material_library_cache
            .contains_key(&material_full_path)
        {
            debug!("material is cached, retrieving");
            let material = blueprints_config
                .material_library_cache
                .get(&material_full_path)
                .expect("we should have the material available");
            material_found = Some(material);
        } else {            
            let mat_gltf = assets_gltf
                .get(gltf.id())
                .expect("material should have been preloaded");
            if mat_gltf.named_materials.contains_key(&material_info.name) {
                let material = mat_gltf
                    .named_materials
                    .get(&material_info.name)
                    .expect("this material should have been loaded");
                blueprints_config
                    .material_library_cache
                    .insert(material_full_path, material.clone());
                material_found = Some(material);
            }
        }

        if let Some(material) = material_found {
            for child in children.iter() {
                if with_materials_and_meshes.contains(*child) {
                    info!(
                        "injecting material {}, path: {:?}",
                        &material_info.name,
                        &material_info.path
                    );

                    commands.entity(*child).insert(material.clone());
                }
            }
        }
    }
}
