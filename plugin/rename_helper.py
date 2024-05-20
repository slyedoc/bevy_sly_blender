
import bpy
from bpy.props import (StringProperty)

class RenameHelper(bpy.types.PropertyGroup):
    original_name: bpy.props.StringProperty(name="") # type: ignore
    new_name: bpy.props.StringProperty(name="") # type: ignore

    #object: bpy.props.PointerProperty(type=bpy.types.Object)
    @classmethod
    def register(cls):
        bpy.types.WindowManager.bevy_component_rename_helper = bpy.props.PointerProperty(type=RenameHelper)

    @classmethod
    def unregister(cls):
        # remove handlers & co
        del bpy.types.WindowManager.bevy_component_rename_helper
