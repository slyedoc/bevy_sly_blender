import bpy
from bpy_types import Operator
from bpy.props import (StringProperty)

from ..components_meta import get_bevy_component_value_by_long_name, remove_component_from_object

class RemoveComponentOperator(Operator):
    """Remove Bevy component from object"""
    bl_idname = "object.remove_bevy_component"
    bl_label = "Remove component from object Operator"
    bl_options = {"UNDO"}

    component_name: StringProperty(
        name="component name",
        description="component to delete",
    ) # type: ignore

    object_name: StringProperty(
        name="object name",
        description="object whose component to delete",
        default=""
    ) # type: ignore

    def execute(self, context):
        if self.object_name == "":
            object = context.object
        else:
            object = bpy.data.objects[self.object_name]
        print("removing component ", self.component_name, "from object  '"+object.name+"'")

        if object is not None and 'bevy_components' in object :
            component_value = get_bevy_component_value_by_long_name(object, self.component_name)
            if component_value is not None:
                remove_component_from_object(object, self.component_name)
            else :
                self.report({"ERROR"}, "The component to remove ("+ self.component_name +") does not exist")
        else: 
            self.report({"ERROR"}, "The object to remove ("+ self.component_name +") from does not exist")
        return {'FINISHED'}