# Blender plugin for bevy

> This is completely based off [Blender_bevy_components_workflow](https://github.com/kaosat-dev/Blender_bevy_components_workflow/)
> A ton of work has gone into it really has working code that does a ton.  Nearly every bit of functionality comes from there.  I was having trouble understanding it and started refactoring it so I understood it better and > I have gotten carried away. I haven't done much with blender and would rather be in rust then python.

Currently focused on an ideal happy path rather supporting every use case.

Using blender 4.2 main branch, there is a bug causing crashes during gltf export that is fixed on main.

Also using main branch for gltf export plugin.

## Goals

- [ ] Docs
- [ ] Flatten Entity Hierarchy - hate having so many, Level>Scene>Instance(Blueprint)>Collection Root>children feels so un ECS,
 makes normal querying a pain.  
 - Have tried ever way I can think of using SceneBundle system, but it forces create new entity, working on by passing it entirely (see [spawn_from_bluerpint.rs](./src/spawn_from_blueprints.rs)).
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
  - Removed BlueprintsLists and blueprint nesting, for now, will simplify more and revisit that
- [ ] GLTF settings capture by watching all operations

## Noteable files

- [\_\_init\_\_.py](./plugin/__init__.py) - Main entry point, wire everything up
- [settings.py](./plugin/settings.py) - Settings, using as App world pretty much
- [ui/main.py](./plugin/ui/main.py) - UI
