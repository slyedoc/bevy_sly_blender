import bpy
from bpy.props import (EnumProperty)

class OT_switch_bevy_tooling(bpy.types.Operator):
    """Switch bevy tooling"""
    bl_idname = "bevy.tooling_switch"
    bl_label = "Switch bevy tooling"
    bl_options = {"UNDO"}
   
    tool: EnumProperty(
            items=(
                ('COMPONENTS', "Components", "Switch to components"),
                #('BLUEPRINTS', "Blueprints", ""),
                #('ASSETS', "Assets", ""),
                ('SETTINGS', "Settings", ""),
                ('TOOLS', "Tools", ""),
                )
        ) # type: ignore

    @classmethod
    def description(cls, context, properties):
        return properties.tool

    def execute(self, context):
        context.window_manager.bevy.mode = self.tool
        return {'FINISHED'}
    