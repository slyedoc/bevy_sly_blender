import bpy

class BEVY_PT_MainPanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'    
    bl_label = "Bevy2"
    bl_region_type = 'UI'
    bl_category = "Bevy2"
    bl_context = "objectmode"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        bevy = context.window_manager.bevy
        row.label(text=f"Some text here... {bevy.mode}")