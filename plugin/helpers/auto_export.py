
import os
import bpy
import traceback
import json

from ..settings import BevySettings
from ..util import BLUEPRINTS_PATH, CHANGE_DETECTION, EXPORT_MATERIALS_LIBRARY, EXPORT_SCENE_SETTINGS, EXPORT_STATIC_DYNAMIC, GLTF_EXTENSION, LEVELS_PATH, TEMPSCENE_PREFIX

from .dynamic import is_object_dynamic, is_object_static
from .generate_and_export import generate_and_export
from .helpers_scenes import clear_hollow_scene, copy_hollowed_collection_into
from .export_materials import cleanup_materials, export_materials
from .object_makers import make_empty

# IF collection_instances_combine_mode is not 'split' check for each scene if any object in changes_per_scene has an instance in the scene
def changed_object_in_scene(scene_name, changes_per_scene, blueprints_data, collection_instances_combine_mode):
    # Embed / EmbedExternal
    blueprints_from_objects = blueprints_data.blueprints_from_objects

    blueprint_instances_in_scene = blueprints_data.blueprint_instances_per_main_scene.get(scene_name, None)
    if blueprint_instances_in_scene is not None:
        changed_objects = [object_name for change in changes_per_scene.values() for object_name in change.keys()] 
        changed_blueprints = [blueprints_from_objects[changed] for changed in changed_objects if changed in blueprints_from_objects]
        changed_blueprints_with_instances_in_scene = [blueprint for blueprint in changed_blueprints if blueprint.name in blueprint_instances_in_scene.keys()]


        changed_blueprint_instances= [object for blueprint in changed_blueprints_with_instances_in_scene for object in blueprint_instances_in_scene[blueprint.name]]
        # print("changed_blueprint_instances", changed_blueprint_instances,)

        level_needs_export = False
        for blueprint_instance in changed_blueprint_instances:
            blueprint = blueprints_data.blueprint_name_from_instances[blueprint_instance]
            combine_mode = blueprint_instance['_combine'] if '_combine' in blueprint_instance else collection_instances_combine_mode
            #print("COMBINE MODE FOR OBJECT", combine_mode)
            if combine_mode == 'Embed':
                level_needs_export = True
                break
            elif combine_mode == 'EmbedExternal' and not blueprint.local:
                level_needs_export = True
                break
        # changes => list of changed objects (regardless of wether they have been changed in main scene or in lib scene)
        # wich of those objects are blueprint instances
        # we need a list of changed objects that are blueprint instances
        return level_needs_export
    return False

# this also takes the split/embed mode into account: if a collection instance changes AND embed is active, its container level/world should also be exported
def get_levels_to_export(changes_per_scene, changed_export_parameters, bevy: BevySettings):

    [main_scene_names, level_scenes, library_scene_names, library_scenes] = bevy.get_scenes()
 
    def check_if_blueprint_on_disk(scene_name: str) -> bool:
        gltf_output_path = os.path.join(bevy.assets_path, LEVELS_PATH, scene_name + GLTF_EXTENSION)
        found = os.path.exists(gltf_output_path) and os.path.isfile(gltf_output_path)
        print("level", scene_name, "found", found, "path", gltf_output_path)
        return found
 
    # determine list of main scenes to export
    # we have more relaxed rules to determine if the main scenes have changed : any change is ok, (allows easier handling of changes, render settings etc)
    main_scenes_to_export = [scene_name for scene_name in main_scene_names if not CHANGE_DETECTION 
                             or changed_export_parameters 
                             or scene_name in changes_per_scene.keys() 
                             or changed_object_in_scene(scene_name, changes_per_scene, bevy.data, bevy.collection_instances_combine_mode) 
                             or not check_if_blueprint_on_disk(scene_name) ]

    return (main_scenes_to_export)


