# Blender plugin for bevy

> This completely based off [Blender_bevy_components_workflow](https://github.com/kaosat-dev/Blender_bevy_components_workflow/)
> A ton of work has gone into it really has working code that does a ton.  Every bit of functionality comes from there.  I'm trying to simplify it a bit and unroll things.  Losing some customization.

Currently focused on an ideal happy path rather supporting every use case.

# Big Issues

  Blender crashes getting all kinda of random blender crashes when exporting, some notes on tracking that down :
    bpy.ops.object.editmode_toggle()  # Operator
  
  
  Spend more hours than I will admit trying to track down blender crash when running export, would sometimes work, and not other, but consistently, last thing you see is "INFO: Starting glTF 2.0 export" and crash report all it was in gltf_exporter.  Turns out have 2 blender instances open at the same time, and running the export in one, while the other is open, will cause the crash.  So if you are having the same issue, close the other blender instance.

## Goals

- [ ] Docs
- [X] Collaspse blender plugins
  - [X] Unify settings
  - [X] flatten structure  
    - [X] removed assets_registry - was only used for ui experement (will see where that goes)
    - [X] remove blueprints_registry - added to bevy_settings
- [x] Collapse bevy plugins  
  - [X] collapse crates
- [x] Simplify paths
- [x] Blueprints always on
- [X] Material library always on
- [ ] Add animations back
- [-] Typed data
  - [-] Typed data python side
- [ ] Collapse blender data
  
- [ ] Add tests back
- [ ] Levels
  - [ ] Rename main scenes
  - [ ] removing the nesting structure for levels, and instead tag items with a level component
- [ ] Blueprints
  - [ ] Removed BlueprintsLists and blueprint nesting, for now, will simplify more and revisit that
- [ ] GLTF settings capture by watching all operations

## Noteable files

- [\_\_init\_\_.py](./plugin/__init__.py) - Main entry point, setup global data
- [settings.py](./plugin/settings.py) - Saved Settings
- [ui/main.py](./plugin/ui/main.py) - UI
