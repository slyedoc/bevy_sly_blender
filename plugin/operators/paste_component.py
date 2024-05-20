
import bpy
from bpy_types import Operator

from ..components_meta import copy_propertyGroup_values_to_another_object, get_bevy_component_value_by_long_name


class PasteComponentOperator(Operator):
    """Paste Bevy component to object"""
    bl_idname = "object.paste_bevy_component"
    bl_label = "Paste component to object Operator"
    bl_options = {"UNDO"}

    def execute(self, context):
        source_object_name = context.window_manager.copied_source_object
        source_object = bpy.data.objects.get(source_object_name, None)
        print("source object", source_object)
        if source_object == None:
            self.report({"ERROR"}, "The source object to copy a component from does not exist")
        else:
            component_name = context.window_manager.copied_source_component_name
            component_value = get_bevy_component_value_by_long_name(source_object, component_name)
            if component_value is None:
                self.report({"ERROR"}, "The source component to copy from does not exist")
            else:
                print("pasting component to object: component name:", str(component_name), "component value:" + str(component_value))
                print (context.object)
                registry = context.window_manager.components_registry
                copy_propertyGroup_values_to_another_object(source_object, context.object, component_name, registry)

        return {'FINISHED'}