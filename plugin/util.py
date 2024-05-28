import bpy
import os
import rna_prop_ui

# TODO: settings that maybe should just be the default
# can move to setttings if really needed
SETTING_NAME = ".bevy_settings"

EXPORT_MARKED_ASSETS = True
#EXPORT_BLUEPRINTS = Only True - Not longer an option
EXPORT_MATERIALS_LIBRARY = True 
EXPORT_STATIC_DYNAMIC = False # dont use this yet
EXPORT_SCENE_SETTINGS = True
CHANGE_DETECTION = True

GLTF_EXTENSION = ".glb" #".gltf"
TEMPSCENE_PREFIX = "__temp_scene"

BLUEPRINTS_PATH = "blueprints"
LEVELS_PATH = "levels"
MATERIALS_PATH = "materials"

# fake way to make our operator's changes be visible to the change/depsgraph update handler in gltf_auto_export
def ping_depsgraph_update(object):
    rna_prop_ui.rna_idprop_ui_create(object, "________temp", default=0)
    rna_prop_ui.rna_idprop_ui_prop_clear(object, "________temp")

def absolute_path_from_blend_file(path):
    # path to the current blend file
    blend_file_path = bpy.data.filepath
    # Get the folder
    blend_file_folder_path = os.path.dirname(blend_file_path) 

    # absolute path
    return os.path.abspath(os.path.join(blend_file_folder_path, path))
