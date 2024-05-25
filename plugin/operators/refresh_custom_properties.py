
import bpy
from bpy_types import (Operator)

from ..components_meta import apply_customProperty_values_to_object_propertyGroups, apply_propertyGroup_values_to_object_customProperties

class COMPONENTS_OT_REFRESH_CUSTOM_PROPERTIES_ALL(Operator):
    """Apply registry to ALL objects: update the custom property values of all objects based on their definition, if any"""
    bl_idname = "object.refresh_custom_properties_all"
    bl_label = "Apply Registry to all objects"
    bl_options = {"UNDO"}

    @classmethod
    def register(cls):
        bpy.types.WindowManager.custom_properties_from_components_progress_all = bpy.props.FloatProperty(default=-1.0) #bpy.props.PointerProperty(type=RenameHelper)

    @classmethod
    def unregister(cls):
        del bpy.types.WindowManager.custom_properties_from_components_progress_all

    def execute(self, context):
        print("apply registry to all")
        #context.window_manager.components_registry.load_schema()
        total = len(bpy.data.objects)

        for index, object in enumerate(bpy.data.objects):
            apply_propertyGroup_values_to_object_customProperties(object)
            progress = index / total
            context.window_manager.custom_properties_from_components_progress_all = progress
            # now force refresh the ui
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        context.window_manager.custom_properties_from_components_progress_all = -1.0

        return {'FINISHED'}
    
class COMPONENTS_OT_REFRESH_CUSTOM_PROPERTIES_CURRENT(Operator):
    """Apply registry to CURRENT object: update the custom property values of current object based on their definition, if any"""
    bl_idname = "object.refresh_custom_properties_current"
    bl_label = "Apply Registry to current object"
    bl_options = {"UNDO"}

    @classmethod
    def register(cls):
        bpy.types.WindowManager.custom_properties_from_components_progress = bpy.props.FloatProperty(default=-1.0) #bpy.props.PointerProperty(type=RenameHelper)

    @classmethod
    def unregister(cls):
        del bpy.types.WindowManager.custom_properties_from_components_progress

    def execute(self, context):
        print("apply registry to current object")
        object = context.object
        context.window_manager.custom_properties_from_components_progress = 0.5
        # now force refresh the ui
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        apply_propertyGroup_values_to_object_customProperties(object)

        context.window_manager.custom_properties_from_components_progress = -1.0
        return {'FINISHED'}
    

class COMPONENTS_OT_REFRESH_PROPGROUPS_FROM_CUSTOM_PROPERTIES_CURRENT(Operator):
    """Update UI values from custom properties to CURRENT object"""
    bl_idname = "object.refresh_ui_from_custom_properties_current"
    bl_label = "Apply custom_properties to current object"
    bl_options = {"UNDO"}

    @classmethod
    def register(cls):
        bpy.types.WindowManager.components_from_custom_properties_progress = bpy.props.FloatProperty(default=-1.0) #bpy.props.PointerProperty(type=RenameHelper)

    @classmethod
    def unregister(cls):
        del bpy.types.WindowManager.components_from_custom_properties_progress

    def execute(self, context):
        print("apply custom properties to current object")
        object = context.object
        error = False
        try:
            apply_customProperty_values_to_object_propertyGroups(object)
            progress = 0.5
            context.window_manager.components_from_custom_properties_progress = progress
            try:
                # now force refresh the ui
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
            except:pass # ony run in ui

        except Exception as error_message:
            del object["__disable__update"] # make sure custom properties are updateable afterwards, even in the case of failure
            error = True
            self.report({'ERROR'}, "Failed to update propertyGroup values from custom property: Error:" + str(error_message))
        if not error:
            self.report({'INFO'}, "Sucessfully generated UI values for custom properties for selected object")
        context.window_manager.components_from_custom_properties_progress = -1.0

        return {'FINISHED'}
    

class COMPONENTS_OT_REFRESH_PROPGROUPS_FROM_CUSTOM_PROPERTIES_ALL(Operator):
    """Update UI values from custom properties to ALL object"""
    bl_idname = "object.refresh_ui_from_custom_properties_all"
    bl_label = "Apply custom_properties to all objects"
    bl_options = {"UNDO"}

    @classmethod
    def register(cls):
        bpy.types.WindowManager.components_from_custom_properties_progress_all = bpy.props.FloatProperty(default=-1.0) #bpy.props.PointerProperty(type=RenameHelper)

    @classmethod
    def unregister(cls):
        del bpy.types.WindowManager.components_from_custom_properties_progress_all

    def execute(self, context):
        print("apply custom properties to all object")
        bpy.context.window_manager.components_registry.disable_all_object_updates = True
        errors = []
        total = len(bpy.data.objects)

        for index, object in enumerate(bpy.data.objects):
          
            try:
                apply_customProperty_values_to_object_propertyGroups(object)
            except Exception as error:
                del object["__disable__update"] # make sure custom properties are updateable afterwards, even in the case of failure
                errors.append( "object: '" + object.name + "', error: " + str(error))

            progress = index / total
            context.window_manager.components_from_custom_properties_progress_all = progress
            # now force refresh the ui
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)



        if len(errors) > 0:
            self.report({'ERROR'}, "Failed to update propertyGroup values from custom property: Errors:" + str(errors))
        else: 
            self.report({'INFO'}, "Sucessfully generated UI values for custom properties for all objects")
        bpy.context.window_manager.components_registry.disable_all_object_updates = False
        context.window_manager.components_from_custom_properties_progress_all = -1.0
        return {'FINISHED'}