
import os
import json
import bpy

from types import SimpleNamespace

from plugin.settings import BevySettings

from ..util import BLUEPRINTS_PATH, CHANGE_DETECTION, EXPORT_MARKED_ASSETS, EXPORT_MATERIALS_LIBRARY, GLTF_EXTENSION, TEMPSCENE_PREFIX
from .generate_and_export import generate_and_export

from .helpers_scenes import clear_hollow_scene, copy_hollowed_collection_into, get_scenes
from .scenes import add_scene_property

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

def inject_blueprints_list_into_main_scene(scene, blueprints_data, addon_prefs):
    project_root_path = getattr(addon_prefs, "project_root_path")
    assets_path = getattr(addon_prefs,"assets_path")
    levels_path = getattr(addon_prefs,"levels_path")
    blueprints_path = getattr(addon_prefs, "blueprints_path")
    export_gltf_extension = getattr(addon_prefs, "export_gltf_extension")

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

# Scan




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


# blueprints: any collection with either
# - an instance
# - marked as asset
# - with the "auto_export" flag
# https://blender.stackexchange.com/questions/167878/how-to-get-all-collections-of-the-current-scene
def blueprints_scan(main_scenes, library_scenes):

    blueprints = {}
    blueprints_from_objects = {}
    blueprint_name_from_instances = {}
    collections = []
    
    # main scenes
    blueprint_instances_per_main_scene = {}
    internal_collection_instances = {}
    external_collection_instances = {}

    # meh
    def add_object_to_collection_instances(collection_name, object, internal=True):
        collection_category = internal_collection_instances if internal else external_collection_instances
        if not collection_name in collection_category.keys():
            #print("ADDING INSTANCE OF", collection_name, "object", object.name, "categ", collection_category)
            collection_category[collection_name] = [] #.append(collection_name)
        collection_category[collection_name].append(object)

    for scene in main_scenes:# should it only be main scenes ? what about collection instances inside other scenes ?
        for object in scene.objects:
            #print("object", object.name)
            if object.instance_type == 'COLLECTION':
                collection = object.instance_collection
                collection_name = object.instance_collection.name
                #print("  from collection:", collection_name)

                collection_from_library = False
                for library_scene in library_scenes: # should be only in library scenes
                    collection_from_library = library_scene.user_of_id(collection) > 0 # TODO: also check if it is an imported asset
                    if collection_from_library:
                        break

                add_object_to_collection_instances(collection_name=collection_name, object=object, internal = collection_from_library)
                
                # experiment with custom properties from assets stored in other blend files
                """if not collection_from_library:
                    for property_name in object.keys():
                        print("stuff", property_name)
                    for property_name in collection.keys():
                        print("OTHER", property_name)"""

                # blueprints[collection_name].instances.append(object)

                # FIXME: this only account for direct instances of blueprints, not for any nested blueprint inside a blueprint
                if scene.name not in blueprint_instances_per_main_scene.keys():
                    blueprint_instances_per_main_scene[scene.name] = {}
                if collection_name not in blueprint_instances_per_main_scene[scene.name].keys():
                    blueprint_instances_per_main_scene[scene.name][collection_name] = []
                blueprint_instances_per_main_scene[scene.name][collection_name].append(object)

                blueprint_name_from_instances[object] = collection_name
                
                """# add any indirect ones
                # FIXME: needs to be recursive, either here or above
                for nested_blueprint in blueprints[collection_name].nested_blueprints:
                    if not nested_blueprint in blueprint_instances_per_main_scene[scene.name]:
                        blueprint_instances_per_main_scene[scene.name].append(nested_blueprint)"""

    for collection in bpy.data.collections: 
        #print("collection", collection, collection.name_full, "users", collection.users)

        collection_from_library = False
        defined_in_scene = None
        for scene in library_scenes: # should be only in library scenes
            collection_from_library = scene.user_of_id(collection) > 0
            if collection_from_library:
                defined_in_scene = scene
                break
        if not collection_from_library: 
            continue

        
        if (
            'AutoExport' in collection and collection['AutoExport'] == True # get marked collections
            or EXPORT_MARKED_ASSETS and collection.asset_data is not None # or if you have marked collections as assets you can auto export them too
            or collection.name in list(internal_collection_instances.keys()) # or if the collection has an instance in one of the main scenes
            ):
            blueprint = Blueprint(collection.name)
            blueprint.local = True
            blueprint.marked = 'AutoExport' in collection and collection['AutoExport'] == True or EXPORT_MARKED_ASSETS and collection.asset_data is not None
            blueprint.objects = [object.name for object in collection.all_objects if not object.instance_type == 'COLLECTION'] # inneficient, double loop
            blueprint.nested_blueprints = [object.instance_collection.name for object in collection.all_objects if object.instance_type == 'COLLECTION'] # FIXME: not precise enough, aka "what is a blueprint"
            blueprint.collection = collection
            blueprint.instances = internal_collection_instances[collection.name] if collection.name in internal_collection_instances else []
            blueprint.scene = defined_in_scene
            blueprints[collection.name] = blueprint

            # add nested collections to internal/external_collection instances 
            # FIXME: inneficient, third loop over all_objects
            for object in collection.all_objects:
                if object.instance_type == 'COLLECTION':
                    add_object_to_collection_instances(collection_name=object.instance_collection.name, object=object, internal = blueprint.local)

            # now create reverse lookup , so you can find the collection from any of its contained objects
            for object in collection.all_objects:
                blueprints_from_objects[object.name] = blueprint#collection.name

        #
        collections.append(collection)

    # EXTERNAL COLLECTIONS: add any collection that has an instance in the main scenes, but is not present in any of the scenes (IE NON LOCAL/ EXTERNAL)
    for collection_name in external_collection_instances:
        collection = bpy.data.collections[collection_name]
        blueprint = Blueprint(collection.name)
        blueprint.local = False
        blueprint.marked = True #external ones are always marked, as they have to have been marked in their original file #'AutoExport' in collection and collection['AutoExport'] == True
        blueprint.objects = [object.name for object in collection.all_objects if not object.instance_type == 'COLLECTION'] # inneficient, double loop
        blueprint.nested_blueprints = [object.instance_collection.name for object in collection.all_objects if object.instance_type == 'COLLECTION'] # FIXME: not precise enough, aka "what is a blueprint"
        blueprint.collection = collection
        blueprint.instances = external_collection_instances[collection.name] if collection.name in external_collection_instances else []
        blueprints[collection.name] = blueprint
        #print("EXTERNAL COLLECTION", collection, dict(collection))

        # add nested collections to internal/external_collection instances 
        # FIXME: inneficient, third loop over all_objects
        """for object in collection.all_objects:
            if object.instance_type == 'COLLECTION':
                add_object_to_collection_instances(collection_name=object.instance_collection.name, object=object, internal = blueprint.local)"""

        # now create reverse lookup , so you can find the collection from any of its contained objects
        for object in collection.all_objects:
            blueprints_from_objects[object.name] = blueprint#collection.name


    # then add any nested collections at root level (so we can have a flat list, regardless of nesting)
    # TODO: do this recursively
    for blueprint_name in list(blueprints.keys()):
        parent_blueprint = blueprints[blueprint_name]

        for nested_blueprint_name in parent_blueprint.nested_blueprints:
            if not nested_blueprint_name in blueprints.keys():
                collection = bpy.data.collections[nested_blueprint_name]
                blueprint = Blueprint(collection.name)
                blueprint.local = parent_blueprint.local
                blueprint.objects = [object.name for object in collection.all_objects if not object.instance_type == 'COLLECTION'] # inneficient, double loop
                blueprint.nested_blueprints = [object.instance_collection.name for object in collection.all_objects if object.instance_type == 'COLLECTION'] # FIXME: not precise enough, aka "what is a blueprint"
                blueprint.collection = collection
                blueprint.instances = external_collection_instances[collection.name] if collection.name in external_collection_instances else []
                blueprint.scene = parent_blueprint.scene if parent_blueprint.local else None
                blueprints[collection.name] = blueprint


                # now create reverse lookup , so you can find the collection from any of its contained objects
                for object in collection.all_objects:
                    blueprints_from_objects[object.name] = blueprint#collection.name


    blueprints = dict(sorted(blueprints.items()))

    '''print("BLUEPRINTS")
    for blueprint_name in blueprints:
        print(" ", blueprints[blueprint_name])

    """print("BLUEPRINTS LOOKUP")
    print(blueprints_from_objects)"""

    print("BLUEPRINT INSTANCES PER MAIN SCENE")
    print(blueprint_instances_per_main_scene)'''


    """changes_test = {'Library': {
        'Blueprint1_mesh': bpy.data.objects['Blueprint1_mesh'], 
        'Fox_mesh': bpy.data.objects['Fox_mesh'],
        'External_blueprint2_Cylinder': bpy.data.objects['External_blueprint2_Cylinder']}
    }
    # which main scene has been impacted by this
    # does one of the main scenes contain an INSTANCE of an impacted blueprint
    for scene in main_scenes:
        changed_objects = list(changes_test["Library"].keys()) # just a hack for testing
        #bluprint_instances_in_scene = blueprint_instances_per_main_scene[scene.name]
        #print("instances per scene", bluprint_instances_in_scene, "changed_objects", changed_objects)

        changed_blueprints_with_instances_in_scene = [blueprints_from_objects[changed] for changed in changed_objects if changed in blueprints_from_objects]
        print("changed_blueprints_with_instances_in_scene", changed_blueprints_with_instances_in_scene)
        level_needs_export = len(changed_blueprints_with_instances_in_scene) > 0
        if level_needs_export:
            print("level needs export", scene.name)

    for scene in library_scenes:
        changed_objects = list(changes_test[scene.name].keys())
        changed_blueprints = [blueprints_from_objects[changed] for changed in changed_objects if changed in blueprints_from_objects]
        # we only care about local blueprints/collections
        changed_local_blueprints = [blueprint_name for blueprint_name in changed_blueprints if blueprint_name in blueprints.keys() and blueprints[blueprint_name].local]
        print("changed blueprints", changed_local_blueprints)"""

    # additional helper data structures for lookups etc
    blueprints_per_name = blueprints
    blueprints = [] # flat list
    internal_blueprints = []
    external_blueprints = []
    blueprints_per_scenes = {}

    blueprint_instances_per_library_scene = {}

    for blueprint in blueprints_per_name.values():
        blueprints.append(blueprint)
        if blueprint.local:
            internal_blueprints.append(blueprint)
            if blueprint.scene:
                if not blueprint.scene.name in blueprints_per_scenes:
                    blueprints_per_scenes[blueprint.scene.name] = []
                blueprints_per_scenes[blueprint.scene.name].append(blueprint.name) # meh

        else:
            external_blueprints.append(blueprint)

    # we also need to have blueprint instances for 

    data = {
        "blueprints": blueprints,
        "blueprints_per_name": blueprints_per_name,
        "blueprint_names": list(blueprints_per_name.keys()),
        "blueprints_from_objects": blueprints_from_objects,

        "internal_blueprints": internal_blueprints,
        "external_blueprints": external_blueprints,
        "blueprints_per_scenes": blueprints_per_scenes,

        "blueprint_instances_per_main_scene": blueprint_instances_per_main_scene,
        "blueprint_instances_per_library_scene": blueprint_instances_per_library_scene,

        # not sure about these two
        "internal_collection_instances": internal_collection_instances,
        "external_collection_instances": external_collection_instances,

        "blueprint_name_from_instances": blueprint_name_from_instances
    }

    return SimpleNamespace(**data)

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
                tempScene_filler= lambda temp_collection: copy_hollowed_collection_into(collection, temp_collection, blueprints_data=blueprints_data, addon_prefs=addon_prefs),
                tempScene_cleaner= lambda temp_scene, params: clear_hollow_scene(original_root_collection=collection, temp_scene=temp_scene, **params)
            )

        # reset active collection to the one we save before
        bpy.context.view_layer.active_layer_collection = active_collection

    except Exception as error:
        print("failed to export collections to gltf: ", error)
        raise error


# TODO: this should also take the split/embed mode into account: if a nested collection changes AND embed is active, its container collection should also be exported
def get_blueprints_to_export(changes_per_scene, changed_export_parameters, blueprints_data, bevy: BevySettings):
    blueprints_path = os.path.join(bevy.assets_path, BLUEPRINTS_PATH)

    [main_scene_names, level_scenes, library_scene_names, library_scenes] = get_scenes()
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