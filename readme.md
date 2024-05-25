# Blender plugin for bevy

> This completely based off [Blender_bevy_components_workflow](https://github.com/kaosat-dev/Blender_bevy_components_workflow/)

After spending some time debugging a few things I wanted to see if I could refactor to simply things and focus on an ideal happy path rather supporting every use case.

Goals:

- [X] Reduce to 1 plugin
  - [X] Unify settings
  - [X] flatten structure to make it easier to understand

- [x] Simplify paths
- [ ] Typed data
- [ ] Remove unused code
- [ ] Add tests back

## Noteable files

- [\_\_init\_\_.py](./plugin/__init__.py) - Main entry point for the plugin
- [settings.py](./plugin/settings.py) - Saved Settings
- [ui/main.py](./plugin/ui/main.py) - UI