# TODO: alot of stuff is collasped into this file, I will most likely split it up, but trying to get a handle on things and it makes it easyer to see what really going on

import json
import bpy
import os
import time
import uuid
import traceback

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any

from bpy.props import (BoolProperty, StringProperty, CollectionProperty, IntProperty, PointerProperty, EnumProperty, FloatProperty,FloatVectorProperty )

from .helpers.custom_scene_components import ambient_color_to_component, scene_ao_to_component, scene_bloom_to_component, scene_shadows_to_component
from .helpers.collections import set_active_collection, traverse_tree
from .helpers.dynamic import is_object_dynamic, is_object_static
from .helpers.materials import clear_materials_scene, generate_materials_scene_content
from .helpers.object_makers import make_empty

from .components_meta import add_metadata_to_components_without_metadata

from .propGroups.process_component import process_component
from .propGroups.prop_groups import update_component
from .propGroups.utils import update_calback_helper

from .util import BLUEPRINTS_PATH, CHANGE_DETECTION, EXPORT_MARKED_ASSETS, EXPORT_MATERIALS_LIBRARY, EXPORT_SCENE_SETTINGS, EXPORT_STATIC_DYNAMIC, GLTF_EXTENSION, LEVELS_PATH, MATERIALS_PATH, SETTING_NAME, TEMPSCENE_PREFIX

