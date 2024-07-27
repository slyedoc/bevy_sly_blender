use bevy::{prelude::*, reflect::Reflect};

// Requires [glTF-Blender-IO](https://github.com/slyedoc/glTF-Blender-IO/tree/material-info) branch so MaterialName is added

#[derive(Component, Reflect, Default, Debug, Deref, DerefMut)]
#[reflect(Component)]
/// struct containing the name & source of the material to apply
pub struct MaterialName(pub String);


