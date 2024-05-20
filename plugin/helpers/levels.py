import os
import bpy
from pathlib import Path

from ..util import TEMPSCENE_PREFIX
from .generate_and_export import generate_and_export
from .export_gltf import (generate_gltf_export_preferences, export_gltf)
from .dynamic import is_object_dynamic, is_object_static
from .helpers_scenes import get_scenes, clear_hollow_scene, copy_hollowed_collection_into
from .blueprints import check_if_blueprint_on_disk, inject_blueprints_list_into_main_scene, remove_blueprints_list_from_main_scene


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
def get_levels_to_export(changes_per_scene, changed_export_parameters, blueprints_data, addon_prefs):
    export_gltf_extension = getattr(addon_prefs, "export_gltf_extension")
    export_levels_path_full = getattr(addon_prefs, "export_levels_path_full")

    change_detection = getattr(addon_prefs.auto_export, "change_detection")
    collection_instances_combine_mode = getattr(addon_prefs.auto_export, "collection_instances_combine_mode")

    [main_scene_names, level_scenes, library_scene_names, library_scenes] = get_scenes(addon_prefs)
 
    # determine list of main scenes to export
    # we have more relaxed rules to determine if the main scenes have changed : any change is ok, (allows easier handling of changes, render settings etc)
    main_scenes_to_export = [scene_name for scene_name in main_scene_names if not change_detection or changed_export_parameters or scene_name in changes_per_scene.keys() or changed_object_in_scene(scene_name, changes_per_scene, blueprints_data, collection_instances_combine_mode) or not check_if_blueprint_on_disk(scene_name, export_levels_path_full, export_gltf_extension) ]

    return (main_scenes_to_export)


def export_main_scene(scene, blend_file_path, addon_prefs, blueprints_data): 
    gltf_export_preferences = generate_gltf_export_preferences(addon_prefs)
    export_assets_path_full = getattr(addon_prefs,"export_assets_path_full")
    export_levels_path_full = getattr(addon_prefs,"export_levels_path_full")

    export_blueprints = getattr(addon_prefs.auto_export,"export_blueprints")
    export_separate_dynamic_and_static_objects = getattr(addon_prefs.auto_export, "export_separate_dynamic_and_static_objects")

    export_settings = { **gltf_export_preferences, 
                       'use_active_scene': True, 
                       'use_active_collection':True, 
                       'use_active_collection_with_nested':True,  
                       'use_visible': False,
                       'use_renderable': False,
                       'export_apply':True
                       }

    if export_blueprints : 
        gltf_output_path = os.path.join(export_levels_path_full, scene.name)

        #inject_blueprints_list_into_main_scene(scene, blueprints_data, addon_prefs)
        return
        if export_separate_dynamic_and_static_objects:
            #print("SPLIT STATIC AND DYNAMIC")
            # first export static objects
            generate_and_export(
                addon_prefs, 
                temp_scene_name=TEMPSCENE_PREFIX,
                export_settings=export_settings,
                gltf_output_path=gltf_output_path,
                tempScene_filler= lambda temp_collection: copy_hollowed_collection_into(scene.collection, temp_collection, blueprints_data=blueprints_data, filter=is_object_static, addon_prefs=addon_prefs),
                tempScene_cleaner= lambda temp_scene, params: clear_hollow_scene(original_root_collection=scene.collection, temp_scene=temp_scene, **params)
            )

            # then export all dynamic objects
            gltf_output_path = os.path.join(export_levels_path_full, scene.name+ "_dynamic")
            generate_and_export(
                addon_prefs, 
                temp_scene_name=TEMPSCENE_PREFIX,
                export_settings=export_settings,
                gltf_output_path=gltf_output_path,
                tempScene_filler= lambda temp_collection: copy_hollowed_collection_into(scene.collection, temp_collection, blueprints_data=blueprints_data, filter=is_object_dynamic, addon_prefs=addon_prefs),
                tempScene_cleaner= lambda temp_scene, params: clear_hollow_scene(original_root_collection=scene.collection, temp_scene=temp_scene, **params)
            )

        else:
            #print("NO SPLIT")
            generate_and_export(
                addon_prefs, 
                temp_scene_name=TEMPSCENE_PREFIX,
                export_settings=export_settings,
                gltf_output_path=gltf_output_path,
                tempScene_filler= lambda temp_collection: copy_hollowed_collection_into(scene.collection, temp_collection, blueprints_data=blueprints_data, addon_prefs=addon_prefs),
                tempScene_cleaner= lambda temp_scene, params: clear_hollow_scene(original_root_collection=scene.collection, temp_scene=temp_scene, **params)
            )

    else:
        gltf_output_path = os.path.join(export_assets_path_full, scene.name)
        print("       exporting gltf to", gltf_output_path, ".gltf/glb")
        export_gltf(gltf_output_path, export_settings)

    remove_blueprints_list_from_main_scene(scene)



