import bpy
from bpy.props import (StringProperty)

from ..components_meta import apply_propertyGroup_values_to_object_customProperties_for_component

class Fix_Component_Operator(bpy.types.Operator):
    """Attempt to fix Bevy component"""
    bl_idname = "object.fix_bevy_component"
    bl_label = "Fix component (attempts to)"
    bl_options = {"UNDO"}

    component_name: StringProperty(
        name="component name",
        description="component to fix",
    ) # type: ignore

    def execute(self, context):
        object = context.object
        error = False
        try:
            apply_propertyGroup_values_to_object_customProperties_for_component(object, self.component_name)
        except Exception as error:
            if "__disable__update" in object:
                del object["__disable__update"] # make sure custom properties are updateable afterwards, even in the case of failure
            error = True
            self.report({'ERROR'}, "Failed to fix component: Error:" + str(error))
        if not error:
            self.report({'INFO'}, "Sucessfully fixed component (please double check component & its custom property value)")
        return {'FINISHED'}