# bevy_sly_blender

> This is completely based off [Blender_bevy_components_workflow](https://github.com/kaosat-dev/Blender_bevy_components_workflow/)

> A ton of work has gone into it and nearly every bit of functionality comes from there.  I have really only been using blender a few months after seeing Blender_bevy_components_workflow, then a month tracking [animation-fixes-and-improvements](https://github.com/kaosat-dev/Blender_bevy_components_workflow/tree/animation-fixes-and-improvements) while learning more blender.  I was trying to figure out a few things and may have gotten carried away resulting in this repo.

# Overview

Currently focused on an ideal happy path.  Going for simplicity and ease of use over flexibility.

Using [Blender 4.2 main branch](https://github.com/blender/blender), on 4.1 there is a bug causing crashes during gltf export that is fixed on main branch. [Build notes here](https://developer.blender.org/docs/handbook/building_blender/)

Also using small fork of glTF-Blender-IO you can find [here](https://github.com/slyedoc/glTF-Blender-IO/tree/material-info), only way to complete fix the material info issue with multiple materials per mesh.

## Goals

- [x] Figure out random crashes during export in io-scene-gltf2 - fixed main branch
- [x] Flatten Entity Hierarchy - having so nested entities is a pain, and feels so foreign and complicates so many things and queries
  - Have tried ever way I can think of using bevy_scenes, but it forces nesting that just gets in the way, have bypassed it completely now, see [SpawnBlueprint](./src/blueprints.rs) and [SpawnLevel](./src/levels.rs).
- [X] Collaspse blender plugins
  - [X] Unify settings
  - [X] flatten structure  
    - [X] removed assets_registry - was only used for ui experement (will see where that goes)
    - [X] removed blueprints_registry - added to bevy_settings
- [x] Collapse bevy plugins  
- [x] Simplify paths
- [x] Blueprints always on
- [X] Material library always on
- [X] Fix material info
  - There is no way to know how many meshes io_scene_gltf2 would generate, so creating material info was not really possible.  A proper fix required a patch to [glTF-Blender-IO - material-info](https://github.com/slyedoc/glTF-Blender-IO/tree/material-info) branch that adds a material name as mesh extra, only support one material liberary scene, looked at an extension to io_scene_gltf2, but the mesh hook doesn't receive material information from what I could tell  
- [ ] Hot Reloading - kinda broke this since not using bevy_scenes to spawn
- [ ] Animations
- [ ] Simplify component_meta? - its taken a while to get my head how the blender plugin handles and creates components_meta and bevy_components, alot of the complexity comes from keeping many component_meta at a time, and when really only one is ever needed (for the selected object).  If I made that change, would it even need the all the class generation code to handle unique instances?
- [x] Build script Enums, see [doc](./docs/build.md)

## Docs

- [Level and Blueprint Enums](./docs/build.md)

## Noteable files

- [\_\_init\_\_.py](./plugin/__init__.py) - Main entry point, wire everything up
- [settings.py](./plugin/settings.py) - Settings, using as App world pretty much
- [ui/main.py](./plugin/ui/main.py) - UI
