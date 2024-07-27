# bevy_sly_blender

> This is completely based off [Blender_bevy_components_workflow](https://github.com/kaosat-dev/Blender_bevy_components_workflow/), and you should go use it.

 A ton of work has gone into it and nearly every bit of functionality comes from there. I wanted to understand it and iterate on it.

## Overview

Currently focused on an ideal happy path.  Going for simplicity and ease of use over flexibility.

Using [Blender 4.2 main branch](https://github.com/blender/blender), on 4.1 there is a bug causing crashes during gltf export that is fixed on main branch. [Build notes here](https://developer.blender.org/docs/handbook/building_blender/)

Also using small fork of glTF-Blender-IO you can find [here](https://github.com/slyedoc/glTF-Blender-IO/tree/material-info), only way to completely fix the material info issue with multiple materials per mesh and reduce log output.

## Noteable files

- [\_\_init\_\_.py](./plugin/__init__.py) - Main entry point, wire everything up
- [settings.py](./plugin/settings.py) - Settings, using as App world pretty much
- [ui/main.py](./plugin/ui/main.py) - UI