class SceneSelector(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty() # type: ignore
    display: bpy.props.BoolProperty() # type: ignore

class RegistryType(bpy.types.PropertyGroup):
    short_name: bpy.props.StringProperty() # type: ignore
    long_name: bpy.props.StringProperty() # type: ignore

# blueprint data
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

# blueprint class
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

@dataclass
class RegistryData:
    type_infos: Dict[str, Any]
    type_infos_missing: List[str]
    component_propertyGroups: Dict[str, Any] 
    custom_types_to_add: Dict[str, Any]
    invalid_components: List[str]
    long_names_to_propgroup_names: Dict[str, str]    

    def __init__(self):
        self.type_infos = {}
        self.type_infos_missing = []
        self.component_propertyGroups = {}
        self.custom_types_to_add = {}
        self.invalid_components = []
        self.long_names_to_propgroup_names = {}
    
# helper class to store missing bevy types information
class MissingBevyType(bpy.types.PropertyGroup):
    long_name: bpy.props.StringProperty(
        name="type",
    ) # type: ignore

# helper function to deal with timer
def toggle_watcher(self, context):
    #print("toggling watcher", self.watcher_enabled, watch_schema, self, bpy.app.timers)
    if not self.watcher_enabled:
        try:
            bpy.app.timers.unregister(watch_registry)
        except Exception as error:
            pass
    else:
        self.watcher_active = True
        bpy.app.timers.register(watch_registry)

def watch_registry():
    self = bpy.context.window_manager.bevy # type: BevySettings
    # print("watching schema file for changes")
    try:
        stamp = os.stat(self.registry_file).st_mtime
        stamp = str(stamp)
        if stamp != self.registry_timestamp and self.registry_timestamp != "":
            print("FILE CHANGED !!", stamp,  self.registry_timestamp)
            # see here for better ways : https://stackoverflow.com/questions/11114492/check-if-a-file-is-not-open-nor-being-used-by-another-process
            
            # TODO: this should be enabled i think
            #bpy.ops.object.reload_registry()
            # we need to add an additional delay as the file might not have loaded yet
            bpy.app.timers.register(lambda: bpy.ops.object.reload_registry(), first_interval=1)
        self.registry_timestamp = stamp
    except Exception as error:
        pass
    return self.watcher_poll_frequency if self.watcher_enabled else None

class BevySettings(bpy.types.PropertyGroup):   
    # save the settings to a text datablock    
    def save_settings(self, context):
        json_str = json.dumps({ 
            'mode': self.mode,
            'registry_file': self.registry_file,
            'assets_path': self.assets_path,
            'auto_export': self.auto_export,
            'main_scene_names': [scene.name for scene in self.main_scenes],
            'library_scene_names': [scene.name for scene in self.library_scenes],
        })
        # update or create the text datablock
        if SETTING_NAME in bpy.data.texts:
            bpy.data.texts[SETTING_NAME].clear()
            bpy.data.texts[SETTING_NAME].write(json_str)
        else:
            stored_settings = bpy.data.texts.new(SETTING_NAME)
            stored_settings.write(json_str)

        # update the registry in case the file has changed
        self.load_registry()

        return None       
    
    #
    # Blueprint Data
    # 
    type_data: RegistryData = RegistryData() # registry info
    data: BlueprintData = BlueprintData
    blueprints_list = [] # type: list[Blueprint]

    #
    # User Setttings
    #
    assets_path: StringProperty(
        name='Export folder',
        description='The root folder for all exports(relative to the root folder/path) Defaults to "assets" ',
        default='./assets',
        options={'HIDDEN'},
        update= save_settings
    ) # type: ignore
    registry_file: StringProperty(
        name='Schema File',
        description='The registry.json file',
        default='./assets/registry.json',
        options={'HIDDEN'},
        update= save_settings
    ) # type: ignore
    auto_export: BoolProperty(
        name='Auto Export',
        description='Automatically export to gltf on save',
        default=False,
        update= save_settings
    ) # type: ignore
    main_scenes: CollectionProperty(name="main scenes",type=SceneSelector) # type: ignore
    library_scenes: CollectionProperty(name="library scenes", type=SceneSelector ) # type: ignore
    collection_instances_combine_mode : EnumProperty(
        # TODO: go over this again
        name='Collection instances',
        items=(
           ('Split', 'Split', 'replace collection instances with an empty + blueprint, creating links to sub blueprints (Default, Recomended)'),
           # TODO: what use case is this for ?, made everything a bit more complex
           ('Embed', 'Embed', 'treat collection instances as embeded objects and do not replace them with an empty'),
           ('EmbedExternal', 'EmbedExternal', 'treat instances of external (not specifified in the current blend file) collections (aka assets etc) as embeded objects and do not replace them with empties'),
           #('Inject', 'Inject', 'inject components from sub collection instances into the curent object')
        ),
        default='Split'
    ) # type: ignore

    # 
    # UI settings
    # 
    mode: EnumProperty(
        items=(
            ('COMPONENTS', "Components", ""),
            ('BLUEPRINTS', "Blueprints", ""),
            ('ASSETS', "Assets", ""),
            ('SETTINGS', "Settings", ""),
            ('TOOLS', "Tools", ""),
        ),
        #update=update_mode
    ) # type: ignore    
    main_scenes_index: IntProperty(name = "Index for main scenes list", default = 0, update= save_settings) # type: ignore    
    library_scenes_index: IntProperty(name = "Index for library scenes list", default = 0, update= save_settings) # type: ignore    
    # list of componets to show in the ui, will be filtered by ComponentDefinitionsList
    ui_components: CollectionProperty(name="ui_components",type=RegistryType) # type: ignore

    #
    # Componet Registry
    #
    missing_type_infos: StringProperty(
        name="missing type infos",
        description="unregistered/missing type infos"
    )# type: ignore
    disable_all_object_updates: BoolProperty(name="disable_object_updates", default=False) # type: ignore
    
    ## file watcher
    watcher_enabled: BoolProperty(name="Watcher_enabled", default=True, update=toggle_watcher)# type: ignore
    watcher_active: BoolProperty(name = "Flag for watcher status", default = False)# type: ignore
    watcher_poll_frequency: IntProperty(
        name="watcher poll frequency",
        description="frequency (s) at wich to poll for changes to the registry file",
        min=1,
        max=10,
        default=1
    )# type: ignore
    registry_timestamp: StringProperty(
        name="last timestamp of schema file",
        description="",
        default=""
    )# type: ignore
    missing_types_list: CollectionProperty(name="missing types list", type=MissingBevyType)# type: ignore
    missing_types_list_index: IntProperty(name = "Index for missing types list", default = 0)# type: ignore

    #type_infos = {}
    #type_infos_missing = []
    #component_propertyGroups = {}
    #custom_types_to_add = {}
    #invalid_components = []
    propGroupIdCounter: IntProperty(
        name="propGroupIdCounter",
        description="",
        min=0,
        max=1000000000,
        default=0
    ) # type: ignore
    #long_names_to_propgroup_names = {}

    def __init__(self):
        self.type_data = RegistryData()

    @classmethod
    def register(cls):
        pass

    @classmethod
    def unregister(cls):
        pass

    @classmethod 
    def get_all_modes(cls):
        # Return a list of all possible mode values
        return [item[0] for item in cls.__annotations__['mode'].keywords['items']]

    def get_scenes(self):        
        level_scene_names= list(map(lambda scene: scene.name, self.main_scenes))
        library_scene_names = list(map(lambda scene: scene.name, self.library_scenes))
        level_scenes = list(map(lambda name: bpy.data.scenes[name], level_scene_names))
        library_scenes = list(map(lambda name: bpy.data.scenes[name], library_scene_names))        
        return [level_scene_names, level_scenes, library_scene_names, library_scenes]

    def load_settings(self):
        stored_settings = bpy.data.texts[SETTING_NAME] if SETTING_NAME in bpy.data.texts else None        
        if stored_settings != None:
            settings =  json.loads(stored_settings.as_string())        
            for prop in ['assets_path', 'registry_file', 'auto_export', 'mode']:
                if prop in settings:
                    setattr(self, prop, settings[prop])
            if "main_scene_names" in settings:
                for name in settings["main_scene_names"]:
                    added = self.main_scenes.add()
                    added.name = name
            if "library_scene_names" in settings:
                for name in settings["library_scene_names"]:
                    added = self.library_scenes.add()
                    added.name = name
        print(f"loaded settings",)
        
        # save the setting back, so its updated if need be, or default added if need be
        # this will also call load_registry
        self.save_settings(None)

    def add_blueprint(self, blueprint): 
        self.blueprints_list.append(blueprint)

    # blueprints: any collection with either
    # - an instance
    # - marked as asset
    # - with the "auto_export" flag
    # https://blender.stackexchange.com/questions/167878/how-to-get-all-collections-of-the-current-scene
    def scan_blueprints(self):
         # will update blueprints_data

        [level_names, main_scenes, library_scene_names, library_scenes] = self.get_scenes()

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

        self.data = BlueprintData(
            blueprints=blueprints,
            blueprints_per_name=blueprints_per_name,
            blueprint_names=list(blueprints_per_name.keys()),
            blueprints_from_objects=blueprints_from_objects,
            internal_blueprints=internal_blueprints,
            external_blueprints=external_blueprints,
            blueprints_per_scenes=blueprints_per_scenes,
            blueprint_instances_per_main_scene=blueprint_instances_per_main_scene,
            blueprint_instances_per_library_scene=blueprint_instances_per_library_scene,
            internal_collection_instances=internal_collection_instances,
            external_collection_instances=external_collection_instances,
            blueprint_name_from_instances=blueprint_name_from_instances
        )


    def export_level_scene(self, scene): 
        export_settings = { 
            'use_active_scene': True, 
            'use_active_collection':True, 
            'use_active_collection_with_nested':True,  
            'use_visible': False,
            'use_renderable': False,
            'export_apply':True
        }
        gltf_output_path = os.path.join(self.assets_path, LEVELS_PATH, scene.name)
        print("exporting scene", scene.name,"to", gltf_output_path + GLTF_EXTENSION)    

        blueprint_instance_names_for_scene = self.data.blueprint_instances_per_main_scene.get(scene.name, None)
        blueprint_assets_list = []
        if blueprint_instance_names_for_scene:
            for blueprint_name in blueprint_instance_names_for_scene:
                blueprint = self.data.blueprints_per_name.get(blueprint_name, None)
                if blueprint is not None: 
                    print("BLUEPRINT", blueprint)
                    blueprint_exported_path = None
                    if blueprint.local:
                        blueprint_exported_path = os.path.join(self.assets_path, BLUEPRINTS_PATH, f"{blueprint.name}{GLTF_EXTENSION}")
                    else:
                        # get the injected path of the external blueprints
                        blueprint_exported_path = blueprint.collection['export_path'] if 'export_path' in blueprint.collection else None
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

        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        # TODO: this added meta data to scene to on bevy side, works, but not using it right now


        # add to the scene
        # scene["assets"] = json.dumps(blueprint_assets_list)            
        # print("blueprint assets", blueprint_assets_list)

        # assets_list_name = f"assets_{scene.name}"
        # assets_list_data = {"blueprints": json.dumps(blueprint_assets_list), "sounds":[], "images":[]}
        # scene["assets"] = json.dumps(blueprint_assets_list)
        
        # add scene property:
        # root_collection = scene.collection
        # scene_property = None
        # for object in scene.objects:
        #     if object.name == assets_list_name:
        #         scene_property = object
        #         break
        
        # if scene_property is None:
        #     scene_property = make_empty(assets_list_name, [0,0,0], [0,0,0], [0,0,0], root_collection)

        # for key in assets_list_data.keys():
        #     scene_property[key] = assets_list_data[key]
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

        if EXPORT_STATIC_DYNAMIC:
            #print("SPLIT STATIC AND DYNAMIC")
            # first export static objects
            self.generate_and_export(
                settings=export_settings, 
                gltf_output_path=gltf_output_path,
                temp_scene_name=TEMPSCENE_PREFIX,
                tempScene_filler= lambda temp_collection: self.copy_hollowed_collection_into(scene.collection, temp_collection, filter=is_object_static),
                tempScene_cleaner= lambda temp_scene, params: self.clear_hollow_scene(temp_scene, scene.collection)
            )

            # then export all dynamic objects
            gltf_output_path = gltf_output_path + "_dynamic"
            self.generate_and_export(
                settings=export_settings, 
                gltf_output_path=gltf_output_path,
                temp_scene_name=TEMPSCENE_PREFIX,
                tempScene_filler= lambda temp_collection: self.copy_hollowed_collection_into(scene.collection, temp_collection, filter=is_object_dynamic),
                tempScene_cleaner= lambda temp_scene, params: self.clear_hollow_scene(original_root_collection=scene.collection, temp_scene=temp_scene)
            )
        else:
            #print("NO SPLIT")
            self.generate_and_export(
                export_settings, 
                gltf_output_path,
                TEMPSCENE_PREFIX,                
                tempScene_filler= lambda temp_collection: self.copy_hollowed_collection_into(scene.collection, temp_collection),
                tempScene_cleaner= lambda temp_scene, params: self.clear_hollow_scene(original_root_collection=scene.collection, temp_scene=temp_scene)
            )

        # remove blueprints list from main scene
        assets_list = None
        assets_list_name = f"assets_list_{scene.name}_components"

        for object in scene.objects:
            if object.name == assets_list_name:
                assets_list = object
        if assets_list is not None:
            bpy.data.objects.remove(assets_list, do_unlink=True)

    # clear & remove "hollow scene"
    def clear_hollow_scene(self, temp_scene, original_root_collection):

        # recursively restore original names
        def restore_original_names(collection):
            if collection.name.endswith("____bak"):
                collection.name = collection.name.replace("____bak", "")
            for object in collection.objects:
                if object.instance_type == 'COLLECTION':
                    if object.name.endswith("____bak"):
                        object.name = object.name.replace("____bak", "")
                else: 
                    if object.name.endswith("____bak"):
                        object.name = object.name.replace("____bak", "")
            for child_collection in collection.children:
                restore_original_names(child_collection)

        # remove any data we created
        temp_root_collection = temp_scene.collection 
        temp_scene_objects = [o for o in temp_root_collection.all_objects]
        for object in temp_scene_objects:
            #print("removing", object.name)
            bpy.data.objects.remove(object, do_unlink=True)

        # remove the temporary scene
        bpy.data.scenes.remove(temp_scene, do_unlink=True)
        
        # reset original names
        restore_original_names(original_root_collection)

    def export_blueprints(self, blueprints):        
        try:
            # save current active collection
            active_collection =  bpy.context.view_layer.active_layer_collection

            for blueprint in blueprints:
                print("exporting collection", blueprint.name)
                gltf_output_path = os.path.join(self.assets_path, BLUEPRINTS_PATH, blueprint.name)
                collection = bpy.data.collections[blueprint.name]
                # do the actual export
                self.generate_and_export(
                    settings={
                        'use_active_scene': True, 
                        'use_active_collection': True, 
                        'use_active_collection_with_nested':True, 
                        'export_materials': 'PLACEHOLDER', # we are using material library, so we dont need to export materials                                                        
                        'use_visible': False,                        
                        'export_apply': True, 
                    },
                    gltf_output_path=gltf_output_path,
                    temp_scene_name=TEMPSCENE_PREFIX+collection.name,                                        
                    tempScene_filler= lambda temp_collection: self.copy_hollowed_collection_into(collection, temp_collection),
                    tempScene_cleaner= lambda temp_scene, params: self.clear_hollow_scene(original_root_collection=collection, temp_scene=temp_scene)
                )

            # reset active collection to the one we save before
            bpy.context.view_layer.active_layer_collection = active_collection

        except Exception as error:
            print("failed to export collections to gltf: ", error)
            raise error
        
    def has_type_infos(self):
        return len(self.type_data.type_infos.keys()) != 0

    def load_registry(self):
        # cleanup previous data and ui data
        self.propGroupIdCounter = 0
        self.missing_types_list.clear()

        # create new registry data
        # IMPORTANT: This does not work
        #   self.type_data = RegistryData()
        # This does, python fml
        self.type_data.type_infos.clear()
        self.type_data.type_infos_missing.clear()
        self.type_data.component_propertyGroups.clear()
        self.type_data.custom_types_to_add.clear()
        self.type_data.invalid_components.clear()
        self.type_data.long_names_to_propgroup_names.clear()
        
        # load registry file if it exists
        if os.path.exists(self.registry_file):            
            try:
                with open(self.registry_file) as f:
                    data = json.load(f)
                    defs = data.get("$defs", {})
                    self.type_data.type_infos = defs                                        
            except (IOError, json.JSONDecodeError) as e:
                print(f"ERROR: An error occurred while reading the file: {e}")
                return
        else:
            print(f"WARN: registy file does not exist: {self.registry_file}")
            return

        # Generate propertyGroups for all components
        for component_name in self.type_data.type_infos:
            definition = self.type_data.type_infos[component_name]
            is_component = definition['isComponent'] if "isComponent" in definition else False
            root_property_name = component_name if is_component else None
            process_component(self, definition, update_calback_helper(definition, update_component, root_property_name), None, [])

        # if we had to add any wrapper types on the fly, process them now
        for long_name in self.type_data.custom_types_to_add:
            self.type_data.type_infos[long_name] = self.type_data.custom_types_to_add[long_name]
        self.type_data.custom_types_to_add.clear() 

        # build ui list of components, from new registry data
        self.ui_components.clear()
        exclude = ['Parent', 'Children', 'Handle', 'Cow', 'AssetId']         
        sorted_components = sorted(
            ((long_name, definition["short_name"]) for long_name, definition in self.type_data.type_infos.items()
            if definition.get("isComponent", False) and not any(definition["short_name"].startswith(ex) for ex in exclude)),
            key=lambda item: item[1]  # Sort by short_name
        )               
        for long_name, short_name in sorted_components:
            added = self.ui_components.add()
            added.long_name = long_name
            added.short_name = short_name

        # start timer
        # TODO: default start to now, right now we always trigger at start
        if not self.watcher_active and self.watcher_enabled:
            self.watcher_active = True
            bpy.app.timers.register(watch_registry)

        #// how can self.type_infos 616, then 0 everywhere else ?
        print(f"INFO: loaded {len(self.type_data.type_infos)} types from registry file: {self.registry_file}")

        # ensure metadata for allobjects
        # FIXME: feels a bit heavy duty, should only be done
        # if the components panel is active ?
        for object in bpy.data.objects:
            add_metadata_to_components_without_metadata(object)

    # TODO: move to registry data    
    # we keep a list of component propertyGroup around 
    def register_component_propertyGroup(self, name, propertyGroup):
        self.type_data.component_propertyGroups[name] = propertyGroup

    # TODO: move to registry data
    # to be able to give the user more feedback on any missin/unregistered types in their registry file
    def add_missing_typeInfo(self, long_name):
        if not long_name in self.type_data.type_infos_missing:
            self.type_data.type_infos_missing.append(long_name)            
            setattr(self, "missing_type_infos", str(self.type_data.type_infos_missing))
            item = self.missing_types_list.add()
            item.long_name = long_name

    # TODO: move to registry data
    def add_custom_type(self, long_name, type_definition):
        self.type_data.custom_types_to_add[long_name] = type_definition


    # TODO: move to registry data
    # add an invalid component to the list (long name)
    def add_invalid_component(self, component_name):
        self.type_data.invalid_components.append(component_name)

    # generate propGroup name from nesting level & shortName: each shortName + nesting is unique
    def generate_propGroup_name(self, nesting, longName):
        #print("gen propGroup name for", shortName, nesting)
        self.propGroupIdCounter += 1

        propGroupIndex = str(self.propGroupIdCounter)
        propGroupName = propGroupIndex + "_ui"

        key = str(nesting) + longName if len(nesting) > 0 else longName
        self.type_data.long_names_to_propgroup_names[key] = propGroupName
        return propGroupName
    
    def copy_hollowed_collection_into(self, source_collection, destination_collection, parent_empty=None, filter=None):                
        for object in source_collection.objects:
            if object.name.endswith("____bak"): # some objects could already have been handled, ignore them
                continue       
            if filter is not None and filter(object) is False:
                continue
            #check if a specific collection instance does not have an ovveride for combine_mode
            combine_mode = object['_combine'] if '_combine' in object else self.collection_instances_combine_mode
            parent = parent_empty
            self.duplicate_object(object, parent, combine_mode, destination_collection)
            
        # for every child-collection of the source, copy its content into a new sub-collection of the destination
        for collection in source_collection.children:
            original_name = collection.name
            collection.name = original_name + "____bak"
            collection_placeholder = make_empty(original_name, [0,0,0], [0,0,0], [1,1,1], destination_collection)

            if parent_empty is not None:
                collection_placeholder.parent = parent_empty
            self.copy_hollowed_collection_into(
                source_collection = collection, 
                destination_collection = destination_collection, 
                parent_empty = collection_placeholder, 
                filter = filter,
            )
        return {}
    
    # recursively duplicates an object and its children, replacing collection instances with empties
    def duplicate_object(self, object, parent, combine_mode, destination_collection):

        custom_properties_to_filter_out = ['_combine', 'template', 'components_meta']

        def is_component_valid_and_enabled(object, component_name):
            if "components_meta" in object or hasattr(object, "components_meta"):
                target_components_metadata = object.components_meta.components
                component_meta = next(filter(lambda component: component["long_name"] == component_name, target_components_metadata), None)
                if component_meta != None:
                    return component_meta.enabled and not component_meta.invalid
            return True
        
        def remove_unwanted_custom_properties(object):
            to_remove = []
            component_names = list(object.keys()) # to avoid 'IDPropertyGroup changed size during iteration' issues
            for component_name in component_names:
                if not is_component_valid_and_enabled(object, component_name):
                    to_remove.append(component_name)
            for cp in custom_properties_to_filter_out + to_remove:
                if cp in object:
                    del object[cp]

        # these are mostly for when using this add-on together with the bevy_components add-on
        copy = None
        internal_blueprint_names = [blueprint.name for blueprint in self.data.internal_blueprints]
        # print("COMBINE MODE", combine_mode)
        if object.instance_type == 'COLLECTION' and (combine_mode == 'Split' or (combine_mode == 'EmbedExternal' and (object.instance_collection.name in internal_blueprint_names)) ): 
            #print("creating empty for", object.name, object.instance_collection.name, internal_blueprint_names, combine_mode)
            collection_name = object.instance_collection.name
            original_name = object.name

            object.name = original_name + "____bak"
            empty_obj = make_empty(original_name, object.location, object.rotation_euler, object.scale, destination_collection)
            
            """we inject the collection/blueprint name, as a component called 'BlueprintName', but we only do this in the empty, not the original object"""
            empty_obj['BlueprintName'] = '("'+collection_name+'")'        
            empty_obj['SpawnHere'] = '()'

            # we also inject a list of all sub blueprints, so that the bevy side can preload them
            # TODO: dont think i am using this right now
            blueprint_name = collection_name
            children_per_blueprint = {}
            blueprint = self.data.blueprints_per_name.get(blueprint_name, None)
            if blueprint:
                children_per_blueprint[blueprint_name] = blueprint.nested_blueprints
            
            # TODO: come back to nested blueprints 
            #empty_obj["BlueprintPath"] = ''
            #empty_obj["BlueprintsList"] = f"({json.dumps(dict(children_per_blueprint))})"
            
            # we copy custom properties over from our original object to our empty
            for component_name, component_value in object.items():
                if component_name not in custom_properties_to_filter_out and is_component_valid_and_enabled(object, component_name): #copy only valid properties
                    empty_obj[component_name] = component_value
            copy = empty_obj
        else:
            # for objects which are NOT collection instances or when embeding
            # we create a copy of our object and its children, to leave the original one as it is
            original_name = object.name
            object.name = original_name + "____bak"
            copy = object.copy()
            copy.name = original_name

            destination_collection.objects.link(copy)

            """if object.parent == None:
                if parent_empty is not None:
                    copy.parent = parent_empty
            """
        # do this both for empty replacements & normal copies
        if parent is not None:
            copy.parent = parent
        remove_unwanted_custom_properties(copy)
        
        
        # TODO: come back to animation data
        #copy_animation_data(object, copy)

        for child in object.children:
            self.duplicate_object(child, copy, combine_mode, destination_collection)

    # IF collection_instances_combine_mode is not 'split' check for each scene if any object in changes_per_scene has an instance in the scene
    def changed_object_in_scene(self, scene_name, changes_per_scene) -> bool:
         
        # Embed / EmbedExternal
        blueprints_from_objects = self.data.blueprints_from_objects
        blueprint_instances_in_scene = self.data.blueprint_instances_per_main_scene.get(scene_name, None)

        if blueprint_instances_in_scene is not None:
            changed_objects = [object_name for change in changes_per_scene.values() for object_name in change.keys()] 
            changed_blueprints = [blueprints_from_objects[changed] for changed in changed_objects if changed in blueprints_from_objects]
            changed_blueprints_with_instances_in_scene = [blueprint for blueprint in changed_blueprints if blueprint.name in blueprint_instances_in_scene.keys()]

            changed_blueprint_instances= [object for blueprint in changed_blueprints_with_instances_in_scene for object in blueprint_instances_in_scene[blueprint.name]]
            # print("changed_blueprint_instances", changed_blueprint_instances,)

            level_needs_export = False
            for blueprint_instance in changed_blueprint_instances:
                blueprint = self.data.blueprint_name_from_instances[blueprint_instance]
                combine_mode = blueprint_instance['_combine'] if '_combine' in blueprint_instance else self.collection_instances_combine_mode
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
    def get_levels_to_export(self, changes_per_scene, changed_export_parameters) -> list[str]:

        [level_names, level_scenes, library_scene_names, library_scenes] = self.get_scenes()
    
        def check_if_blueprint_on_disk(scene_name: str) -> bool:
            gltf_output_path = os.path.join(self.assets_path, LEVELS_PATH, scene_name + GLTF_EXTENSION)
            found = os.path.exists(gltf_output_path) and os.path.isfile(gltf_output_path)
            print("level", scene_name, "found", found, "path", gltf_output_path)
            return found
    
        # determine list of main scenes to export
        # we have more relaxed rules to determine if the main scenes have changed : any change is ok, (allows easier handling of changes, render settings etc)
        main_scenes_to_export = [scene_name for scene_name in level_names if not CHANGE_DETECTION 
                                or changed_export_parameters 
                                or scene_name in changes_per_scene.keys() 
                                or self.changed_object_in_scene(scene_name, changes_per_scene) 
                                or not check_if_blueprint_on_disk(scene_name) ]

        return main_scenes_to_export


    # TODO: this should also take the split/embed mode into account: if a nested collection changes AND embed is active, its container collection should also be exported
    def get_blueprints_to_export(self, changes_per_scene, changed_export_parameters) -> list[Blueprint]:

        [main_scene_names, level_scenes, library_scene_names, library_scenes] = self.get_scenes()
        blueprints_to_export = []
        
        # if the export parameters have changed, bail out early
        # we need to re_export everything if the export parameters have been changed
        if CHANGE_DETECTION and not changed_export_parameters:
            changed_blueprints = []

            # first check if all collections have already been exported before (if this is the first time the exporter is run
            # in your current Blender session for example)       

            # check if the blueprints are already on disk
            blueprints_not_on_disk = []
            for blueprint in self.data.internal_blueprints:
                gltf_output_path = os.path.join(self.assets_path, BLUEPRINTS_PATH, blueprint.name + GLTF_EXTENSION)
                found = os.path.exists(gltf_output_path) and os.path.isfile(gltf_output_path)
                if not found:
                    blueprints_not_on_disk.append(blueprint)

            for scene in library_scenes:
                if scene.name in changes_per_scene:
                    changed_objects = list(changes_per_scene[scene.name].keys())
                    changed_blueprints = [self.data.blueprints_from_objects[changed] for changed in changed_objects if changed in self.data.blueprints_from_objects]
                    # we only care about local blueprints/collections
                    changed_local_blueprints = [blueprint for blueprint in changed_blueprints if blueprint.name in self.data.blueprints_per_name.keys() and blueprint.local]
                    # FIXME: double check this: why are we combining these two ?
                    changed_blueprints += changed_local_blueprints

        
            blueprints_to_export =  list(set(changed_blueprints + blueprints_not_on_disk))
        else:
            blueprints_to_export = self.data.internal_blueprints

        # filter out blueprints that are not marked & deal with the different combine modes
        # we check for blueprint & object specific overrides ...
        filtered_blueprints = []
        for blueprint in blueprints_to_export:
            if blueprint.marked:
                filtered_blueprints.append(blueprint)
            else:
                blueprint_instances = self.data.internal_collection_instances.get(blueprint.name, [])
                # print("INSTANCES", blueprint_instances, blueprints_data.internal_collection_instances)
                # marked blueprints that have changed are always exported, regardless of whether they are in use (have instances) or not 
                for blueprint_instance in blueprint_instances:
                    combine_mode = blueprint_instance['_combine'] if '_combine' in blueprint_instance else self.collection_instances_combine_mode
                    if combine_mode == "Split": # we only keep changed blueprints if mode is set to split for at least one instance (aka if ALL instances of a blueprint are merged, do not export ? )  
                        filtered_blueprints.append(blueprint)

            blueprints_to_export =  list(set(filtered_blueprints))

        
        # changed/all blueprints to export     
        return blueprints_to_export

    def get_all_materials(self, library_scenes): 
        used_material_names = []
        for scene in library_scenes:
            root_collection = scene.collection
            for cur_collection in traverse_tree(root_collection):
                if cur_collection.name in self.data.blueprint_names:
                    for object in cur_collection.all_objects:
                        used_material_names = used_material_names + self.get_materials(object)

        # we only want unique names
        used_material_names = list(set(used_material_names))
        return used_material_names

    # get materials per object, and injects the materialInfo component
    def get_materials(self, object):
        material_slots = object.material_slots
        used_materials_names = []
        #materials_per_object = {}
        current_project_name = Path(bpy.context.blend_data.filepath).stem

        for m in material_slots:
            material = m.material
            # print("    slot", m, "material", material)
            used_materials_names.append(material.name)
            # TODO:, also respect slots & export multiple materials if applicable ! 
            # TODO: do NOT modify objects like this !! do it in a different function
            object['MaterialInfo'] = '(name: "'+material.name+'", source: "'+current_project_name + '")' 

        return used_materials_names


    # export the scenes, blueprints, materials etc
    def export(self, changes_per_scene, changed_export_parameters):

        [level_scene_names, level_scenes, library_scene_names, library_scenes] = self.get_scenes()

        # have the export parameters (not auto export, just gltf export) have changed: if yes (for example switch from glb to gltf, compression or not, animations or not etc), we need to re-export everything
        print ("changed_export_parameters", changed_export_parameters)
        try:
            # Step 1: Figure out what to export
            # update the blueprints registry
            self.scan_blueprints()

            # we inject the blueprints export path
            for blueprint in self.data.internal_blueprints:
                blueprint.collection["export_path"] = os.path.join(self.assets_path, BLUEPRINTS_PATH, f"{blueprint.name}{GLTF_EXTENSION}")           

            for blueprint in self.data.blueprints:
                self.add_blueprint(blueprint)

            # Step 2: Create custom compoents based on the scene settings
            # TODO: Custom Scene settings, with 
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

            # Step 3: Export materials to its own glb so they can be shared            
            # since materials export adds components we need to call this before blueprints are exported        
            current_project_name = Path(bpy.context.blend_data.filepath).stem
            used_material_names = self.get_all_materials(library_scenes)

            self.generate_and_export(
                settings={ 
                    'use_active_scene': True, 
                    'use_active_collection':True, 
                    'use_active_collection_with_nested':True,  
                    'use_visible': False,
                    'use_renderable': False,
                    'export_apply':True
                },
                temp_scene_name="__materials_scene",        
                gltf_output_path=os.path.join(self.assets_path, MATERIALS_PATH, current_project_name + "_materials_library"),
                tempScene_filler= lambda temp_collection: generate_materials_scene_content(temp_collection, used_material_names),
                tempScene_cleaner= lambda temp_scene, params: clear_materials_scene(temp_scene)
            )

            # Step 4: Export blueprints and levels
            # get blueprints and levels
            blueprints_to_export = self.get_blueprints_to_export(changes_per_scene, changed_export_parameters)                     
            levels_to_export = self.get_levels_to_export(changes_per_scene, changed_export_parameters)

            # update the list of tracked exports
            exports_total = len(blueprints_to_export) + len((levels_to_export)) + 1  # +1 for the materials library
            bpy.context.window_manager.auto_export_tracker.exports_total = exports_total
            bpy.context.window_manager.auto_export_tracker.exports_count = exports_total

            print("-------------------------------")
            print("BLUEPRINTS:    local/internal:", [blueprint.name for blueprint in self.data.internal_blueprints])
            print("BLUEPRINTS:          external:", [blueprint.name for blueprint in self.data.external_blueprints])
            print("BLUEPRINTS:         per_scene:", self.data.blueprints_per_scenes)
            print("-------------------------------")
            print("BLUEPRINTS:         to export:", [blueprint.name for blueprint in blueprints_to_export])
            print("-------------------------------")
            print("LEVELS:             to export:", levels_to_export)
            print("-------------------------------")
            # backup current active scene
            old_current_scene = bpy.context.scene
            # backup current selections
            old_selections = bpy.context.selected_objects

            # first export levels
            if len(levels_to_export) > 0:
                print("export MAIN scenes")
                for scene_name in (levels_to_export):                
                    self.export_level_scene(bpy.data.scenes[scene_name])

            # now deal with blueprints/collections
            do_export_library_scene = not CHANGE_DETECTION or changed_export_parameters or len(blueprints_to_export) > 0
            if do_export_library_scene:
                print("export LIBRARY")
                self.export_blueprints(blueprints_to_export)

            # reset current scene from backup
            bpy.context.window.scene = old_current_scene

            # reset selections
            for obj in old_selections:
                obj.select_set(True)
        
            # Clear the material info from the objects        
            if EXPORT_MATERIALS_LIBRARY:
                for scene in library_scenes:
                    root_collection = scene.collection
                    for cur_collection in traverse_tree(root_collection):
                        if cur_collection.name in self.data.blueprint_names:
                            for object in cur_collection.all_objects:
                                if 'MaterialInfo' in dict(object): # FIXME: hasattr does not work ????
                                    del object["MaterialInfo"]

            else:
                for scene_name in level_scene_names:
                    self.export_level_scene(bpy.data.scenes[scene_name])

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
                        
    """ 
    generates a temporary scene, fills it with data, cleans up after itself
        * named using temp_scene_name 
        * filled using the tempScene_filler
        * written on disk to gltf_output_path, with the gltf export parameters in export_settings
        * cleaned up using tempScene_cleaner

    """
    def generate_and_export(self, settings: Dict[str, Any], gltf_output_path, temp_scene_name="__temp_scene", tempScene_filler=None, tempScene_cleaner=None):         
        # this are our default settings, can be overriden by settings
        #https://docs.blender.org/api/current/bpy.ops.export_scene.html#bpy.ops.export_scene.gltf        
        export_settings = dict(
            # export_format= 'GLB', #'GLB', 'GLTF_SEPARATE', 'GLTF_EMBEDDED'
            check_existing=False,
            use_selection=False,
            use_visible=True, # Export visible and hidden objects. See Object/Batch Export to skip.
            use_renderable=False,
            use_active_collection= False,
            use_active_collection_with_nested=False,
            use_active_scene = False,
            export_apply=False, # TODO: think i turn this on everywhere we are called

            # TODO: add animations back                         
            #export_draco_mesh_compression_enable=True,
            export_animations=False,

            export_cameras=True,
            export_extras=True, # For custom exported properties.
            export_lights=True,

            #export_texcoords=True,
            #export_normals=True,
            # here add draco settings
            #export_draco_mesh_compression_enable = False,

            #export_tangents=False,
            #export_materials
            #export_colors=True,
            #export_attributes=True,
            #use_mesh_edges
            #use_mesh_vertices
        
            
            #export_yup=True,
            #export_skins=True,
            #export_morph=False,
            #export_apply=False,
            #export_animations=False,
            #export_optimize_animation_size=False
        )

        # add custom settings to the export settings
        export_settings = {**export_settings, **settings}

        temp_scene = bpy.data.scenes.new(name=temp_scene_name)
        temp_root_collection = temp_scene.collection

        # save active scene
        original_scene = bpy.context.window.scene
        # and selected collection
        original_collection = bpy.context.view_layer.active_layer_collection
        # and mode
        original_mode = bpy.context.active_object.mode if bpy.context.active_object != None else None
        
        # we change the mode to object mode, otherwise the gltf exporter is not happy
        if original_mode != None and original_mode != 'OBJECT':
            print("setting to object mode", original_mode)
            bpy.ops.object.mode_set(mode='OBJECT')


        # we set our active scene to be this one : this is needed otherwise the stand-in empties get generated in the wrong scene
        bpy.context.window.scene = temp_scene

        area = [area for area in bpy.context.screen.areas if area.type == "VIEW_3D"][0]
        region = [region for region in area.regions if region.type == 'WINDOW'][0]
        with bpy.context.temp_override(scene=temp_scene, area=area, region=region):
            # detect scene mistmatch
            scene_mismatch = bpy.context.scene.name != bpy.context.window.scene.name
            if scene_mismatch:
                raise Exception("Context scene mismatch, aborting", bpy.context.scene.name, bpy.context.window.scene.name)
            
            set_active_collection(bpy.context.scene, temp_root_collection.name)
            # generate contents of temporary scene
            scene_filler_data = tempScene_filler(temp_root_collection)
            # export the temporary scene
            try:            
                settings = {**export_settings, "filepath": gltf_output_path }            
                print("export settings", settings)
                
                os.makedirs(os.path.dirname(gltf_output_path), exist_ok=True)
                #https://docs.blender.org/api/current/bpy.ops.export_scene.html#bpy.ops.export_scene.gltf
                bpy.ops.export_scene.gltf(**settings)


            except Exception as error:
                print("failed to export gltf !", error)
                raise error
            # restore everything
            tempScene_cleaner(temp_scene, scene_filler_data)

        # reset active scene
        bpy.context.window.scene = original_scene
        # reset active collection
        bpy.context.view_layer.active_layer_collection = original_collection
        # reset mode
        if original_mode != None:
            bpy.ops.object.mode_set( mode = original_mode )