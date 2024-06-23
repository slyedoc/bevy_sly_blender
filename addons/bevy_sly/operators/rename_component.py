import json
import bpy
from bpy_types import Operator
from bpy.props import (StringProperty)

from ..settings import BevySettings

from ..rename_helper import RenameHelper
from ..components_meta import get_bevy_components

class OT_rename_component(Operator):
    """Rename Bevy component"""
    bl_idname = "object.rename_bevy_component"
    bl_label = "rename component"
    bl_options = {"UNDO"}

    original_name: bpy.props.StringProperty(default="") # type: ignore
    new_name: StringProperty(
        name="new_name",
        description="new name of component",
    ) # type: ignore

    target_objects: bpy.props.StringProperty() # type: ignore

    @classmethod
    def register(cls):
        return

    @classmethod
    def unregister(cls):
        return

    def execute(self, context):
        settings = context.window_manager.bevy_component_rename_helper # type: RenameHelper
        bevy = context.window_manager.bevy # type: BevySettings

        original_name = settings.original_name if self.original_name == "" else self.original_name
        new_name = self.new_name

        print("renaming components: original name", original_name, "new_name", self.new_name, "targets", self.target_objects)
        target_objects = json.loads(self.target_objects)
        errors = []
        total = len(target_objects)

        if original_name != '' and new_name != '' and original_name != new_name and len(target_objects) > 0:
            for index, object_name in enumerate(target_objects):
                object = bpy.data.objects[object_name]
                if object and original_name in get_bevy_components(object) or original_name in object:
                    try:
                        # attempt conversion
                        bevy.rename_component(object=object, original_long_name=original_name, new_long_name=new_name)
                    except Exception as error:
                        if '__disable__update' in object:
                            del object["__disable__update"] # make sure custom properties are updateable afterwards, even in the case of failure
                        components_metadata = getattr(object, "components_meta", None)
                        if components_metadata:
                            components_metadata = components_metadata.components
                            component_meta =  next(filter(lambda component: component["long_name"] == new_name, components_metadata), None)
                            if component_meta:
                                component_meta.invalid = True
                                component_meta.invalid_details = "wrong custom property value, overwrite them by changing the values in the ui or change them & regenerate"

                        errors.append( "wrong custom property values to generate target component: object: '" + object.name + "', error: " + str(error))
                
                progress = index / total
                context.window_manager.components_rename_progress = progress

                try:
                    # now force refresh the ui
                    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                except: pass # this is to allow this to run in cli/headless mode

        if len(errors) > 0:
            self.report({'ERROR'}, "Failed to rename component: Errors:" + str(errors))
        else: 
            self.report({'INFO'}, "Sucessfully renamed component")

        #clear data after we are done
        self.original_name = ""
        context.window_manager.bevy_component_rename_helper.original_name = ""
        context.window_manager.components_rename_progress = -1.0

        return {'FINISHED'}