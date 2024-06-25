# Build Enums

I hate magic strings and would rather use an enum for everything like most rustaceans.  This is how I am generating them for Levels and Blueprints along the path info so with BlenderAssets it's pretty nice.

> This is a bit hacky and is why it's not part of the plugin:

```rust
// turn this
commands.spawn((
    BlueprintName("Menu"), // Booo
    Transform::from_xyz(0.0, 0.0, 0.0),
));

// into this
commands.spawn((
    Blueprint::Menu, // Yay
    Transform::from_xyz(0.0, 0.0, 0.0),
));

```

## Build Script

Update or add a build.rs file to the root of your project

```rust
/// This build script generates the `blender_enums.rs` file which contains the `Level` and `Blueprint` enums.
use std::env;
use std::fs::{self};
use std::io::{self, Write};
use std::path::{Path, PathBuf};

/// Generate for [`blender_enums.rs`]
fn main() -> io::Result<()> {
    let out_dir = env::var("OUT_DIR").unwrap();
    let file_path = Path::new(&out_dir).join("blender_enums.rs");
    
    let manifest_dir = env::var("CARGO_MANIFEST_DIR").unwrap();
    let project_root = PathBuf::from(&manifest_dir);
    
    let level_path = Path::new(&manifest_dir).join("assets/levels");
    let blueprint_path = Path::new(&manifest_dir).join("assets/blueprints");

    // Tell cargo to rerun this build script if any of the files in the asset directories change
    println!("cargo:rerun-if-changed={:?}", level_path);
    println!("cargo:rerun-if-changed={:?}", blueprint_path);

    // Generate file
    let mut f = fs::File::create(&file_path)?;
    
    // Generate the Level enum
    write_enum(&mut f, "Level", level_path.as_path(), &project_root)?;

    // // Generate the Blueprints enum
    write_enum(&mut f, "Blueprint", blueprint_path.as_path(), &project_root)?;

    Ok(())
}

fn write_enum(f: &mut fs::File, enum_name: &str, dir_path: &Path, project_root: &PathBuf) -> io::Result<()> {    
    write!(f, "#[derive(Debug, Default, Component, States, Clone, PartialEq, Eq, Hash, Serialize, Deserialize, Reflect, EnumIter)]\n")?;
    write!(f, "#[reflect(Default, Serialize, Deserialize)]\n")?;
    write!(f, "pub enum {} {{\n", enum_name)?;
    write!(f, "    #[default]\n")?;

    let mut mappings = Vec::new();

    let mut entries = fs::read_dir(dir_path)?
        .filter_map(|e| e.ok())
        .filter(|e| e.path().extension().map_or(false, |ext| ext == "glb"))
        .collect::<Vec<_>>();
    entries.sort_by(|a, b| a.path().file_stem().cmp(&b.path().file_stem()));

    for entry in entries {
        let file_stem = entry
            .path()
            .file_stem()
            .unwrap()
            .to_str()
            .unwrap()
            .to_owned();
        let sanitized_name = sanitize_file_name(&file_stem);
        write!(f, "    {},\n", sanitized_name)?;

        // Create a path relative to the project root
        let file_path = entry.path();
        let relative_path = file_path.strip_prefix(&project_root.join("assets")).unwrap();

        // Save the mapping from enum variant to file path
        let path_str = relative_path.display().to_string().replace("\\", "/");
        mappings.push(format!(
            "    {}::{} => \"{}\"",
            enum_name, sanitized_name, path_str
        ));
    }

    write!(f, "}}\n\n")?; // Close enum definition

    // Write the constant map
    write!(f, "impl {} {{\n", enum_name)?;
    write!(f, "    pub fn path(&self) -> String {{\n")?;
    write!(f, "        match self {{\n")?;
    // write!(f, "            {}::None => \"\".to_owned(),\n", enum_name)?;
    for mapping in mappings {
        write!(f, "        {}.to_owned(),\n", mapping)?;
    }
    write!(f, "        }}\n")?;
    write!(f, "    }}\n")?;
    write!(f, "}}\n\n")?; // Close impl block

    Ok(())
}

fn sanitize_file_name(name: &String) -> String {
    name.split(|c: char| !c.is_alphanumeric())
        .filter(|part| !part.is_empty())
        .map(|part| {
            let mut chars = part.chars();
            chars
                .next()
                .unwrap()
                .to_uppercase()
                .chain(chars.flat_map(|c| c.to_lowercase()))
                .collect::<String>()
        })
        .collect()
}
```

Update your `Cargo.toml` to include the build script

```toml
[package]
build = "build.rs"
```

Now we need to include the generated file in your project

```rust
include!(concat!(env!("OUT_DIR"), "/blender_enums.rs"));
```

For me, it's in a plugin that looks something like:

```rust
use crate::prelude::*;
use bevy::{gltf::Gltf, prelude::*, transform::commands, utils::HashMap};
use bevy_asset_loader::prelude::*;

use bevy_sly_blender::prelude::*;
// needed in generated code
use serde::{Deserialize, Serialize};
pub use strum_macros::EnumIter;

// Generated:
//      Level enum from ./assets/levels/ directory
//      Blueprint enum from ./assets/blueprints/ directory
//      impl a path method for Level and Blueprint to get file path
include!(concat!(env!("OUT_DIR"), "/blender_enums.rs"));

pub fn plugin(app: &mut App) {
    app.register_type::<Level>()
        .register_type::<Blueprint>()
        .init_state::<Level>()
        .add_systems(Update, spawn.run_if(not(in_state(AppState::Loading))));
}

pub fn spawn(
    mut commands: Commands,
    blueprints: Query<(Entity, &Blueprint), Added<Blueprint>>,
    levels: Query<(Entity, &Level), Added<Level>>,
    blender_assets: Res<BlenderAssets>,
) {
    for (e, b) in blueprints.iter() {
        commands.entity(e).insert(BlueprintGltf(
            blender_assets.blueprints.get(&b.path()).unwrap().clone(),
        ));
    }
}

```

Now every time you build your project cargo will look thought your assets directory and create enums based on the *.glb files it finds there.

## Notes

- This has been useful for when I have blueprints names that conflict with each other, you get compile errors about duplicate enum value you know exactly which it is.
- Bet there is a better way to do this
