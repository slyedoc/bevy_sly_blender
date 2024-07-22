use bevy::{prelude::*, reflect::Reflect};

// Requires [glTF-Blender-IO](https://github.com/slyedoc/glTF-Blender-IO/tree/material-info) branch so MaterialName is added

#[derive(Component, Reflect, Default, Debug, Deref, DerefMut)]
#[reflect(Component)]
/// struct containing the name & source of the material to apply
pub struct MaterialName(pub String);

#[derive(Event, Debug, Clone)]
/// Event to trigger material injection
pub struct LoadMaterial {
    pub entity: Entity,
    pub material_name: String,
}

/// system that notifies the LoadMaterial event, so you can handle it yourself for now
///
///
pub(crate) fn materials_inject(
    mut commands: Commands,
    material_infos: Query<(Entity, &MaterialName), Added<MaterialName>>,    
    mut load_event: EventWriter<LoadMaterial>,
) {
    for (e, material_name) in material_infos.iter() {
        //info!("running material: {}, {}", e, material_name.0);
        load_event.send(LoadMaterial {
            entity: e,
            material_name: material_name.0.clone(),
        });
        commands.entity(e).remove::<MaterialName>();
    }
}
