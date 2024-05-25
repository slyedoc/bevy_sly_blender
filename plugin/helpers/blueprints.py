
import os
import json
import bpy

from types import SimpleNamespace

from dataclasses import dataclass, field
from typing import List, Dict, Any

from plugin.settings import BevySettings

from ..util import BLUEPRINTS_PATH, CHANGE_DETECTION, EXPORT_MARKED_ASSETS, EXPORT_MATERIALS_LIBRARY, GLTF_EXTENSION, LEVELS_PATH, TEMPSCENE_PREFIX
from .generate_and_export import generate_and_export

from .helpers_scenes import clear_hollow_scene, copy_hollowed_collection_into
from .scenes import add_scene_property

@dataclass
class BlueprintData:
    blueprints: List[Any]
    blueprints_per_name: Dict[str, Any]
    blueprint_names: List[str]
    blueprints_from_objects: Dict[str, Any]
    internal_blueprints: List[Any]
    external_blueprints: List[Any]
    blueprints_per_scenes: Dict[str, List[str]]
    blueprint_instances_per_main_scene: Dict[str, Dict[str, List[Any]]]
    blueprint_instances_per_library_scene: Dict[str, List[Any]]
    internal_collection_instances: Dict[str, List[Any]]
    external_collection_instances: Dict[str, List[Any]]
    blueprint_name_from_instances: Dict[Any, str]

def find_blueprints_not_on_disk(blueprints, folder_path, extension):
    not_found_blueprints = []
    for blueprint in blueprints:
        gltf_output_path = os.path.join(folder_path, blueprint.name + extension)
        # print("gltf_output_path", gltf_output_path)
        found = os.path.exists(gltf_output_path) and os.path.isfile(gltf_output_path)
        if not found:
            not_found_blueprints.append(blueprint)
    return not_found_blueprints

def check_if_blueprint_on_disk(scene_name, folder_path, extension):
    gltf_output_path = os.path.join(folder_path, scene_name + extension)
    found = os.path.exists(gltf_output_path) and os.path.isfile(gltf_output_path)
    print("level", scene_name, "found", found, "path", gltf_output_path)
    return found

def inject_export_path_into_internal_blueprints(internal_blueprints, blueprints_path, gltf_extension):
    for blueprint in internal_blueprints:
        blueprint_exported_path = os.path.join(blueprints_path, f"{blueprint.name}{gltf_extension}")
        blueprint.collection["export_path"] = blueprint_exported_path

def inject_blueprints_list_into_main_scene(scene, blueprints_data, bevy: BevySettings):
    #project_root_path = getattr(addon_prefs, "project_root_path")
    #assets_path = getattr(addon_prefs,"assets_path")
    #levels_path = getattr(addon_prefs,"levels_path")
    blueprints_path = os.path.join(bevy.assets_path, BLUEPRINTS_PATH)
    levels_path = os.path.join(bevy.assets_path, LEVELS_PATH)
    
    #export_gltf_extension = getattr(addon_prefs, "export_gltf_extension")

    # print("injecting assets/blueprints data into scene")
    assets_list_name = f"assets_list_{scene.name}_components"
    assets_list_data = {}

    blueprint_instance_names_for_scene = blueprints_data.blueprint_instances_per_main_scene.get(scene.name, None)
    blueprint_assets_list = []
    if blueprint_instance_names_for_scene:
        for blueprint_name in blueprint_instance_names_for_scene:
            blueprint = blueprints_data.blueprints_per_name.get(blueprint_name, None)
            if blueprint is not None: 
                print("BLUEPRINT", blueprint)
                blueprint_exported_path = None
                if blueprint.local:
                    blueprint_exported_path = os.path.join(blueprints_path, f"{blueprint.name}{export_gltf_extension}")
                else:
                    # get the injected path of the external blueprints
                    blueprint_exported_path = blueprint.collection['Export_path'] if 'Export_path' in blueprint.collection else None
                    print("foo", dict(blueprint.collection))
                if blueprint_exported_path is not None:
                    blueprint_assets_list.append({"name": blueprint.name, "path": blueprint_exported_path, "type": "MODEL", "internal": True})
                
    assets_list_name = f"assets_{scene.name}"
    scene["assets"] = json.dumps(blueprint_assets_list)

    print("blueprint assets", blueprint_assets_list)
    """add_scene_property(scene, assets_list_name, assets_list_data)
    """

def remove_blueprints_list_from_main_scene(scene):
    assets_list = None
    assets_list_name = f"assets_list_{scene.name}_components"

    for object in scene.objects:
        if object.name == assets_list_name:
            assets_list = object
    if assets_list is not None:
        bpy.data.objects.remove(assets_list, do_unlink=True)

