import os
import bpy
from bpy_types import (Operator)
from bpy.props import (StringProperty)

from ..settings import BevySettings


class ReloadRegistryOperator(Operator):
    """Reloads registry (schema file) from disk, generates propertyGroups for components & ensures all objects have metadata """
    bl_idname = "object.reload_registry"
    bl_label = "Reload Registry"
    bl_options = {"UNDO"}

    component_type: StringProperty(
        name="component_type",
        description="component type to add",
    ) # type: ignore

    def execute(self, context):
        bevy = context.window_manager.bevy # type: BevySettings
        bevy.load_registry()

        # now force refresh the ui
        for area in context.screen.areas: 
            for region in area.regions:
                if region.type == "UI":
                    region.tag_redraw()

        return {'FINISHED'}