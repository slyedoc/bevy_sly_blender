# TODO: will break this up, but for now trying to get control over things,
# and have random panels that exists god knows where
# spawning in due to a parentid doesnt work for me

import bpy
import json
from types import SimpleNamespace

from ..ui.scene_list import SCENE_UL_Bevy, SCENES_LIST_OT_actions

from ..operators.copy_component import CopyComponentOperator
from ..operators.fix_component import Fix_Component_Operator
from ..operators.toggle_component_visibility import Toggle_ComponentVisibility
from ..operators.add_component import AddComponentOperator
from ..operators.refresh_custom_properties import COMPONENTS_OT_REFRESH_CUSTOM_PROPERTIES_ALL, COMPONENTS_OT_REFRESH_CUSTOM_PROPERTIES_CURRENT, COMPONENTS_OT_REFRESH_PROPGROUPS_FROM_CUSTOM_PROPERTIES_ALL, COMPONENTS_OT_REFRESH_PROPGROUPS_FROM_CUSTOM_PROPERTIES_CURRENT
from ..operators.remove_component_from_all_objects import RemoveComponentFromAllObjectsOperator
from ..operators.generate_component_from_custom_property import GenerateComponent_From_custom_property_Operator
from ..operators.paste_component import PasteComponentOperator
from ..operators.remove_component import RemoveComponentOperator
from ..operators.select_component_to_replace import OT_select_component_name_to_replace
from ..operators.rename_component import OT_rename_component
from ..operators.select_object import OT_select_object
from ..operators.open_schema_file_brower import OT_OpenSchemaFileBrowser
from ..operators.open_assets_folder_browser import OT_OpenAssetsFolderBrowser
from ..operators.reload_registry import ReloadRegistryOperator
from ..operators.tooling_switch import OT_switch_bevy_tooling


from ..components_meta import do_object_custom_properties_have_missing_metadata, get_bevy_components
from ..components_registry import ComponentsRegistry
from ..component_definitions_list import ComponentDefinitionsList
from ..settings import BevySettings
#from ..assets_registry import AssetsRegistry
from ..rename_helper import RenameHelper

