import bpy

class BEVY_PT_MainPanel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'    
    bl_label = "Bevy"
    bl_region_type = 'UI'
    bl_category = "Bevy"
    bl_context = "objectmode"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text="Some text here...")