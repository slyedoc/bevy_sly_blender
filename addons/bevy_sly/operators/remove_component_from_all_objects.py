import bpy
from bpy_types import Operator
from bpy.props import (StringProperty)

from ..components_meta import is_bevy_component_in_object, remove_component_from_object

class RemoveComponentFromAllObjectsOperator(Operator):
    """Remove Bevy component from all object"""
    bl_idname = "object.remove_bevy_component_all"
    bl_label = "Remove component from all objects Operator"
    bl_options = {"UNDO"}

    component_name: StringProperty(
        name="component name (long name)",
        description="component to delete",
    ) # type: ignore

    @classmethod
    def register(cls):
        bpy.types.WindowManager.components_remove_progress = bpy.props.FloatProperty(default=-1.0)

    @classmethod
    def unregister(cls):
        del bpy.types.WindowManager.components_remove_progress

    def execute(self, context):
        print("removing component ", self.component_name, "from all objects")
        total = len(bpy.data.objects)
        for index, object in enumerate(bpy.data.objects):
            if len(object.keys()) > 0:
                if object is not None and is_bevy_component_in_object(object, self.component_name): 
                    remove_component_from_object(object, self.component_name)
            
            progress = index / total
            context.window_manager.components_remove_progress = progress
            # now force refresh the ui
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        context.window_manager.components_remove_progress = -1.0

        return {'FINISHED'}