import ast
import json
import bpy

from bpy_types import Operator
from bpy.props import (StringProperty)

from ..settings import BevySettings

from ..components_meta import add_component_to_object

class AddComponentOperator(Operator):
    """Add Bevy component to object"""
    bl_idname = "object.add_bevy_component"
    bl_label = "Add component to object Operator"
    bl_options = {"UNDO"}

    component_type: StringProperty(
        name="component_type",
        description="component type to add",
    ) # type: ignore

    def execute(self, context):
        object = context.object
        bevy = context.window_manager.bevy # type: BevySettings        
        print("adding component ", self.component_type, "to object  '"+object.name+"'")
    
        has_component_type = self.component_type != ""

        if has_component_type and object != None:
            component_definition = bevy.type_data.type_infos[self.component_type]
            add_component_to_object(object, component_definition)

        return {'FINISHED'}