def draw_propertyGroup( propertyGroup, layout, nesting =[], rootName=None):
    is_enum = getattr(propertyGroup, "with_enum")
    is_list = getattr(propertyGroup, "with_list") 
    is_map = getattr(propertyGroup, "with_map")
    # item in our components hierarchy can get the correct propertyGroup by STRINGS because of course, we cannot pass objects to operators...sigh

    # if it is an enum, the first field name is always the list of enum variants, the others are the variants
    field_names = propertyGroup.field_names
    #print("")
    #print("drawing", propertyGroup, nesting, "component_name", rootName)
    if is_enum:
        subrow = layout.row()
        display_name = field_names[0] if propertyGroup.tupple_or_struct == "struct" else ""
        subrow.prop(propertyGroup, field_names[0], text=display_name)
        subrow.separator()
        selection = getattr(propertyGroup, "selection")

        for fname in field_names[1:]:
            if fname == "variant_" + selection:
                subrow = layout.row()
                display_name = fname if propertyGroup.tupple_or_struct == "struct" else ""

                nestedPropertyGroup = getattr(propertyGroup, fname)
                nested = getattr(nestedPropertyGroup, "nested", False)
                #print("nestedPropertyGroup", nestedPropertyGroup, fname, nested)
                if nested:
                    draw_propertyGroup(nestedPropertyGroup, subrow.column(), nesting + [fname], rootName )
                # if an enum variant is not a propertyGroup
                break
    elif is_list:
        item_list = getattr(propertyGroup, "list")
        list_index = getattr(propertyGroup, "list_index")
        box = layout.box()
        split = box.split(factor=0.9)
        list_column, buttons_column = (split.column(),split.column())

        list_column = list_column.box()
        for index, item  in enumerate(item_list):
            row = list_column.row()
            draw_propertyGroup(item, row, nesting, rootName)
            icon = 'CHECKBOX_HLT' if list_index == index else 'CHECKBOX_DEHLT'
            op = row.operator('generic_list.select_item', icon=icon, text="")
            op.component_name = rootName
            op.property_group_path = json.dumps(nesting)
            op.selection_index = index

        #various control buttons
        buttons_column.separator()
        row = buttons_column.row()
        op = row.operator('generic_list.list_action', icon='ADD', text="")
        op.action = 'ADD'
        op.component_name = rootName
        op.property_group_path = json.dumps(nesting)

        row = buttons_column.row()
        op = row.operator('generic_list.list_action', icon='REMOVE', text="")
        op.action = 'REMOVE'
        op.component_name = rootName
        op.property_group_path = json.dumps(nesting)

        buttons_column.separator()
        row = buttons_column.row()
        op = row.operator('generic_list.list_action', icon='TRIA_UP', text="")
        op.action = 'UP'
        op.component_name = rootName
        op.property_group_path = json.dumps(nesting)

        row = buttons_column.row()
        op = row.operator('generic_list.list_action', icon='TRIA_DOWN', text="")
        op.action = 'DOWN'
        op.component_name = rootName
        op.property_group_path = json.dumps(nesting)

    elif is_map:
        root = layout.row().column()
        if hasattr(propertyGroup, "list"): # TODO: improve handling of non drawable UI
            keys_list = getattr(propertyGroup, "list")
            values_list = getattr(propertyGroup, "values_list")
            box = root.box()
            row = box.row()
            row.label(text="Add entry:")
            keys_setter = getattr(propertyGroup, "keys_setter")
            draw_propertyGroup(keys_setter, row, nesting, rootName)

            values_setter = getattr(propertyGroup, "values_setter")
            draw_propertyGroup(values_setter, row, nesting, rootName)

            op = row.operator('generic_map.map_action', icon='ADD', text="")
            op.action = 'ADD'
            op.component_name = rootName
            op.property_group_path = json.dumps(nesting)

            box = root.box()
            split = box.split(factor=0.9)
            list_column, buttons_column = (split.column(),split.column())
            list_column = list_column.box()

            for index, item  in enumerate(keys_list):
                row = list_column.row()
                draw_propertyGroup(item, row, nesting, rootName)

                value = values_list[index]
                draw_propertyGroup(value, row, nesting, rootName)

                op = row.operator('generic_map.map_action', icon='REMOVE', text="")
                op.action = 'REMOVE'
                op.component_name = rootName
                op.property_group_path = json.dumps(nesting)
                op.target_index = index

            #various control buttons
            buttons_column.separator()
            row = buttons_column.row()
        
    else: 
        for fname in field_names:
            #subrow = layout.row()
            nestedPropertyGroup = getattr(propertyGroup, fname)
            nested = getattr(nestedPropertyGroup, "nested", False)
            display_name = fname if propertyGroup.tupple_or_struct == "struct" else ""

            if nested:
                layout.separator()
                layout.separator()

                layout.label(text=display_name) #  this is the name of the field/sub field
                layout.separator()
                subrow = layout.row()
                draw_propertyGroup(nestedPropertyGroup, subrow, nesting + [fname], rootName )
            else:
                subrow = layout.row()
                subrow.prop(propertyGroup, fname, text=display_name)
                subrow.separator()

## components ui
def draw_invalid_or_unregistered(layout, components_registry: ComponentsRegistry, components_list, status, component_name, object):
    registry_has_type_infos = components_registry.has_type_infos()

    row = layout.row()

    col = row.column()
    col.label(text=component_name)

    col = row.column()
    operator = col.operator(OT_select_object.bl_idname, text=object.name)
    operator.object_name = object.name

    col = row.column()
    col.label(text=status)

    col = row.column()
    col.prop(components_list, "list", text="")

    col = row.column()
    operator = col.operator(OT_rename_component.bl_idname, text="", icon="SHADERFX") #rename
    new_name = components_registry.type_infos[components_list.list]['long_name'] if components_list.list in components_registry.type_infos else ""
    operator.original_name = component_name
    operator.target_objects = json.dumps([object.name])
    operator.new_name = new_name
    col.enabled = registry_has_type_infos and component_name != "" and component_name != new_name

    col = row.column()
    operator = col.operator(RemoveComponentOperator.bl_idname, text="", icon="X")
    operator.object_name = object.name
    operator.component_name = component_name

    col = row.column()
    col = row.column()
    operator = col.operator(OT_select_component_name_to_replace.bl_idname, text="", icon="EYEDROPPER") #text="select for rename", 
    operator.component_name = component_name


