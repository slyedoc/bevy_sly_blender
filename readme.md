# Blender plugin for bevy

> This completely based off [Blender_bevy_components_workflow](https://github.com/kaosat-dev/Blender_bevy_components_workflow/)
> A ton of work has gone into it really has working code that does a ton.  Every bit of functionality comes from there.  I'm trying to simplify it a bit and unroll things.  Losing some customization.

Currently focused on an ideal happy path rather supporting every use case.

## Goals

- [X] Collaspse blender plugins
  - [X] Unify settings
  - [X] flatten structure  
    - [ ] still some window_manager property groups that could be removed
- [x] Collapse bevy plugins  
  - [X] collapse crates
- [x] Simplify paths
- [x] Blueprints always on
- [X] Material library always on
- [-] Typed data
  - [-] Typed data python side
- [ ] Remove unused code
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
