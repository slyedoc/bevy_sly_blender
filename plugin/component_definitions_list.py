import bpy
from bpy.props import (StringProperty)

from plugin.components_registry import ComponentsRegistry

# this one is for UI only, and its inner list contains a useable list of shortnames of components
class ComponentDefinitionsList(bpy.types.PropertyGroup):

    # FIXME: not sure, hard coded exclude list, feels wrong
    exclude = ['Parent', 'Children']

    def add_component_to_ui_list(self, context):
        #print("add components to ui_list")
        items = []
        cr = context.window_manager.components_registry # type: ComponentsRegistry
        for long_name in cr.type_infos.keys():
            definition = cr.type_infos[long_name]
            short_name = definition["short_name"]
            is_component = definition['isComponent']  if "isComponent" in definition else False

            if self.filter in short_name and is_component:
                if not 'Handle' in short_name and not "Cow" in short_name and not "AssetId" in short_name and short_name not in self.exclude: # FIXME: hard coded, seems wrong
                    items.append((long_name, short_name, long_name))

        items.sort(key=lambda a: a[1])
        return items

    list : bpy.props.EnumProperty(
        name="list",
        description="list",
        # items argument required to initialize, just filled with empty values
        items = add_component_to_ui_list,
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

    
