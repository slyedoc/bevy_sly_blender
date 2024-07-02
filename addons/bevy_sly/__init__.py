bl_info = {
    "name": "Bevy Sly",
    "description": "Tooling for Bevy and Blender integration",
    "author": "slyedoc",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "warning": "",
    "wiki_url": "https://github.com/slyedoc/bevy_sly_blender",
    "tracker_url": "https://github.com/slyedoc/bevy_sly_blender/issues/new",
    "category": "Import-Export"
}

import bpy
from bpy_types import (PropertyGroup)
from bpy.props import (StringProperty, BoolProperty, FloatProperty, FloatVectorProperty, IntProperty, IntVectorProperty, EnumProperty, PointerProperty, CollectionProperty)

from bpy.app.handlers import persistent

# one big ui for now while simplifying
from .ui.main import BEVY_PT_SidePanel
from .ui.missing_types import MISSING_TYPES_UL_List
from .ui.scene_list import SCENE_UL_Bevy, SCENES_LIST_OT_actions

from .operators.add_component import AddComponentOperator
from .operators.auto_export_gltf import AutoExportGLTF
from .operators.clear_component_definitions_list import ClearComponentDefinitionsList
from .operators.copy_component import CopyComponentOperator
from .operators.fix_component import Fix_Component_Operator
from .operators.generate_component_from_custom_property import GenerateComponent_From_custom_property_Operator
from .operators.generic_list import GENERIC_LIST_OT_actions, Generic_LIST_OT_AddItem, Generic_LIST_OT_RemoveItem, Generic_LIST_OT_SelectItem
from .operators.generic_map_actions import GENERIC_MAP_OT_actions
from .operators.open_assets_folder_browser import OT_OpenAssetsFolderBrowser
from .operators.open_registry_file_brower import OT_OpenRegistryFileBrowser
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
from .operators.edit_collection import EditCollectionInstance, ExitCollectionInstance, edit_collection_menu

# data
from .settings import BevySettings, SceneSelector, RegistryType, MissingBevyType, watch_registry
from .component_definitions_list import ComponentDefinitionsList
from .rename_helper import RenameHelper
from .components_meta import (ComponentMetadata, ComponentsMeta)
from .auto_export_tracker import AutoExportTracker

addon_keymaps = []

classes = [
    # helpers


    # main
    #Asset,
    #AssetsRegistry,
    SceneSelector,
    MissingBevyType,
    RegistryType,
    BevySettings,    
    ComponentDefinitionsList,
    RenameHelper,
    ComponentMetadata,
    ComponentsMeta,
    #AutoExportTracker, 

    #UI
    BEVY_PT_SidePanel,
    MISSING_TYPES_UL_List,
    SCENE_UL_Bevy,
    SCENES_LIST_OT_actions,

    # operators
    AddComponentOperator,
    AutoExportGLTF,
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
    OT_OpenRegistryFileBrowser,
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
    EditCollectionInstance,
    ExitCollectionInstance,
]

# Called when basiclly anything changes
# @persistent
def post_update(scene, depsgraph):
    print("\npost_update\n");
    #auto_export_tracker = bpy.context.window_manager.auto_export_tracker # type: AutoExportTracker
    #auto_export_tracker.deps_post_update_handler( scene, depsgraph)

@persistent
def post_save(scene, depsgraph):
    print("\npost_save\n");
#     auto_export_tracker = bpy.context.window_manager.auto_export_tracker # type: AutoExportTracker
    bevy = bpy.context.window_manager.bevy # type: BevySettings    
    bevy.save_handler( scene, depsgraph)
    # Could we just call bevy export directly without the operation that does the same thing
    #bevy.export()

@persistent
def post_load(file_name):
    #print("loaded blend file")
    bevy = bpy.context.window_manager.bevy # type: BevySettings    
    bevy.load_settings()
    

def is_scene_ok(self, scene):
    print("is_scene_ok", self.name)
    try:
        operator = bpy.context.space_data.active_operator
        return scene.name not in operator.main_scenes and scene.name not in operator.library_scenes
    except:
        return True
        

