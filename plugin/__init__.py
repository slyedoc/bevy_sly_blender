bl_info = {
    "name": "bevy_sly_blender",
    "author": "slyedoc",
    "version": (0, 1, 0),
    "blender": (4, 1, 0),
    "description": "simple tooling for the Bevy",
    "warning": "",
    "wiki_url": "https://github.com/slyedoc/bevy_sly_blender",
    "tracker_url": "https://github.com/slyedoc/bevy_sly_blender/issues/new",
    "category": "Import-Export"
}

import bpy
from .ui.main import BEVY_PT_MainPanel
from .ui.switch import OT_switch_bevy_tooling
# from bpy_types import (PropertyGroup)
# from bpy.app.handlers import persistent
# from bpy.props import (BoolProperty, StringProperty, PointerProperty, EnumProperty)

from .settings import (BevySettings, upsert_settings, load_settings)

classes = [
    # main
    BevySettings, # PropertyGroup for settings

    BEVY_PT_MainPanel,
    #operators
    OT_switch_bevy_tooling
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    #bpy.app.handlers.load_post.append(post_load)
    # for some reason, adding these directly to the tracker class in register() do not work reliably
    #bpy.app.handlers.depsgraph_update_post.append(post_update)
    #bpy.app.handlers.save_post.append(post_save)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    #del bpy.types.WindowManager.bevy
    #bpy.app.handlers.load_post.remove(post_load)
    #bpy.app.handlers.depsgraph_update_post.remove(post_update)
    #bpy.app.handlers.save_post.remove(post_save)
 
if __name__ == "__main__":
    register()

# def update_scene_lists(self, context):                
#     blenvy = self# context.window_manager.blenvy
#     blenvy.main_scene_names = [scene.name for scene in blenvy.main_scenes] # FIXME: unsure
#     blenvy.library_scene_names = [scene.name for scene in blenvy.library_scenes] # FIXME: unsure
#     upsert_settings(blenvy.settings_save_path, {"common_main_scene_names": [scene.name for scene in blenvy.main_scenes]})
#     upsert_settings(blenvy.settings_save_path, {"common_library_scene_names": [scene.name for scene in blenvy.library_scenes]})

# def update_asset_folders(self, context):
#     blenvy = context.window_manager.blenvy
#     asset_path_names = ['project_root_path', 'assets_path', 'blueprints_path', 'levels_path', 'materials_path']
#     for asset_path_name in asset_path_names:
#         upsert_settings(blenvy.settings_save_path, {asset_path_name: getattr(blenvy, asset_path_name)})

# def update_mode(self, context):
#     blenvy = self # context.window_manager.blenvy
#     upsert_settings(blenvy.settings_save_path, {"mode": blenvy.mode })


# @persistent
# def post_update(scene, depsgraph):
#     print("post_update");
    #bpy.context.window_manager.auto_export_tracker.deps_post_update_handler( scene, depsgraph)

# @persistent
# def post_save(scene, depsgraph):
#     print("post_save");
    #bpy.context.window_manager.auto_export_tracker.save_handler( scene, depsgraph)

# @persistent
# def post_load(file_name):
#     print("post_load");
    # registry = bpy.context.window_manager.components_registry
    # if registry  is not None:
    #     registry.load_settings()
    # blenvy = bpy.context.window_manager.blenvy
    # if blenvy is not None:
    #     blenvy.load_settings()
