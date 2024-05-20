bl_info = {
    "name": "bevy_sly_blender",
    "author": "slyedoc",
    "version": (0, 1, 0),
    "blender": (4, 1, 0),
    "description": "simple tooling for the Bevy",
    "warning": "",
    "wiki_url": "https://github.com/slyedoc/bevy_sly_blender",
    "tracker_url": "https://github.com/slyedoc/bevy_sly_blender/issues/new",
    "category": "Import-Export"
}

import bpy
from bpy_types import (PropertyGroup)
from bpy.props import (StringProperty, BoolProperty, FloatProperty, FloatVectorProperty, IntProperty, IntVectorProperty, EnumProperty, PointerProperty, CollectionProperty)

from bpy.app.handlers import persistent

from .ui.main import BEVY_PT_SidePanel
from .ui.missing_types import MISSING_TYPES_UL_List

from .operators.add_component import AddComponentOperator
from .operators.clear_component_definitions_list import ClearComponentDefinitionsList
from .operators.copy_component import CopyComponentOperator
from .operators.fix_component import Fix_Component_Operator
from .operators.generate_component_from_custom_property import GenerateComponent_From_custom_property_Operator
from .operators.generic_list import GENERIC_LIST_OT_actions, Generic_LIST_OT_AddItem, Generic_LIST_OT_RemoveItem, Generic_LIST_OT_SelectItem
from .operators.generic_map_actions import GENERIC_MAP_OT_actions
from .operators.open_assets_folder_browser import OT_OpenAssetsFolderBrowser
from .operators.open_schema_file_brower import OT_OpenSchemaFileBrowser
from .operators.paste_component import PasteComponentOperator
from .operators.refresh_custom_properties import (COMPONENTS_OT_REFRESH_CUSTOM_PROPERTIES_ALL, COMPONENTS_OT_REFRESH_CUSTOM_PROPERTIES_CURRENT, COMPONENTS_OT_REFRESH_PROPGROUPS_FROM_CUSTOM_PROPERTIES_ALL, COMPONENTS_OT_REFRESH_PROPGROUPS_FROM_CUSTOM_PROPERTIES_CURRENT)
from .operators.reload_registry import ReloadRegistryOperator
from .operators.remove_component_from_all_objects import RemoveComponentFromAllObjectsOperator
from .operators.remove_component import RemoveComponentOperator
from .operators.rename_component import OT_rename_component
from .operators.select_blueprint import OT_select_blueprint
from .operators.select_component_to_replace import OT_select_component_name_to_replace
from .operators.select_object import OT_select_object
from .operators.toggle_component_visibility import Toggle_ComponentVisibility
from .operators.tooling_switch import OT_switch_bevy_tooling

# prop groups
from .settings import BevySettings
from .assets_registry import Asset, AssetsRegistry
from .blueprints_registry import BlueprintsRegistry
from .component_definitions_list import ComponentDefinitionsList
from .components_registry import ComponentsRegistry, MissingBevyType
from .rename_helper import RenameHelper
from .components_meta import (ComponentMetadata, ComponentsMeta)

classes = [
    # main
    AssetsRegistry,
    BevySettings,
    ComponentsRegistry,    
    BlueprintsRegistry,
    ComponentDefinitionsList,
    RenameHelper,
    ComponentMetadata,
    ComponentsMeta,
    MissingBevyType,

    #UI
    BEVY_PT_SidePanel,
    MISSING_TYPES_UL_List,

    # operators
    AddComponentOperator,
    ClearComponentDefinitionsList,
    CopyComponentOperator,
    Fix_Component_Operator,
    GenerateComponent_From_custom_property_Operator,
    GENERIC_LIST_OT_actions,
    Generic_LIST_OT_AddItem,
    Generic_LIST_OT_RemoveItem,
    Generic_LIST_OT_SelectItem,
    GENERIC_MAP_OT_actions,
    OT_OpenAssetsFolderBrowser,
    OT_OpenSchemaFileBrowser,
    PasteComponentOperator,
    COMPONENTS_OT_REFRESH_CUSTOM_PROPERTIES_ALL,
    COMPONENTS_OT_REFRESH_CUSTOM_PROPERTIES_CURRENT,
    COMPONENTS_OT_REFRESH_PROPGROUPS_FROM_CUSTOM_PROPERTIES_ALL,
    COMPONENTS_OT_REFRESH_PROPGROUPS_FROM_CUSTOM_PROPERTIES_CURRENT,
    ReloadRegistryOperator,
    RemoveComponentFromAllObjectsOperator,
    RemoveComponentOperator,
    OT_rename_component,
    OT_select_blueprint,
    OT_select_component_name_to_replace,
    OT_select_object,
    Toggle_ComponentVisibility,
    OT_switch_bevy_tooling,
]

