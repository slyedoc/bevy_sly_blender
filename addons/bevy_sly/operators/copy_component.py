import bpy
from bpy.props import (StringProperty)

class CopyComponentOperator(bpy.types.Operator):
    """Copy Bevy component from object"""
    bl_idname = "object.copy_bevy_component"
    bl_label = "Copy component Operator"
    bl_options = {"UNDO"}

    source_component_name: StringProperty(
        name="source component_name (long)",
        description="name of the component to copy",
    ) # type: ignore

    source_object_name: StringProperty(
        name="source object name",
        description="name of the object to copy the component from",
    ) # type: ignore

    @classmethod
    def register(cls):
        bpy.types.WindowManager.copied_source_component_name = StringProperty()
        bpy.types.WindowManager.copied_source_object = StringProperty()

    @classmethod
    def unregister(cls):
        del bpy.types.WindowManager.copied_source_component_name
        del bpy.types.WindowManager.copied_source_object
      

    def execute(self, context):
        if self.source_component_name != '' and self.source_object_name != "":
            context.window_manager.copied_source_component_name = self.source_component_name
            context.window_manager.copied_source_object = self.source_object_name
        else:
            self.report({"ERROR"}, "The source object name / component name to copy a component from have not been specified")

        return {'FINISHED'}