# TODO: this should also take the split/embed mode into account: if a nested collection changes AND embed is active, its container collection should also be exported
def get_blueprints_to_export(changes_per_scene, changed_export_parameters, bevy: BevySettings):

    [main_scene_names, level_scenes, library_scene_names, library_scenes] = bevy.get_scenes()
    blueprints_to_export = []
    
    # if the export parameters have changed, bail out early
    # we need to re_export everything if the export parameters have been changed
    if CHANGE_DETECTION and not changed_export_parameters:
        changed_blueprints = []

        # first check if all collections have already been exported before (if this is the first time the exporter is run
        # in your current Blender session for example)       

        # check if the blueprints are already on disk
        blueprints_not_on_disk = []
        for blueprint in bevy.data.internal_blueprints:
            gltf_output_path = os.path.join(bevy.assets_path, BLUEPRINTS_PATH, blueprint.name + GLTF_EXTENSION)
            found = os.path.exists(gltf_output_path) and os.path.isfile(gltf_output_path)
            if not found:
                blueprints_not_on_disk.append(blueprint)

        for scene in library_scenes:
            if scene.name in changes_per_scene:
                changed_objects = list(changes_per_scene[scene.name].keys())
                changed_blueprints = [bevy.data.blueprints_from_objects[changed] for changed in changed_objects if changed in bevy.data.blueprints_from_objects]
                # we only care about local blueprints/collections
                changed_local_blueprints = [blueprint for blueprint in changed_blueprints if blueprint.name in bevy.data.blueprints_per_name.keys() and blueprint.local]
                # FIXME: double check this: why are we combining these two ?
                changed_blueprints += changed_local_blueprints

       
        blueprints_to_export =  list(set(changed_blueprints + blueprints_not_on_disk))
    else:
        blueprints_to_export = bevy.data.internal_blueprints

    # filter out blueprints that are not marked & deal with the different combine modes
    # we check for blueprint & object specific overrides ...
    filtered_blueprints = []
    for blueprint in blueprints_to_export:
        if blueprint.marked:
            filtered_blueprints.append(blueprint)
        else:
            blueprint_instances = bevy.data.internal_collection_instances.get(blueprint.name, [])
            # print("INSTANCES", blueprint_instances, blueprints_data.internal_collection_instances)
            # marked blueprints that have changed are always exported, regardless of whether they are in use (have instances) or not 
            for blueprint_instance in blueprint_instances:
                combine_mode = blueprint_instance['_combine'] if '_combine' in blueprint_instance else bevy.collection_instances_combine_mode
                if combine_mode == "Split": # we only keep changed blueprints if mode is set to split for at least one instance (aka if ALL instances of a blueprint are merged, do not export ? )  
                    filtered_blueprints.append(blueprint)

        blueprints_to_export =  list(set(filtered_blueprints))

    
    # changed/all blueprints to export     
    return (blueprints_to_export)

def ambient_color_to_component(world):
    color = None
    strength = None
    try:
        color = world.node_tree.nodes['Background'].inputs[0].default_value
        strength = world.node_tree.nodes['Background'].inputs[1].default_value
    except Exception as ex:
        print("failed to parse ambient color: Only background is supported")
   

    if color is not None and strength is not None:
        colorRgba = f"Rgba(red: {color[0]}, green: {color[1]}, blue: {color[2]}, alpha: {color[3]})"
        component = f"( color: {colorRgba}, strength: {strength})"
        return component
    return None

def scene_shadows_to_component(scene):
    cascade_size = scene.eevee.shadow_cascade_size
    component = f"(cascade_size: {cascade_size})"
    return component

def scene_bloom_to_component(scene):
    component = f"BloomSettings(intensity: {scene.eevee.bloom_intensity})"
    return component

def scene_ao_to_component(scene):
    ssao = scene.eevee.use_gtao
    component= "SSAOSettings()"
    return component


def add_scene_property(scene, property_name, property_data):
    root_collection = scene.collection
    scene_property = None
    for object in scene.objects:
        if object.name == property_name:
            scene_property = object
            break
    
    if scene_property is None:
        scene_property = make_empty(property_name, [0,0,0], [0,0,0], [0,0,0], root_collection)

    for key in property_data.keys():
        scene_property[key] = property_data[key]

