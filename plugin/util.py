import bpy
import os
import rna_prop_ui

TEMPSCENE_PREFIX = "__temp_scene"

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
