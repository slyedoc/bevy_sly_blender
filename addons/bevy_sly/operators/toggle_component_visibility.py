import bpy

from bpy.props import (StringProperty)

from ..components_meta import toggle_component

class Toggle_ComponentVisibility(bpy.types.Operator):
    """Toggle Bevy component's visibility"""
    bl_idname = "object.toggle_bevy_component_visibility"
    bl_label = "Toggle component visibility"
    bl_options = {"UNDO"}

    component_name: StringProperty(
        name="component name",
        description="component to toggle",
    ) # type: ignore

    def execute(self, context):
        object = context.object
        toggle_component(object, self.component_name)
        return {'FINISHED'}
