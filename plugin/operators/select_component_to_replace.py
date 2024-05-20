import bpy
from bpy.props import (StringProperty)

class OT_select_component_name_to_replace(bpy.types.Operator):
    """Select component name to replace"""
    bl_idname = "object.select_component_name_to_replace"
    bl_label = "Select component name for bulk replace"
    bl_options = {"UNDO"}

    component_name: StringProperty(
        name="component_name",
        description="component name to replace",
    ) # type: ignore

    def execute(self, context):
        context.window_manager.bevy_component_rename_helper.original_name = self.component_name
        return {'FINISHED'}
    