def export_main_scene(scene, bevy: BevySettings): 
    gltf_export_preferences = bevy.generate_gltf_export_preferences()
    export_settings = { **gltf_export_preferences, 
                       'use_active_scene': True, 
                       'use_active_collection':True, 
                       'use_active_collection_with_nested':True,  
                       'use_visible': False,
                       'use_renderable': False,
                       'export_apply':True
                       }
    gltf_output_path = os.path.join(bevy.assets_path, LEVELS_PATH, scene.name)
    print("exporting scene", scene.name,"to", gltf_output_path + GLTF_EXTENSION)    

    blueprint_instance_names_for_scene = bevy.data.blueprint_instances_per_main_scene.get(scene.name, None)
    blueprint_assets_list = []
    if blueprint_instance_names_for_scene:
        for blueprint_name in blueprint_instance_names_for_scene:
            blueprint = bevy.data.blueprints_per_name.get(blueprint_name, None)
            if blueprint is not None: 
                print("BLUEPRINT", blueprint)
                blueprint_exported_path = None
                if blueprint.local:
                    blueprint_exported_path = os.path.join(bevy.assets_path, BLUEPRINTS_PATH, f"{blueprint.name}{GLTF_EXTENSION}")
                else:
                    # get the injected path of the external blueprints
                    blueprint_exported_path = blueprint.collection['Export_path'] if 'Export_path' in blueprint.collection else None
                    print("foo", dict(blueprint.collection))
                if blueprint_exported_path is not None:
                    blueprint_assets_list.append({"name": blueprint.name, "path": blueprint_exported_path, "type": "MODEL", "internal": True})
    
    # fetch images/textures
    # see https://blender.stackexchange.com/questions/139859/how-to-get-absolute-file-path-for-linked-texture-image
    # textures = []
    # for ob in bpy.data.objects:
    #     if ob.type == "MESH":
    #         for mat_slot in ob.material_slots:
    #             if mat_slot.material:
    #                 if mat_slot.material.node_tree:
    #                     textures.extend([x.image.filepath for x in mat_slot.material.node_tree.nodes if x.type=='TEX_IMAGE'])
    # print("textures", textures)

    # add to the scene
    scene["assets"] = json.dumps(blueprint_assets_list)            
    print("blueprint assets", blueprint_assets_list)

    assets_list_name = f"assets_{scene.name}"
    assets_list_data = {"blueprints": json.dumps(blueprint_assets_list), "sounds":[], "images":[]}
    scene["assets"] = json.dumps(blueprint_assets_list)

    add_scene_property(scene, assets_list_name, assets_list_data)

    #assets_registry = bpy.context.window_manager.assets_registry # type: AssetsRegistry
    #for blueprint in blueprint_assets_list:
    #    assets_registry.add_asset(**blueprint)

    if EXPORT_STATIC_DYNAMIC:
        #print("SPLIT STATIC AND DYNAMIC")
        # first export static objects
        generate_and_export(
            export_settings, 
            gltf_output_path,
            temp_scene_name=TEMPSCENE_PREFIX,
            tempScene_filler= lambda temp_collection: copy_hollowed_collection_into(scene.collection, temp_collection, blueprints_data=bevy.data, filter=is_object_static),
            tempScene_cleaner= lambda temp_scene, params: clear_hollow_scene(temp_scene, scene.collection)
        )

        # then export all dynamic objects
        gltf_output_path = gltf_output_path + "_dynamic"
        generate_and_export(
            export_settings, 
            gltf_output_path,
            temp_scene_name=TEMPSCENE_PREFIX,
            tempScene_filler= lambda temp_collection: copy_hollowed_collection_into(scene.collection, temp_collection, blueprints_data=bevy.data, filter=is_object_dynamic),
            tempScene_cleaner= lambda temp_scene, params: clear_hollow_scene(original_root_collection=scene.collection, temp_scene=temp_scene)
        )

    else:
        #print("NO SPLIT")
        generate_and_export(
            export_settings, 
            gltf_output_path,
            TEMPSCENE_PREFIX,                
            tempScene_filler= lambda temp_collection: copy_hollowed_collection_into(scene.collection, temp_collection, blueprints_data=bevy.data),
            tempScene_cleaner= lambda temp_scene, params: clear_hollow_scene(original_root_collection=scene.collection, temp_scene=temp_scene)
        )

    # remove blueprints list from main scene
    assets_list = None
    assets_list_name = f"assets_list_{scene.name}_components"

    for object in scene.objects:
        if object.name == assets_list_name:
            assets_list = object
    if assets_list is not None:
        bpy.data.objects.remove(assets_list, do_unlink=True)


