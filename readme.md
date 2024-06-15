# Blender plugin for bevy

> This is completely based off [Blender_bevy_components_workflow](https://github.com/kaosat-dev/Blender_bevy_components_workflow/)
> A ton of work has gone into it really has working code that does a ton.  Nearly every bit of functionality comes from there.  I was having trouble understanding it and started refactoring and I have gotten carried away. I haven't done much with blender and would rather be in rust then python.

Currently focused on an ideal happy path rather supporting every use case.

Using [Blender 4.2 main branch](https://github.com/blender/blender), on 4.1  there is a bug causing crashes during gltf export that is fixed on main branch. [Build notes here](https://developer.blender.org/docs/handbook/building_blender/)

Also using main branch for [glTF-Blender-IO](https://github.com/slyedoc/glTF-Blender-IO/tree/material-info) based on lasted version to fix material info. Only few lines changed.

## Goals

- [ ] Docs
- [x] Flatten Entity Hierarchy - hate having so many, Level>Scene>Instance(Blueprint)>Collection Root>children feels so un ECS,
 and systems far to complicated when it should be simple queries.
  - Have tried ever way I can think of using bevy_scenes, but it forces nesting that just gets in the way, have bypassed it completely now, see [bluerpints.rs](./src/blueprints.rs) and [levels.rs](./src/levels.rs).
- [ ] Simplify UI
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
- [X] Fix material info
- There is no way to know how many meshes io_scene_gltf2 would generate, so creating material info was not really possible.  A proper fix required a patch to [glTF-Blender-IO - material-info](https://github.com/slyedoc/glTF-Blender-IO/tree/material-info) branch that adds a material name as mesh extra, only only support one material liberary scene.
- [ ] Reload in bevy on file changes
- [ ] Add animations back
- [ ] Add tests back

## Noteable files

- [\_\_init\_\_.py](./plugin/__init__.py) - Main entry point, wire everything up
- [settings.py](./plugin/settings.py) - Settings, using as App world pretty much
- [ui/main.py](./plugin/ui/main.py) - UI
