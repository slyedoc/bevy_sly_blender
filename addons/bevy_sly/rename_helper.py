
import bpy
from bpy.props import (StringProperty)

class RenameHelper(bpy.types.PropertyGroup):
    original_name: bpy.props.StringProperty(name="") # type: ignore
    new_name: bpy.props.StringProperty(name="") # type: ignore
    #object: bpy.props.PointerProperty(type=bpy.types.Object)

    @classmethod
    def register(cls):
        return
    
    @classmethod
    def unregister(cls):
        # remove handlers & co
        return
