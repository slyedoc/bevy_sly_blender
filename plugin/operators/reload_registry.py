import os
import bpy
from bpy_types import (Operator)
from bpy.props import (StringProperty)

from ..components_meta import ensure_metadata_for_all_objects
from ..propGroups.prop_groups import generate_propertyGroups_for_components

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
        print("reload registry")
        context.window_manager.components_registry.load_schema()
        generate_propertyGroups_for_components()
        print("")
        print("")
        print("")
        ensure_metadata_for_all_objects()

        # now force refresh the ui
        for area in context.screen.areas: 
            for region in area.regions:
                if region.type == "UI":
                    region.tag_redraw()

        return {'FINISHED'}