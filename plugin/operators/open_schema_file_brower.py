import os
import bpy
from bpy_types import (Operator)
from bpy.props import (StringProperty)
from bpy_extras.io_utils import ImportHelper

from ..settings import BevySettings, upsert_settings


class OT_OpenSchemaFileBrowser(Operator, ImportHelper):
    """Browse for registry json file"""
    bl_idname = "bevy.open_schemafilebrowser" 
    bl_label = "Open the file browser" 

    filter_glob: StringProperty( 
        default='*.json', 
        options={'HIDDEN'} 
    ) # type: ignore
    
    def execute(self, context): 
        """Do something with the selected file(s)."""
        #filename, extension = os.path.splitext(self.filepath) 
        file_path = bpy.data.filepath
        # Get the folder
        folder_path = os.path.dirname(file_path)
        relative_path = os.path.relpath(self.filepath, folder_path)

        registry = context.window_manager.components_registry
        registry.schemaPath = relative_path

        bevy = context.window_manager.bevy # type: BevySettings
        upsert_settings(bevy.settings_save_path, {"components_schemaPath": relative_path})
        
        return {'FINISHED'}
    