class Blueprint:
    def __init__(self, name):
        self.name = name
        self.local = True
        self.marked = False # If marked as asset or with auto_export flag, always export if changed
        self.scene = None # Not sure, could be usefull for tracking

        self.instances = []
        self.objects = []
        self.nested_blueprints = []

        self.collection = None # should we just sublclass ?
    
    def __repr__(self):
        return f'Name: {self.name} Local: {self.local}, Scene: {self.scene}, Instances: {self.instances},  Objects: {self.objects}, nested_blueprints: {self.nested_blueprints}'

    def __str__(self):
        return f'Name: "{self.name}", Local: {self.local}, Scene: {self.scene}, Instances: {self.instances},  Objects: {self.objects}, nested_blueprints: {self.nested_blueprints}'


# export blueprints
def export_blueprints(blueprints, blueprints_data, bevy: BevySettings):
    export_blueprints_path_full = os.path.join(bevy.assets_path, BLUEPRINTS_PATH)
    gltf_export_preferences = bevy.generate_gltf_export_preferences()
    
    try:
        # save current active collection
        active_collection =  bpy.context.view_layer.active_layer_collection

        for blueprint in blueprints:
            print("exporting collection", blueprint.name)
            gltf_output_path = os.path.join(export_blueprints_path_full, blueprint.name)
            export_settings = { **gltf_export_preferences, 'use_active_scene': True, 'use_active_collection': True, 'use_active_collection_with_nested':True}
            
            # if we are using the material library option, do not export materials, use placeholder instead
            if EXPORT_MATERIALS_LIBRARY:
                export_settings['export_materials'] = 'PLACEHOLDER'

            collection = bpy.data.collections[blueprint.name]
            # do the actual export
            generate_and_export(
                temp_scene_name=TEMPSCENE_PREFIX+collection.name,
                export_settings=export_settings,
                gltf_output_path=gltf_output_path,
                tempScene_filler= lambda temp_collection: copy_hollowed_collection_into(collection, temp_collection, blueprints_data=blueprints_data),
                tempScene_cleaner= lambda temp_scene, params: clear_hollow_scene(original_root_collection=collection, temp_scene=temp_scene)
            )

        # reset active collection to the one we save before
        bpy.context.view_layer.active_layer_collection = active_collection

    except Exception as error:
        print("failed to export collections to gltf: ", error)
        raise error


# TODO: this should also take the split/embed mode into account: if a nested collection changes AND embed is active, its container collection should also be exported
def get_blueprints_to_export(changes_per_scene, changed_export_parameters, blueprints_data, bevy: BevySettings):
    blueprints_path = os.path.join(bevy.assets_path, BLUEPRINTS_PATH)

    [main_scene_names, level_scenes, library_scene_names, library_scenes] = bevy.get_scenes()
    internal_blueprints = blueprints_data.internal_blueprints
    blueprints_to_export = internal_blueprints # just for clarity

    # print("change_detection", change_detection, "changed_export_parameters", changed_export_parameters, "changes_per_scene", changes_per_scene)
    
    # if the export parameters have changed, bail out early
    # we need to re_export everything if the export parameters have been changed
    if CHANGE_DETECTION and not changed_export_parameters:
        changed_blueprints = []

        # first check if all collections have already been exported before (if this is the first time the exporter is run
        # in your current Blender session for example)
        blueprints_not_on_disk = find_blueprints_not_on_disk(internal_blueprints, blueprints_path, GLTF_EXTENSION)

        for scene in library_scenes:
            if scene.name in changes_per_scene:
                changed_objects = list(changes_per_scene[scene.name].keys())
                changed_blueprints = [blueprints_data.blueprints_from_objects[changed] for changed in changed_objects if changed in blueprints_data.blueprints_from_objects]
                # we only care about local blueprints/collections
                changed_local_blueprints = [blueprint for blueprint in changed_blueprints if blueprint.name in blueprints_data.blueprints_per_name.keys() and blueprint.local]
                # FIXME: double check this: why are we combining these two ?
                changed_blueprints += changed_local_blueprints

       
        blueprints_to_export =  list(set(changed_blueprints + blueprints_not_on_disk))


    # filter out blueprints that are not marked & deal with the different combine modes
    # we check for blueprint & object specific overrides ...
    filtered_blueprints = []
    for blueprint in blueprints_to_export:
        if blueprint.marked:
            filtered_blueprints.append(blueprint)
        else:
            blueprint_instances = blueprints_data.internal_collection_instances.get(blueprint.name, [])
            # print("INSTANCES", blueprint_instances, blueprints_data.internal_collection_instances)
            # marked blueprints that have changed are always exported, regardless of whether they are in use (have instances) or not 
            for blueprint_instance in blueprint_instances:
                combine_mode = blueprint_instance['_combine'] if '_combine' in blueprint_instance else bevy.collection_instances_combine_mode
                if combine_mode == "Split": # we only keep changed blueprints if mode is set to split for at least one instance (aka if ALL instances of a blueprint are merged, do not export ? )  
                    filtered_blueprints.append(blueprint)

        blueprints_to_export =  list(set(filtered_blueprints))

    
    # changed/all blueprints to export     
    return (blueprints_to_export)