@persistent
def post_update(scene, depsgraph):
    print("\n\npost_update\n\n");
    #bpy.context.window_manager.auto_export_tracker.deps_post_update_handler( scene, depsgraph)

@persistent
def post_save(scene, depsgraph):
    print("\n\npost_save\n\n");
    #bpy.context.window_manager.auto_export_tracker.save_handler( scene, depsgraph)

@persistent
def post_load(file_name):
    registry = bpy.context.window_manager.components_registry
    if registry  is not None:
        registry.load_settings()
    bevy = bpy.context.window_manager.bevy
    bevy.load_settings()

def register():
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError as e:
            pass
            #print(f"{cls.__name__} is already registered. Error: {e}")

    #assets_registory
    
    #bpy.types.Scene.user_assets = CollectionProperty(name="user assets", type=Asset)
    #bpy.types.Collection.user_assets = CollectionProperty(name="user assets", type=Asset) 
    bpy.types.Object.components_meta = PointerProperty(type=ComponentsMeta)

    bpy.types.WindowManager.bevy = PointerProperty(type=BevySettings)
    bpy.types.WindowManager.assets_registry = PointerProperty(type=AssetsRegistry)
    bpy.types.WindowManager.blueprints_registry = PointerProperty(type=BlueprintsRegistry)
    bpy.types.WindowManager.components_list = bpy.props.PointerProperty(type=ComponentDefinitionsList)    
    bpy.types.WindowManager.components_registry = PointerProperty(type=ComponentsRegistry)
    bpy.types.WindowManager.components_registry.watcher_active = False

    bpy.app.handlers.load_post.append(post_load)
    # for some reason, adding these directly to the tracker class in register() do not work reliably
    bpy.app.handlers.depsgraph_update_post.append(post_update)
    bpy.app.handlers.save_post.append(post_save)

def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError as e:            
            pass
        #    print(f"Failed to unregister {cls.__name__}")
    
    #del bpy.types.Scene.user_assets
    #del bpy.types.Collection.user_assets
    #del bpy.types.Object.components_meta
    
    del bpy.types.WindowManager.bevy
    del bpy.types.WindowManager.assets_registry
    del bpy.types.WindowManager.blueprints_registry
    del bpy.types.WindowManager.components_list
    
    components_registry = bpy.types.WindowManager.components_registry # type: ComponentsRegistry
    components_registry.watcher_active = False

    for propgroup_name in components_registry.component_propertyGroups.keys():
        try:
            delattr(ComponentMetadata, propgroup_name)
            #print("unregistered propertyGroup", propgroup_name)
        except Exception as error:
            pass
            #print("failed to remove", error, "ComponentMetadata")
        
        try:
            bpy.app.timers.unregister(watch_schema)
        except Exception as error:
            pass

        del bpy.types.WindowManager.components_registry        


    
    bpy.app.handlers.load_post.remove(post_load)
    bpy.app.handlers.depsgraph_update_post.remove(post_update)
    bpy.app.handlers.save_post.remove(post_save)

if __name__ == "__main__":
     register()

# def update_scene_lists(self, context):                
#     blenvy = self# context.window_manager.blenvy
#     blenvy.main_scene_names = [scene.name for scene in blenvy.main_scenes] # FIXME: unsure
#     blenvy.library_scene_names = [scene.name for scene in blenvy.library_scenes] # FIXME: unsure
#     upsert_settings(blenvy.settings_save_path, {"common_main_scene_names": [scene.name for scene in blenvy.main_scenes]})
#     upsert_settings(blenvy.settings_save_path, {"common_library_scene_names": [scene.name for scene in blenvy.library_scenes]})

# def update_asset_folders(self, context):
#     blenvy = context.window_manager.blenvy
#     asset_path_names = ['project_root_path', 'assets_path', 'blueprints_path', 'levels_path', 'materials_path']
#     for asset_path_name in asset_path_names:
#         upsert_settings(blenvy.settings_save_path, {asset_path_name: getattr(blenvy, asset_path_name)})

# def update_mode(self, context):
#     blenvy = self # context.window_manager.blenvy
#     upsert_settings(blenvy.settings_save_path, {"mode": blenvy.mode })