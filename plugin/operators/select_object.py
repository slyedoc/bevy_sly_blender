import bpy

from bpy.props import (StringProperty)
from bpy_extras.io_utils import ImportHelper


class OT_select_object(bpy.types.Operator):
    """Select object by name"""
    bl_idname = "object.select"
    bl_label = "Select object"
    bl_options = {"UNDO"}

    object_name: StringProperty(
        name="object_name",
        description="object to select's name ",
    ) # type: ignore

    def execute(self, context):
        if self.object_name:
            object = bpy.data.objects[self.object_name]
            scenes_of_object = list(object.users_scene)
            if len(scenes_of_object) > 0:
                bpy.ops.object.select_all(action='DESELECT')
                bpy.context.window.scene = scenes_of_object[0]
                object.select_set(True)    
                bpy.context.view_layer.objects.active = object
        return {'FINISHED'}