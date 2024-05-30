import bpy
from bpy.props import (StringProperty)

from .settings import BevySettings



# this one is for UI only, and its inner list contains a useable list of shortnames of components
class ComponentDefinitionsList(bpy.types.PropertyGroup):
    def filter_components(self, context):
        #print("add components to ui_list")
        bevy = bpy.context.window_manager.bevy # type: BevySettings
        items = []
        for c in bevy.ui_components:
            if self.filter in c.short_name:
                # id, name, description
                items.append((c.long_name, c.short_name, c.long_name))

        return items
    
    list : bpy.props.EnumProperty(
        name="list",
        description="list",
        # items argument required to initialize, just filled with empty values
        items = filter_components,
    ) # type: ignore
    filter: StringProperty(
        name="component filter",
        description="filter for the components list",
        options={'TEXTEDIT_UPDATE'}
    ) # type: ignore

    @classmethod
    def register(cls):
        return
        #bpy.types.WindowManager.components_list = bpy.props.PointerProperty(type=ComponentDefinitionsList)

    @classmethod
    def unregister(cls):
        return
        #del bpy.types.WindowManager.components_list

    