"""this is the main 'central' function for all auto export """
def auto_export(changes_per_scene, changed_export_parameters, bevy: BevySettings):

    [level_scene_names, level_scenes, library_scene_names, library_scenes] = bevy.get_scenes()

    # have the export parameters (not auto export, just gltf export) have changed: if yes (for example switch from glb to gltf, compression or not, animations or not etc), we need to re-export everything
    print ("changed_export_parameters", changed_export_parameters)
    try:
        # update the blueprints registry
        bevy.scan_blueprints()

        # we inject the blueprints export path
        for blueprint in bevy.data.internal_blueprints:
            blueprint.collection["export_path"] = os.path.join(bevy.assets_path, BLUEPRINTS_PATH, f"{blueprint.name}{GLTF_EXTENSION}")           

        for blueprint in bevy.data.blueprints:
            bevy.add_blueprint(blueprint)

        # TODO: IMPORTANT: this is where custom components are injected        
        if EXPORT_SCENE_SETTINGS:
            for scene in level_scenes:
                lighting_components_name = f"lighting_components_{scene.name}"
                lighting_components = bpy.data.objects.get(lighting_components_name, None)
                if not lighting_components:
                    root_collection = scene.collection
                    lighting_components = make_empty('lighting_components_'+scene.name, [0,0,0], [0,0,0], [0,0,0], root_collection)

                if scene.world is not None:
                    lighting_components['BlenderBackgroundShader'] = ambient_color_to_component(scene.world)
                lighting_components['BlenderShadowSettings'] = scene_shadows_to_component(scene)

                if scene.eevee.use_bloom:
                    lighting_components['BloomSettings'] = scene_bloom_to_component(scene)
                elif 'BloomSettings' in lighting_components:
                    del lighting_components['BloomSettings']

                if scene.eevee.use_gtao: 
                    lighting_components['SSAOSettings'] = scene_ao_to_component(scene)
                elif 'SSAOSettings' in lighting_components:
                    del lighting_components['SSAOSettings']
                    
                #inject/ update light shadow information
                for light in bpy.data.lights:
                    enabled = 'true' if light.use_shadow else 'false'
                    light['BlenderLightShadows'] = f"(enabled: {enabled}, buffer_bias: {light.shadow_buffer_bias})"

        # export blueprints

        (blueprints_to_export) = get_blueprints_to_export(changes_per_scene, changed_export_parameters, bevy)                     
        (main_scenes_to_export) = get_levels_to_export(changes_per_scene, changed_export_parameters, bevy)

        # since materials export adds components we need to call this before blueprints are exported
        # export materials & inject materials components into relevant objects
        if EXPORT_MATERIALS_LIBRARY:
            export_materials(bevy.data.blueprint_names, library_scenes, bevy)

        # update the list of tracked exports
        exports_total = len(blueprints_to_export) + len(main_scenes_to_export) + (1 if EXPORT_MATERIALS_LIBRARY else 0)
        bpy.context.window_manager.auto_export_tracker.exports_total = exports_total
        bpy.context.window_manager.auto_export_tracker.exports_count = exports_total

        print("-------------------------------")
        #print("collections:               all:", collections)
        #print("collections: not found on disk:", collections_not_on_disk)
        print("BLUEPRINTS:    local/internal:", [blueprint.name for blueprint in bevy.data.internal_blueprints])
        print("BLUEPRINTS:          external:", [blueprint.name for blueprint in bevy.data.external_blueprints])
        print("BLUEPRINTS:         per_scene:", bevy.data.blueprints_per_scenes)
        print("-------------------------------")
        print("BLUEPRINTS:          to export:", [blueprint.name for blueprint in blueprints_to_export])
        print("-------------------------------")
        print("MAIN SCENES:         to export:", main_scenes_to_export)
        print("-------------------------------")
        # backup current active scene
        old_current_scene = bpy.context.scene
        # backup current selections
        old_selections = bpy.context.selected_objects

        # first export any main/level/world scenes
        if len(main_scenes_to_export) > 0:
            print("export MAIN scenes")
            for scene_name in main_scenes_to_export:
                export_main_scene(bpy.data.scenes[scene_name], bevy)

        # now deal with blueprints/collections
        do_export_library_scene = not CHANGE_DETECTION or changed_export_parameters or len(blueprints_to_export) > 0
        if do_export_library_scene:
            print("export LIBRARY")
            bevy.export_blueprints(blueprints_to_export)

        # reset current scene from backup
        bpy.context.window.scene = old_current_scene

        # reset selections
        for obj in old_selections:
            obj.select_set(True)
        if EXPORT_MATERIALS_LIBRARY:
            cleanup_materials(bevy.data.blueprint_names, library_scenes)

        else:
            for scene_name in level_scene_names:
                export_main_scene(bpy.data.scenes[scene_name], bevy)

    except Exception as error:
        print(traceback.format_exc())

        def error_message(self, context):
            self.layout.label(text="Failure during auto_export: Error: "+ str(error))

        bpy.context.window_manager.popup_menu(error_message, title="Error", icon='ERROR')

    finally:
        # FIXME: error handling ? also redundant
        if EXPORT_SCENE_SETTINGS:
            # TODO: IMPORTANT: this where those custom components are removed
                for scene in level_scenes:
                    lighting_components_name = f"lighting_components_{scene.name}"
                    lighting_components = bpy.data.objects.get(lighting_components_name, None)
                    if lighting_components:
                        bpy.data.objects.remove(lighting_components, do_unlink=True)
                        