def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError as e:
            pass
            #print(f"{cls.__name__} is already registered. Error: {e}")
    
    # Instead of having each class register its down global data, I wanted to see whats out there
    # may move some back, but gaining some clarity and collasping some of the data 
    # has been worth it so far

    #assets_registory - bpy.types.Scene and bpy.types.Collection didnt exist - not working
    #bpy.types.Scene.user_assets = CollectionProperty(name="user assets", type=Asset)
    #bpy.types.Collection.user_assets = CollectionProperty(name="user assets", type=Asset) 
    bpy.types.Object.components_meta = PointerProperty(type=ComponentsMeta)                

    # our global settings everyone shares this and should be minimal
    bpy.types.WindowManager.bevy = PointerProperty(type=BevySettings)

    # TODO: just put this in settings?
    bpy.types.WindowManager.main_scene = bpy.props.PointerProperty(type=bpy.types.Scene, name="main scene", description="main_scene_picker", poll=is_scene_ok)
    bpy.types.WindowManager.library_scene = bpy.props.PointerProperty(type=bpy.types.Scene, name="library scene", description="library_scene_picker", poll=is_scene_ok)
    bpy.types.WindowManager.components_list = bpy.props.PointerProperty(type=ComponentDefinitionsList)    
    bpy.types.WindowManager.bevy_component_rename_helper = bpy.props.PointerProperty(type=RenameHelper)
    bpy.types.WindowManager.components_rename_progress = bpy.props.FloatProperty(default=-1.0) #bpy.props.PointerProperty(type=RenameHelper)
    #bpy.types.WindowManager.auto_export_tracker = PointerProperty(type=AutoExportTracker)

    bpy.app.handlers.load_post.append(post_load)    
    bpy.app.handlers.depsgraph_update_post.append(post_update)
    bpy.app.handlers.save_post.append(post_save)

    bpy.types.VIEW3D_MT_object.append(edit_collection_menu)
    bpy.types.VIEW3D_MT_object_context_menu.append(edit_collection_menu)

    wm = bpy.context.window_manager
    if wm.keyconfigs.addon:
        km = wm.keyconfigs.addon.keymaps.new(name="Object Mode", space_type="EMPTY")
        kmi = km.keymap_items.new(EditCollectionInstance.bl_idname, "C", "PRESS", ctrl=True, alt=True)
        # kmi.properties.total = 4
        addon_keymaps.append((km, kmi))

def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError as e:            
            pass
        #    print(f"Failed to unregister {cls.__name__}")
    
    #del bpy.types.Scene.user_assets
    #del bpy.types.Collection.user_assets
    del bpy.types.Object.components_meta
    
    del bpy.types.WindowManager.bevy
    del bpy.types.WindowManager.components_list
    del bpy.types.WindowManager.bevy_component_rename_helper
    del bpy.types.WindowManager.components_rename_progress
    #del bpy.types.WindowManager.auto_export_tracker

    # figure out what this was doing
    #components_registry = bpy.types.WindowManager.components_registry # type: ComponentsRegistry
    # components_registry.watcher_active = False
    # for propgroup_name in cls.component_propertyGroups.keys():
    #     try:
    #         delattr(ComponentMetadata, propgroup_name)
    #         #print("unregistered propertyGroup", propgroup_name)
    #     except Exception as error:
    #         pass
    #         #print("failed to remove", error, "ComponentMetadata")
        
    #     try:

    #     except Exception as error:
    #         pass
    try:
        bpy.app.timers.unregister(watch_registry)
    except Exception as error:
        pass
    
    #del bpy.types.WindowManager.components_registry
    
    bpy.app.handlers.load_post.remove(post_load)
    # not sure why this errors
    try:
        bpy.app.handlers.depsgraph_update_post.remove(post_update)
    except: pass
    bpy.app.handlers.save_post.remove(post_save)

    # Remove menu items
    bpy.types.VIEW3D_MT_object.remove(edit_collection_menu)
    bpy.types.VIEW3D_MT_object_context_menu.remove(edit_collection_menu)

    # Clear keymaps
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

if __name__ == "__main__":
    register()