class BEVY_PT_SidePanel(bpy.types.Panel):
    bl_idname = "BEVY_PT_SidePanel"
    bl_space_type = 'VIEW_3D'    
    bl_label = "Bevy"
    bl_region_type = 'UI'
    bl_category = "Bevy"
    bl_context = "objectmode"

    def draw(self, context):
        object = context.object
        layout = self.layout
        row = layout.row()
        
        # get all the data
        bevy = context.window_manager.bevy # type: BevySettings
        #asset_registry = context.window_manager.assets_registry # type: AssetsRegistry        
        #blueprints_data = blueprints_registry.blueprints_data
        components_registry = context.window_manager.components_registry # type: ComponentsRegistry        
        components_list = context.window_manager.components_list # type: ComponentDefinitionsList
        rename_helper = context.window_manager.bevy_component_rename_helper # type: RenameHelper
        remove_components_progress = context.window_manager.components_remove_progress # type: float


        registry_has_type_infos = components_registry.has_type_infos()
        selected_object = context.selected_objects[0] if len(context.selected_objects) > 0 else None

        def mode_icon(mode):
            match mode:
                case "ASSETS":
                    return "ASSET_MANAGER"
                case "COMPONENTS":
                    return "PROPERTIES"
                case "BLUEPRINTS":
                    return "PACKAGE"
                case "SETTINGS":
                    return "SETTINGS"
                case "TOOLS":
                    return "TOOL_SETTINGS"
                case _:
                    return "ERROR"

        row = layout.row()
        # Tab switcher    
        for mode in BevySettings.get_all_modes():
            icon = mode_icon(mode)
            target = row.box() if mode == bevy.mode else row
            tool_switch_components = target.operator(OT_switch_bevy_tooling.bl_idname, text="", icon=icon)
            tool_switch_components.tool = mode
      
        # Tabs
        row = layout.row()
        match bevy.mode:
            case "ASSETS":
                # TODO: this was in the middle of changing when i forked, update it
                #layout.operator(operator="bevyassets.test")

                name = "world"
                header, panel = layout.box().panel(f"assets{name}", default_closed=False)
                header.label(text="World/Level Assets")

                # settings = {"blueprints_path": "blueprints", "export_gltf_extension": ".glb"}
                # settings = SimpleNamespace(**settings)

                #if panel:
                    #for scene in bpy.data.scenes:
                        #if scene.name != "Library": # FIXME: hack for testing
                            #get_main_scene_assets_tree(scene, blueprints_data, settings)

                            #user_assets = getattr(scene, 'user_assets', [])
                            #row = panel.row()
                            #scene_assets_panel = draw_assets(layout=row, name=scene.name, title=f"{scene.name} Assets", asset_registry=asset_registry, user_assets=user_assets, target_type="SCENE", target_name=scene.name)
        #                     """if scene.name in blueprints_data.blueprint_instances_per_main_scene:
        #                         for blueprint_name in blueprints_data.blueprint_instances_per_main_scene[scene.name].keys():
        #                             blueprint = blueprints_data.blueprints_per_name[blueprint_name]
        #                             blueprint_assets = getattr(blueprint.collection, 'user_assets', [])
        #                             if scene_assets_panel:
        #                                 row = scene_assets_panel.row()
        #                                 draw_assets(layout=row, name=blueprint.name, title=f"{blueprint.name} Assets", asset_registry=asset_registry, assets=blueprint_assets, target_type="BLUEPRINT", target_name=blueprint.name)
        # """
            case "COMPONENTS":        
                name = context.object.name if context.object != None else ''
                row.label(text="Components For "+ name)
                row = layout.row()

                if object is not None:
                    row = layout.row(align=True)
                    row.prop(components_list, "list", text="Component")
                    row.prop(components_list, "filter",text="Filter")

                    # add components
                    row = layout.row(align=True)
                    op = row.operator(AddComponentOperator.bl_idname, text="Add", icon="ADD")
                    op.component_type = components_list.list
                    row.enabled = components_list.list != ''

                    layout.separator()

                    # paste components
                    row = layout.row(align=True)
                    row.operator(PasteComponentOperator.bl_idname, text="Paste component ("+bpy.context.window_manager.copied_source_component_name+")", icon="PASTEDOWN")
                    row.enabled = registry_has_type_infos and context.window_manager.copied_source_object != ''

                    layout.separator()

                    # upgrate custom props to components
                    upgradeable_customProperties = registry_has_type_infos and do_object_custom_properties_have_missing_metadata(context.object)
                    if upgradeable_customProperties:
                        row = layout.row(align=True)
                        op = row.operator(GenerateComponent_From_custom_property_Operator.bl_idname, text="generate components from custom properties" , icon="LOOP_FORWARDS") 
                        layout.separator()


                    components_in_object = object.components_meta.components
                    #print("components_names", dict(components_bla).keys())

                    for component_name in sorted(get_bevy_components(object)) : # sorted by component name, practical
                        #print("component_name", component_name)
                        if component_name == "components_meta": 
                            continue
                        # anything withouth metadata gets skipped, we only want to see real components, not all custom props
                        component_meta =  next(filter(lambda component: component["long_name"] == component_name, components_in_object), None)
                        if component_meta == None: 
                            continue
                        
                        component_invalid = getattr(component_meta, "invalid")
                        invalid_details = getattr(component_meta, "invalid_details")
                        component_visible = getattr(component_meta, "visible")
                        single_field = False

                        # our whole row 
                        box = layout.box() 
                        row = box.row(align=True)
                        # "header"
                        row.alert = component_invalid
                        row.prop(component_meta, "enabled", text="")
                        row.label(text=component_name)

                        # we fetch the matching ui property group
                        root_propertyGroup_name =  components_registry.get_propertyGroupName_from_longName(component_name)
                        """print("root_propertyGroup_name", root_propertyGroup_name)"""
                        print("component_meta", component_meta, component_invalid)

                        if root_propertyGroup_name:
                            propertyGroup = getattr(component_meta, root_propertyGroup_name, None)
                            """print("propertyGroup", propertyGroup)"""
                            if propertyGroup:
                                # if the component has only 0 or 1 field names, display inline, otherwise change layout
                                single_field = len(propertyGroup.field_names) < 2
                                prop_group_location = box.row(align=True).column()
                                """if single_field:
                                    prop_group_location = row.column(align=True)#.split(factor=0.9)#layout.row(align=False)"""
                                
                                if component_visible:
                                    if component_invalid:
                                        error_message = invalid_details if component_invalid else "Missing component UI data, please reload registry !"
                                        prop_group_location.label(text=error_message)
                                    draw_propertyGroup(propertyGroup, prop_group_location, [root_propertyGroup_name], component_name)
                                else :
                                    row.label(text="details hidden, click on toggle to display")
                            else:
                                error_message = invalid_details if component_invalid else "Missing component UI data, please reload registry !"
                                row.label(text=error_message)

                        # "footer" with additional controls
                        if component_invalid:
                            if root_propertyGroup_name:
                                propertyGroup = getattr(component_meta, root_propertyGroup_name, None)
                                if propertyGroup:
                                    unit_struct = len(propertyGroup.field_names) == 0
                                    if unit_struct: 
                                        op = row.operator(Fix_Component_Operator.bl_idname, text="", icon="SHADERFX")
                                        op.component_name = component_name
                                        row.separator()

                        op = row.operator(RemoveComponentOperator.bl_idname, text="", icon="X")
                        op.component_name = component_name
                        row.separator()
                        
                        op = row.operator(CopyComponentOperator.bl_idname, text="", icon="COPYDOWN")
                        op.source_component_name = component_name
                        op.source_object_name = object.name
                        row.separator()
                        
                        #if not single_field:
                        toggle_icon = "TRIA_DOWN" if component_visible else "TRIA_RIGHT"
                        op = row.operator(Toggle_ComponentVisibility.bl_idname, text="", icon=toggle_icon)
                        op.component_name = component_name
                        #row.separator()

                else: 
                    layout.label(text ="Select an object to edit its components")
            case "BLUEPRINTS":        
                for blueprint in blueprints_registry.blueprints_list:

                    row.label(icon="RIGHTARROW")
                    row.label(text=blueprint.name)

                    if blueprint.local:
                        
                        select_blueprint = row.operator(operator="blueprint.select", text="", icon="RESTRICT_SELECT_OFF")
                        
                        if blueprint.collection and blueprint.collection.name:
                            select_blueprint.blueprint_collection_name = blueprint.collection.name
                        select_blueprint.blueprint_scene_name = blueprint.scene.name

                        user_assets = getattr(blueprint.collection, 'user_assets', [])
                        #draw_assets(layout=layout, name=blueprint.name, title="Assets", asset_registry=asset_registry, user_assets=user_assets, target_type="BLUEPRINT", target_name=blueprint.name)

                    else:
                        user_assets = getattr(blueprint.collection, 'user_assets', [])
                        #draw_assets(layout=layout, name=blueprint.name, title="Assets", asset_registry=asset_registry, user_assets=user_assets, target_type="BLUEPRINT", target_name=blueprint.name, editable=False)
                        row.label(text="External")

            case "SETTINGS":
                # header, panel = layout.panel("common", default_closed=False)
                # header.label(text="Common")
        
                # row = panel.row()

                row = layout.row()
                row.label(text="Assets Folder")
                col = row.column()
                col.enabled = False
                col.prop(data=bevy, property="assets_path", text="")
                folder_selector = row.operator(OT_OpenAssetsFolderBrowser.bl_idname, icon="FILE_FOLDER", text="")
                folder_selector.target_property = "assets_path"

                row = layout.row()
                row.label(text="Schema File")
                col = row.column()
                col.enabled = False                        
                col.prop(data=bevy, property="schema_file", text="")
                file_selector = row.operator(OT_OpenSchemaFileBrowser.bl_idname, icon="FILE", text="")
                #file_selector.target_property = "assets_path"

                row = layout.row()
                row.label(text="Reload Register")
                row.operator(ReloadRegistryOperator.bl_idname, text="reload registry" , icon="FILE_REFRESH")

                row = layout.row()
                row.prop(components_registry, "watcher_enabled", text="enable registry file polling")
                row.prop(components_registry, "watcher_poll_frequency", text="registry file poll frequency (s)")

                row = layout.row()
                row.label(text="Auto Export")
                row.prop(bevy, "auto_export", text="Export on save")

                # scenes selection
                if len(bevy.main_scenes) == 0 and len(bevy.library_scenes) == 0:
                    row = layout.row()
                    row.alert = True
                    row.label(text="NO library or main scenes specified! at least one main scene or library scene is required!")
                    row = layout.row()
                    row.label(text="Please select and add one using the UI below")

                rows = 2
                row = layout.row()
                row.label(text="main scenes")
                row.prop(context.window_manager, "main_scene", text='')

                row = layout.row()
                row.template_list(SCENE_UL_Bevy.bl_idname, "level scenes", bevy, "main_scenes", bevy, "main_scenes_index", rows=rows)

                col = row.column(align=True)
                sub_row = col.row()
                add_operator = sub_row.operator(SCENES_LIST_OT_actions.bl_idname, icon='ADD', text="") # type: SCENES_LIST_OT_actions
                add_operator.action = 'ADD'
                add_operator.scene_type = 'LEVEL'
                #add_operator.operator = operator
                sub_row.enabled = context.window_manager.main_scene is not None

                sub_row = col.row()
                remove_operator = sub_row.operator("scene_list.list_action", icon='REMOVE', text="")
                remove_operator.action = 'REMOVE'
                remove_operator.scene_type = 'LEVEL'
                col.separator()

                # library scenes
                row = layout.row()
                row.label(text="library scenes")
                row.prop(context.window_manager, "library_scene", text='')

                row = layout.row()
                row.template_list(SCENE_UL_Bevy.bl_idname, "library scenes", bevy, "library_scenes", bevy, "library_scenes_index", rows=rows)

                col = row.column(align=True)
                sub_row = col.row()
                add_operator = sub_row.operator(SCENES_LIST_OT_actions.bl_idname, icon='ADD', text="")
                add_operator.action = 'ADD'
                add_operator.scene_type = 'LIBRARY'
                sub_row.enabled = context.window_manager.library_scene is not None

                sub_row = col.row()
                remove_operator = sub_row.operator("scene_list.list_action", icon='REMOVE', text="")
                remove_operator.action = 'REMOVE'
                remove_operator.scene_type = 'LIBRARY'
                col.separator()
            case "TOOLS":

                layout.label(text="Missing types ")
                layout.template_list("MISSING_TYPES_UL_List", "Missing types list", components_registry, "missing_types_list", components_registry, "missing_types_list_index")

                box= row.box()
                box.label(text="Invalid/ unregistered components")

                objects_with_invalid_components = []
                invalid_component_names = []
                
                row = layout.row()
                for item in ["Component", "Object", "Status", "Target"]:
                    col = row.column()
                    col.label(text=item)

                # TODO: very inneficent
                for object in bpy.data.objects: 
                    if len(object.keys()) > 0:
                        if "components_meta" in object:
                            components_metadata = object.components_meta.components
                            comp_names = []
                            for index, component_meta in enumerate(components_metadata):
                                long_name = component_meta.long_name
                                if component_meta.invalid:
                                    draw_invalid_or_unregistered(layout, components_registry, components_list, "Invalid", long_name, object)
                                
                                    if not object.name in objects_with_invalid_components:
                                        objects_with_invalid_components.append(object.name)
                                    
                                    if not long_name in invalid_component_names:
                                        invalid_component_names.append(long_name)


                                comp_names.append(long_name) 

                            for custom_property in object.keys():
                                if custom_property != 'components_meta' and custom_property != 'bevy_components' and custom_property not in comp_names:
                                    draw_invalid_or_unregistered(layout, components_registry, components_list, "Unregistered", custom_property, object)
                                
                                    if not object.name in objects_with_invalid_components:
                                        objects_with_invalid_components.append(object.name)
                                    """if not long_name in invalid_component_names:
                                        invalid_component_names.append(custom_property)""" # FIXME
                layout.separator()
                layout.separator()            

                row = layout.row()
                col = row.column()
                col.label(text="Original")
                col = row.column()
                col.label(text="New")
                col = row.column()
                col.label(text="------")

                row = layout.row()
                col = row.column()
                box = col.box()
                box.label(text=rename_helper.original_name)

                col = row.column()
                col.prop(components_list, "list", text="")
                #row.prop(available_components, "filter",text="Filter")
            
                col = row.column()
                components_rename_progress = context.window_manager.components_rename_progress

                if components_rename_progress == -1.0:
                    operator = col.operator(OT_rename_component.bl_idname, text="apply", icon="SHADERFX")
                    operator.target_objects = json.dumps(objects_with_invalid_components)
                    new_name = components_registry.type_infos[components_list.list]['short_name'] if components_list.list in components_registry.type_infos else ""
                    operator.new_name = new_name
                    col.enabled = registry_has_type_infos and rename_helper.original_name != "" and rename_helper.original_name != new_name
                else:
                    if hasattr(layout,"progress") : # only for Blender > 4.0
                        col.progress(factor = components_rename_progress, text=f"updating {components_rename_progress * 100.0:.2f}%")

                col = row.column()
                
                if remove_components_progress == -1.0:
                    operator = row.operator(RemoveComponentFromAllObjectsOperator.bl_idname, text="", icon="X")
                    operator.component_name = rename_helper.original_name
                    col.enabled = registry_has_type_infos and rename_helper.original_name != ""
                else:
                    if hasattr(layout,"progress") : # only for Blender > 4.0
                        col.progress(factor = remove_components_progress, text=f"updating {remove_components_progress * 100.0:.2f}%")

                layout.separator()
                layout.separator()
                row = layout.row()
                box= row.box()
                box.label(text="Conversions between custom properties and components & vice-versa")

                row = layout.row()
                row.label(text="WARNING ! The following operations will overwrite your existing custom properties if they have matching types on the bevy side !")
                row.alert = True

                ##
                row = layout.row()
                custom_properties_from_components_progress_current = context.window_manager.custom_properties_from_components_progress

                if custom_properties_from_components_progress_current == -1.0:
                    row.operator(COMPONENTS_OT_REFRESH_CUSTOM_PROPERTIES_CURRENT.bl_idname, text="update custom properties of current object" , icon="LOOP_FORWARDS")
                    row.enabled = registry_has_type_infos and selected_object is not None
                else:
                    if hasattr(layout,"progress") : # only for Blender > 4.0
                        layout.progress(factor = custom_properties_from_components_progress_current, text=f"updating {custom_properties_from_components_progress_current * 100.0:.2f}%")

                layout.separator()
                row = layout.row()
                custom_properties_from_components_progress_all = context.window_manager.custom_properties_from_components_progress_all

                if custom_properties_from_components_progress_all == -1.0:
                    row.operator(COMPONENTS_OT_REFRESH_CUSTOM_PROPERTIES_ALL.bl_idname, text="update custom properties of ALL objects" , icon="LOOP_FORWARDS")
                    row.enabled = registry_has_type_infos
                else:
                    if hasattr(layout,"progress") : # only for Blender > 4.0
                        layout.progress(factor = custom_properties_from_components_progress_all, text=f"updating {custom_properties_from_components_progress_all * 100.0:.2f}%")

                ########################

                row = layout.row()
                row.label(text="WARNING ! The following operations will try to overwrite your existing ui values if they have matching types on the bevy side !")
                row.alert = True

                components_from_custom_properties_progress_current = context.window_manager.components_from_custom_properties_progress

                row = layout.row()
                if components_from_custom_properties_progress_current == -1.0:
                    row.operator(COMPONENTS_OT_REFRESH_PROPGROUPS_FROM_CUSTOM_PROPERTIES_CURRENT.bl_idname, text="update UI FROM custom properties of current object" , icon="LOOP_BACK")
                    row.enabled = registry_has_type_infos and selected_object is not None
                else:
                    if hasattr(layout,"progress") : # only for Blender > 4.0
                        layout.progress(factor = components_from_custom_properties_progress_current, text=f"updating {components_from_custom_properties_progress_current * 100.0:.2f}%")

                layout.separator()
                row = layout.row()
                components_from_custom_properties_progress_all = context.window_manager.components_from_custom_properties_progress_all

                if components_from_custom_properties_progress_all == -1.0:
                    row.operator(COMPONENTS_OT_REFRESH_PROPGROUPS_FROM_CUSTOM_PROPERTIES_ALL.bl_idname, text="update UI FROM custom properties of ALL objects" , icon="LOOP_BACK")
                    row.enabled = registry_has_type_infos
                else:
                    if hasattr(layout,"progress") : # only for Blender > 4.0
                        layout.progress(factor = components_from_custom_properties_progress_all, text=f"updating {components_from_custom_properties_progress_all * 100.0:.2f}%")
            case _:
                print(f"No handler for mode: {self.mode}")





