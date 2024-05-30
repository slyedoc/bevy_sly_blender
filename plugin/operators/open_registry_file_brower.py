import os
import bpy
from bpy_types import (Operator)
from bpy.props import (StringProperty)
from bpy_extras.io_utils import ImportHelper

from ..settings import BevySettings


class OT_OpenRegistryFileBrowser(Operator, ImportHelper):
    """Browse for registry json file"""
    bl_idname = "bevy.open_registryfilebrowser" 
    bl_label = "Open the file browser" 

    filter_glob: StringProperty( 
        default='*.json', 
        options={'HIDDEN'} 
    ) # type: ignore
    
    def execute(self, context): 
        """Do something with the selected file(s)."""
        bevy = context.window_manager.bevy # type: BevySettings
        bevy.registry_file = self.filepath
        
        return {'FINISHED'}
    
