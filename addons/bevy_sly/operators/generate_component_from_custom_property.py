
import bpy
from bpy.props import (StringProperty)
from ..components_meta import add_component_from_custom_property

class GenerateComponent_From_custom_property_Operator(bpy.types.Operator):
    """Generate Bevy components from custom property"""
    bl_idname = "object.generate_bevy_component_from_custom_property"
    bl_label = "Generate component from custom_property Operator"
    bl_options = {"UNDO"}

    component_name: StringProperty(
        name="component name",
        description="component to generate custom properties for",
    ) # type: ignore

    def execute(self, context):
        object = context.object

        error = False
        try:
            add_component_from_custom_property(object)
        except Exception as error:
            del object["__disable__update"] # make sure custom properties are updateable afterwards, even in the case of failure
            error = True
            self.report({'ERROR'}, "Failed to update propertyGroup values from custom property: Error:" + str(error))
        if not error:
            self.report({'INFO'}, "Sucessfully generated UI values for custom properties for selected object")
        return {'FINISHED'}
