# TODO: alot of stuff is collasped into this file, I will most likely split it up, but trying to get a handle on things and it makes it easyer to see what really going on

import json
import bpy
import os
import time
import uuid
import traceback
import re

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any
from bpy_types import PropertyGroup
from bpy.props import (BoolProperty, StringProperty, CollectionProperty, IntProperty, PointerProperty, EnumProperty, FloatProperty,FloatVectorProperty )

from .helpers.custom_scene_components import add_scene_settings
from .helpers.collections import recurLayerCollection, traverse_tree
from .helpers.dynamic import is_object_dynamic, is_object_static
from .helpers.object_makers import make_cube, make_empty
from .components_meta import ComponentMetadata,  cleanup_invalid_metadata, get_bevy_component_value_by_long_name, get_bevy_components, remove_component_from_object, upsert_bevy_component
from .prop_groups import is_def_value_type, parse_struct_string, parse_tuplestruct_string, type_mappings, conversion_tables

from .util import BLENDER_PROPERTY_MAPPING, BLUEPRINTS_PATH, CHANGE_DETECTION, EXPORT_MARKED_ASSETS,  EXPORT_SCENE_SETTINGS, EXPORT_STATIC_DYNAMIC, GLTF_EXTENSION, LEVELS_PATH, MATERIALS_PATH, NAME_BACKUP_SUFFIX, SETTING_NAME, TEMPSCENE_PREFIX, VALUE_TYPES_DEFAULTS
from collections import  defaultdict

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
class TypeInfo:
    isComponent: bool
    isResource: bool
    items: Any #{
        #"type": {
          #"$ref": "#/$defs/glam::Quat"
        #}
      #},
    long_name: str # "alloc::vec::Vec<glam::Quat>"
    short_name: str # "Vec<Quat>",
    type: str # "array",
    typeInfo: str | None# "List"
    oneOf: List[Any]
   
@dataclass
class RegistryData:
    type_infos: Dict[str, TypeInfo]
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
    bevy = bpy.context.window_manager.bevy # type: BevySettings
    # print("watching schema file for changes")
    try:
        stamp = os.stat(bevy.registry_file).st_mtime
        stamp = str(stamp)
        if stamp != bevy.registry_timestamp and bevy.registry_timestamp != "":
            print("FILE CHANGED !!", stamp,  bevy.registry_timestamp)
            # see here for better ways : https://stackoverflow.com/questions/11114492/check-if-a-file-is-not-open-nor-being-used-by-another-process
            
            # TODO: this should be enabled i think
            #bpy.ops.object.reload_registry()
            # we need to add an additional delay as the file might not have loaded yet
            bpy.app.timers.register(lambda: bpy.ops.object.reload_registry(), first_interval=1)
        bevy.registry_timestamp = stamp
    except Exception as error:
        pass
    return bevy.watcher_poll_frequency if bevy.watcher_enabled else None



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
            'edit_collection_world_texture': self.edit_collection_world_texture,
            'edit_collection_last_scene': self.edit_collection_last_scene
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
    #blueprints_list = [] # type: list[Blueprint]

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
    # 
    # UI settings
    # 
    mode: EnumProperty(
        items=(
            ('COMPONENTS', "Components", ""),
            #('BLUEPRINTS', "Blueprints", ""),
            #('ASSETS', "Assets", ""),bevy
            ('SETTINGS', "Settings", ""),
            ('TOOLS', "Tools", ""),
        ),
        update=save_settings
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

    propGroupIdCounter: IntProperty(
        name="propGroupIdCounter",
        description="",
        min=0,
        max=1000000000,
        default=0
    ) # type: ignore

    # Edit collection instance settings
    edit_collection_last_scene: StringProperty(
        name="name of the scene we started from for editing collection instances",
        description="",
        default="",
        update=save_settings        
    )# type: ignore
    edit_collection_world_texture: bpy.props.EnumProperty(
        name="Background",
        description="Background (World) texture of the temporary scene",
        items=[
            ("checker", "Checker (generated map)", "Checker-like texture using a Generated map"),
            ("checker_view", "Checker (view aligned)", "Checkerboard texture aligned to the view"),
            ("gray", "Gray", "Solid Gray Background"),
            ("none", "None", "No World/background (black)")
        ],
        update=save_settings    
    ) # type: ignore

    def __init__(self):
        self.type_data = RegistryData()

    @classmethod
    def register(cls):
        pass

    @classmethod
    def unregister(cls):
        pass

    # export the scenes, blueprints, materials etc
    def export(self): # , changes_per_scene, changed_export_parameters
        
        start = time.time()

        # save active scene, selected collection and mode
        original_scene = bpy.context.window.scene
        original_collection = bpy.context.view_layer.active_layer_collection        
        original_mode = bpy.context.active_object.mode if bpy.context.active_object != None else None
        original_selections = bpy.context.selected_objects

        # we change the mode to object mode, otherwise the gltf exporter is not happy
        if original_mode != None and original_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        
        self.create_dirs() # create the directories if they dont exist

        # Figure out what to export
        [level_scenes, library_scenes] = self.get_scenes()
        level_scenes.sort(key = lambda a: a.name.lower())                  
        level_count = len(level_scenes)        
    
        # get blueprints
        self.scan_blueprints(level_scenes, library_scenes)
        blueprints_to_export = self.get_blueprints_to_export(library_scenes)                                     
        blueprints_to_export.sort(key = lambda a: a.name.lower())
        blueprint_count = len(blueprints_to_export)

        used_material_names = self.get_all_materials(library_scenes)
        current_project_name = Path(bpy.context.blend_data.filepath).stem

        # update the list of tracked exports
        exports_total = len(blueprints_to_export) + level_count + 1  # +1 for the materials library
        bpy.context.window_manager.auto_export_tracker.exports_total = exports_total
        bpy.context.window_manager.auto_export_tracker.exports_count = exports_total

        print("-------------------------------")
        print("Blueprints:  ", len(self.data.internal_blueprints))
        print("Levels:      ", level_count)
        print("Materials:   ", len(used_material_names))
        print("-------------------------------")

        try:           
            # Export materials
            gltf_path = os.path.join(self.assets_path, MATERIALS_PATH, current_project_name + "_materials")
            material_scene = bpy.data.scenes.new(name=TEMPSCENE_PREFIX + "_materials")                
            for index, material_name in enumerate(used_material_names):
                object = make_cube("Material_"+material_name, location=[index * 0.2,0,0], rotation=[0,0,0], scale=[1,1,1], scene=material_scene)
                material = bpy.data.materials[material_name]
                if material:
                    if object.data.materials: # assign to 1st material slot
                        object.data.materials[0] = material
                    else: # no slots
                        object.data.materials.append(material)      
            self.export_scene(material_scene, {}, gltf_path)

            # delete material scene:
            for object in [o for o in material_scene.collection.objects]:
                try:
                    mesh = bpy.data.meshes[object.name+"_Mesh"]
                    bpy.data.meshes.remove(mesh, do_unlink=True)
                except: pass
                try:
                    bpy.data.objects.remove(object, do_unlink=True)
                except: pass
            bpy.data.scenes.remove(material_scene)

            # export levels
            for index, level_scene in enumerate(level_scenes):                                                             
                print(f"exporting level {index+1}/{level_count}) - {level_scene.name}")                
                gltf_path = os.path.join(self.assets_path, LEVELS_PATH, level_scene.name)    
                temp_scene = bpy.data.scenes.new(name=TEMPSCENE_PREFIX+"_"+ level_scene.name)  
                copy_collection(level_scene.collection, temp_scene.collection)
                if EXPORT_SCENE_SETTINGS:
                    add_scene_settings(temp_scene)
                self.export_scene(temp_scene, {}, gltf_path)
                delete_scene(temp_scene)
                restore_original_names(level_scene.collection)
 
            # export blueprints    
            for index, blueprint in enumerate(blueprints_to_export):
                print(f"exporting blueprint ({index+1}/{blueprint_count}) - {blueprint.name}")
                gltf_path = os.path.join(self.assets_path, BLUEPRINTS_PATH, blueprint.name)                                
                collection = bpy.data.collections[blueprint.name]
                temp_scene = bpy.data.scenes.new(name=TEMPSCENE_PREFIX+"_"+collection.name)                
                copy_collection(collection, temp_scene.collection)
                self.export_scene(temp_scene, {'export_materials': 'PLACEHOLDER'}, gltf_path)
                delete_scene(temp_scene )                
                restore_original_names(collection)

            # reset scene
            bpy.context.window.scene = original_scene
            bpy.context.view_layer.active_layer_collection = original_collection
            if original_mode != None:
                bpy.ops.object.mode_set( mode = original_mode )
            for obj in original_selections:
                obj.select_set(True)

        except Exception as error:
            print(traceback.format_exc())
            def error_message(self, context):
                self.layout.label(text="Failure during auto_export: Error: "+ str(error))
            bpy.context.window_manager.popup_menu(error_message, title="Error", icon='ERROR')

        print(f"Export time: {time.time() - start:.2f}s")       

    @classmethod
    def get_all_modes(cls):
        # Return a list of all possible mode values
        return [item[0] for item in cls.__annotations__['mode'].keywords['items']]

    def get_scenes(self) -> tuple[list[bpy.types.Scene], list[bpy.types.Scene]]:        
        level_scene_names = list(map(lambda scene: scene.name, self.main_scenes))
        library_scene_names = list(map(lambda scene: scene.name, self.library_scenes))
        level_scenes = list(map(lambda name: bpy.data.scenes[name], level_scene_names))
        library_scenes = list(map(lambda name: bpy.data.scenes[name], library_scene_names))        
        return (level_scenes, library_scenes)

    def load_settings(self):
        stored_settings = bpy.data.texts[SETTING_NAME] if SETTING_NAME in bpy.data.texts else None        
        if stored_settings != None:
            settings =  json.loads(stored_settings.as_string())        
            for prop in ['assets_path', 'registry_file', 'auto_export', 'mode', 'edit_collection_world_texture', 'edit_collection_last_scene']:
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

    # blueprints: any collection with either
    # - an instance
    # - marked as asset
    # - with the "auto_export" flag
    # https://blender.stackexchange.com/questions/167878/how-to-get-all-collections-of-the-current-scene
    # TODO: flatten this, use all_objects
    def scan_blueprints(self, main_scenes: list[bpy.types.Scene], library_scenes: list[bpy.types.Scene] ):
         # will update blueprints_data        

        blueprints = {}
        blueprints_from_objects = {}
        blueprint_name_from_instances = {}
        collections = []
        
        # main scenes
        blueprint_instances_per_main_scene = {}
        internal_collection_instances = {}
        external_collection_instances = {}

        # meh
        def add_object_to_collection_instances(collection_name, obj, internal=True):
            collection_category = internal_collection_instances if internal else external_collection_instances
            if not collection_name in collection_category.keys():
                #print("ADDING INSTANCE OF", collection_name, "object", object.name, "categ", collection_category)
                collection_category[collection_name] = [] #.append(collection_name)
            collection_category[collection_name].append(obj)

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

                    add_object_to_collection_instances(collection_name=collection_name, obj=object, internal = collection_from_library)

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
                        add_object_to_collection_instances(collection_name=object.instance_collection.name, obj=object, internal = blueprint.local)

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

        # helper function that returns a lambda, used for the PropertyGroups update function below        
        def update_calback_helper(definition, update, component_name_override):
            return lambda self, context: update(self, context, definition, component_name_override)

        # called on updated by generated property groups for component_meta, serializes component_meta then saves it to bevy_components
        def update_component(self, context, definition, component_name):
            bevy = bpy.context.window_manager.bevy # type: BevySettings
            
            # get selected object or collection:
            current_object_or_collection = None
            object = next(iter(context.selected_objects), None)
            collection = context.collection
            if object is not None:
                current_object_or_collection = object
            elif collection is not None:
                current_object_or_collection = collection            
            
            # if we have an object or collection
            if current_object_or_collection:
                update_disabled = current_object_or_collection["__disable__update"] if "__disable__update" in current_object_or_collection else False
                update_disabled = bevy.disable_all_object_updates or update_disabled # global settings
                if update_disabled:
                    return
                
                if current_object_or_collection["components_meta"] is None:
                    print("ERROR: object does not have components_meta", current_object_or_collection.name)
                    return
                
                components_in_object = current_object_or_collection.components_meta.components
                component_meta =  next(filter(lambda component: component["long_name"] == component_name, components_in_object), None)

                if component_meta is not None:
                    property_group_name = bevy.type_data.long_names_to_propgroup_names.get(component_name, None)
                    property_group = getattr(component_meta, property_group_name)
                    # we use our helper to set the values
                    previous = json.loads(current_object_or_collection['bevy_components'])
                    previous[component_name] = bevy.property_group_value_to_custom_property_value(property_group, definition, None)
                    current_object_or_collection['bevy_components'] = json.dumps(previous)

        # Generate propertyGroups for all components        
        for component_name in self.type_data.type_infos:
            definition = self.type_data.type_infos.get(component_name, None) 
            if definition:
                self.process_component(definition, update_calback_helper(definition, update_component, component_name), None, [])                
            else:
                print(f"ERROR: could not find definition for component {component_name}")
                #self.data.type_infos_missing.append(component_name)

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

        # how can self.type_infos 616, then 0 everywhere else ?
        print(f"INFO: loaded {len(self.type_data.type_infos)} types from registry file: {self.registry_file}")

        # ensure metadata for allobjects
        # FIXME: feels a bit heavy duty, should only be done
        # if the components panel is active ?
        for object in bpy.data.objects:
            self.add_metadata_to_components_without_metadata(object)

    # adds metadata to object only if it is missing
    def add_metadata_to_components_without_metadata(self, object):
        for component_name in get_bevy_components(object) :
            if component_name == "components_meta":
                continue
            self.upsert_component_in_object(object, component_name)

    # TODO: so this kinda blew my mind because not only does it recursively handle nested components, 
    # and all the different types, but ithen it generates __annotations__ which is a special class definition
    # system just for blender
    def process_component(self, definition: dict[str, Any], update, extras=None, nesting = [], nesting_long_names = []):
        long_name = definition["long_name"]
        short_name = definition["short_name"]
        type_info = definition["typeInfo"] if "typeInfo" in definition else None
        type_def = definition["type"] if "type" in definition else None
        properties = definition["properties"] if "properties" in definition else {}
        prefixItems = definition["prefixItems"] if "prefixItems" in definition else []

        has_properties = len(properties.keys()) > 0
        has_prefixItems = len(prefixItems) > 0
        is_enum = type_info == "Enum"
        is_list = type_info == "List"
        is_map = type_info == "Map"

        __annotations__ = {}
        tupple_or_struct = None

        with_properties = False
        with_items = False
        with_enum = False
        with_list = False
        with_map = False


        if has_properties:
            __annotations__ = __annotations__ | self.process_structs(definition, update, properties, nesting, nesting_long_names)
            with_properties = True
            tupple_or_struct = "struct"

        if has_prefixItems:
            __annotations__ = __annotations__ | self.process_tupples(definition, update, prefixItems, nesting, nesting_long_names)
            with_items = True
            tupple_or_struct = "tupple"

        if is_enum:
            __annotations__ = __annotations__ | self.process_enum(definition, update, nesting, nesting_long_names)
            with_enum = True

        if is_list:
            __annotations__ = __annotations__ | self.process_list(definition, update, nesting, nesting_long_names)
            with_list= True

        if is_map:
            __annotations__ = __annotations__ | self.process_map(definition, update, nesting, nesting_long_names)
            with_map = True
        
        field_names = []
        for a in __annotations__:
            field_names.append(a)
    

        extras = extras if extras is not None else {
            "long_name": long_name
        }
        root_component = nesting_long_names[0] if len(nesting_long_names) > 0 else long_name
        # print("")
        property_group_params = {
            **extras,
            '__annotations__': __annotations__,
            'tupple_or_struct': tupple_or_struct,
            'field_names': field_names, 
            **dict(with_properties = with_properties, with_items= with_items, with_enum= with_enum, with_list= with_list, with_map = with_map, short_name= short_name, long_name=long_name),
            'root_component': root_component
        }
        #FIXME: YIKES, but have not found another way
        #  withouth this, the following does not work
        # -BasicTest
        # - NestingTestLevel2
        #    -BasicTest => the registration & update callback of this one overwrites the first "basicTest"
        # have not found a cleaner workaround so far
        property_group_name = self.generate_propGroup_name(nesting, long_name)

        def property_group_from_infos(property_group_name, property_group_parameters):
            # print("creating property group", property_group_name)
            property_group_class = type(property_group_name, (PropertyGroup,), property_group_parameters)
            bpy.utils.register_class(property_group_class)
            property_group_pointer = PointerProperty(type=property_group_class)
            return (property_group_pointer, property_group_class)
        
        (property_group_pointer, property_group_class) = property_group_from_infos(property_group_name, property_group_params)
        
        # add our component propertyGroup to the registry
        self.type_data.component_propertyGroups[property_group_name] = property_group_pointer
        
        return (property_group_pointer, property_group_class)

    def process_enum(self, definition: TypeInfo, update, nesting, nesting_long_names):
        short_name = definition["short_name"]
        long_name = definition["long_name"]

        type_def = definition["type"] if "type" in definition else None
        variants = definition["oneOf"]

        nesting = nesting + [short_name]
        nesting_long_names = nesting_long_names = [long_name]

        __annotations__ = {}
        original_type_name = "enum"

        # print("processing enum", short_name, long_name, definition)

        if type_def == "object":
            labels = []
            additional_annotations = {}
            for variant in variants:
                variant_name = variant["long_name"]
                variant_prefixed_name = "variant_" + variant_name
                labels.append(variant_name)

                if "prefixItems" in variant:
                    #print("tupple variant in enum", variant)
                    self.add_custom_type(variant_name, variant)
                    (sub_component_group, _) = self.process_component(variant, update, {"nested": True}, nesting, nesting_long_names) 
                    additional_annotations[variant_prefixed_name] = sub_component_group
                elif "properties" in variant:
                    #print("struct variant in enum", variant)
                    self.add_custom_type(variant_name, variant)
                    (sub_component_group, _) = self.process_component(variant, update, {"nested": True}, nesting, nesting_long_names) 
                    additional_annotations[variant_prefixed_name] = sub_component_group
                else: # for the cases where it's neither a tupple nor a structs: FIXME: not 100% sure of this
                    #print("other variant in enum")
                    annotations = {"variant_"+variant_name: StringProperty(default="----<ignore_field>----")}
                    additional_annotations = additional_annotations | annotations

            items = tuple((e, e, e) for e in labels)

            blender_property_def = BLENDER_PROPERTY_MAPPING[original_type_name]
            blender_property = blender_property_def["type"](
                **blender_property_def["presets"],# we inject presets first
                items=items, # this is needed by Blender's EnumProperty , which we are using here
                update=update
            )
            __annotations__["selection"] = blender_property

            for a in additional_annotations:
                __annotations__[a] = additional_annotations[a]
            # enum_value => what field to display
            # a second field + property for the "content" of the enum
        else:
            items = tuple((e, e, "") for e in variants)        
            blender_property_def = BLENDER_PROPERTY_MAPPING[original_type_name]
            blender_property = blender_property_def["type"](
                **blender_property_def["presets"],# we inject presets first
                items=items,
                update=update
            )
            __annotations__["selection"] = blender_property
        
        return __annotations__

    def process_tupples(self, definition: TypeInfo, update, prefixItems, nesting=[], nesting_long_names=[]):
        type_infos = self.type_data.type_infos
        long_name = definition["long_name"]
        short_name = definition["short_name"]

        nesting = nesting + [short_name]
        nesting_long_names = nesting_long_names + [long_name]
        __annotations__ = {}

        default_values = []
        prefix_infos = []
        for index, item in enumerate(prefixItems):
            ref_name = item["type"]["$ref"].replace("#/$defs/", "")

            property_name = str(index)# we cheat a bit, property names are numbers here, as we do not have a real property name
        
            if ref_name in type_infos:
                original = type_infos[ref_name]
                original_long_name = original["long_name"]
                is_value_type = original_long_name in VALUE_TYPES_DEFAULTS

                value = VALUE_TYPES_DEFAULTS[original_long_name] if is_value_type else None
                default_values.append(value)
                prefix_infos.append(original)

                if is_value_type:
                    if original_long_name in BLENDER_PROPERTY_MAPPING:
                        blender_property_def = BLENDER_PROPERTY_MAPPING[original_long_name]
                        blender_property = blender_property_def["type"](
                            **blender_property_def["presets"],# we inject presets first
                            name = property_name, 
                            default=value,
                            update=update
                        )
                    
                        __annotations__[property_name] = blender_property
                else:
                    original_long_name = original["long_name"]
                    (sub_component_group, _) = self.process_component(original, update, {"nested": True, "long_name": original_long_name}, nesting)
                    __annotations__[property_name] = sub_component_group
            else: 
                # component not found in type_infos, generating placeholder
                __annotations__[property_name] = StringProperty(default="N/A")
                self.add_missing_typeInfo(ref_name)
                # the root component also becomes invalid (in practice it is not always a component, but good enough)
                self.add_invalid_component(nesting_long_names[0])


        return __annotations__

    def process_list(self, definition: TypeInfo, update, nesting=[], nesting_long_names=[]):
        
        type_infos = self.type_data.type_infos

        short_name = definition["short_name"]
        long_name = definition["long_name"]
        ref_name = definition["items"]["type"]["$ref"].replace("#/$defs/", "")

        nesting = nesting+[short_name]
        nesting_long_names = nesting_long_names + [long_name]
        
        item_definition = type_infos[ref_name]
        item_long_name = item_definition["long_name"]
        is_item_value_type = item_long_name in VALUE_TYPES_DEFAULTS

        property_group_class = None
        #if the content of the list is a unit type, we need to generate a fake wrapper, otherwise we cannot use layout.prop(group, "propertyName") as there is no propertyName !
        if is_item_value_type:
            property_group_class = self.generate_wrapper_propertyGroup(long_name, item_long_name, definition["items"]["type"]["$ref"], update)
        else:
            (_, list_content_group_class) = self.process_component(item_definition, update, {"nested": True, "long_name": item_long_name}, nesting)
            property_group_class = list_content_group_class

        item_collection = CollectionProperty(type=property_group_class)

        item_long_name = item_long_name if not is_item_value_type else  "wrapper_" + item_long_name
        __annotations__ = {
            "list": item_collection,
            "list_index": IntProperty(name = "Index for list", default = 0,  update=update),
            "long_name": StringProperty(default=item_long_name)
        }

        return __annotations__

    def process_structs(self, definition: TypeInfo, update, properties, nesting, nesting_long_names): 
        type_infos = self.type_data.type_infos
        
        long_name = definition["long_name"]
        short_name = definition["short_name"]

        __annotations__ = {}
        default_values = {}
        nesting = nesting + [short_name]
        nesting_long_names = nesting_long_names + [long_name]

        for property_name in properties.keys():
            ref_name = properties[property_name]["type"]["$ref"].replace("#/$defs/", "")
            
            if ref_name in type_infos:
                original = type_infos[ref_name]
                original_long_name = original["long_name"]
                is_value_type = original_long_name in VALUE_TYPES_DEFAULTS
                value = VALUE_TYPES_DEFAULTS[original_long_name] if is_value_type else None
                default_values[property_name] = value

                if is_value_type:
                    if original_long_name in BLENDER_PROPERTY_MAPPING:
                        blender_property_def = BLENDER_PROPERTY_MAPPING[original_long_name]
                        blender_property = blender_property_def["type"](
                            **blender_property_def["presets"],# we inject presets first
                            name= property_name,
                            default= value,
                            update= update,
                        )
                        __annotations__[property_name] = blender_property
                else:
                    original_long_name = original["long_name"]
                    (sub_component_group, _) = self.process_component(original, update, {"nested": True, "long_name": original_long_name}, nesting, nesting_long_names)
                    __annotations__[property_name] = sub_component_group
            # if there are sub fields, add an attribute "sub_fields" possibly a pointer property ? or add a standard field to the type , that is stored under "attributes" and not __annotations (better)
            else:
                # component not found in type_infos, generating placeholder
                __annotations__[property_name] = StringProperty(default="N/A")
                self.add_missing_typeInfo(ref_name)
                # the root component also becomes invalid (in practice it is not always a component, but good enough)
                self.add_invalid_component(nesting_long_names[0])

        return __annotations__

    def process_map(self, definition: TypeInfo, update, nesting=[], nesting_long_names=[]):
        
        type_infos = self.type_data.type_infos

        short_name = definition["short_name"]
        long_name = definition["long_name"]

        nesting = nesting + [short_name]
        nesting_long_names = nesting_long_names + [long_name]

        value_ref_name = definition["valueType"]["type"]["$ref"].replace("#/$defs/", "")
        key_ref_name = definition["keyType"]["type"]["$ref"].replace("#/$defs/", "")

        #print("definition", definition)
        __annotations__ = {}
        if key_ref_name in type_infos:
            key_definition = type_infos[key_ref_name]
            original_long_name = key_definition["long_name"]
            is_key_value_type = original_long_name in VALUE_TYPES_DEFAULTS
            definition_link = definition["keyType"]["type"]["$ref"]

            #if the content of the list is a unit type, we need to generate a fake wrapper, otherwise we cannot use layout.prop(group, "propertyName") as there is no propertyName !
            if is_key_value_type:
                keys_property_group_class = self.generate_wrapper_propertyGroup(f"{long_name}_keys", original_long_name, definition_link, update)
            else:
                (_, list_content_group_class) = self.process_component(key_definition, update, {"nested": True, "long_name": original_long_name}, nesting, nesting_long_names)
                keys_property_group_class = list_content_group_class

            keys_collection = CollectionProperty(type=keys_property_group_class)
            keys_property_group_pointer = PointerProperty(type=keys_property_group_class)
        else:
            __annotations__["list"] = StringProperty(default="N/A")
            self.add_missing_typeInfo(key_ref_name)
            # the root component also becomes invalid (in practice it is not always a component, but good enough)
            self.add_invalid_component(nesting_long_names[0])

        if value_ref_name in type_infos:
            value_definition = type_infos[value_ref_name]
            original_long_name = value_definition["long_name"]
            is_value_value_type = original_long_name in VALUE_TYPES_DEFAULTS
            definition_link = definition["valueType"]["type"]["$ref"]

            #if the content of the list is a unit type, we need to generate a fake wrapper, otherwise we cannot use layout.prop(group, "propertyName") as there is no propertyName !
            if is_value_value_type:
                values_property_group_class = self.generate_wrapper_propertyGroup(f"{long_name}_values", original_long_name, definition_link, update)
            else:
                (_, list_content_group_class) = self.process_component( value_definition, update, {"nested": True, "long_name": original_long_name}, nesting, nesting_long_names)
                values_property_group_class = list_content_group_class

            values_collection = CollectionProperty(type=values_property_group_class)
            values_property_group_pointer = PointerProperty(type=values_property_group_class)

        else:
            #__annotations__["list"] = StringProperty(default="N/A")
            self.add_missing_typeInfo(value_ref_name)
            # the root component also becomes invalid (in practice it is not always a component, but good enough)
            self.add_invalid_component(nesting_long_names[0])


        if key_ref_name in type_infos and value_ref_name in type_infos:
            __annotations__ = {
                "list": keys_collection,
                "list_index": IntProperty(name = "Index for keys", default = 0,  update=update),
                "keys_setter":keys_property_group_pointer,
                
                "values_list": values_collection,
                "values_list_index": IntProperty(name = "Index for values", default = 0,  update=update),
                "values_setter":values_property_group_pointer,
            }
        
        """__annotations__["list"] = StringProperty(default="N/A")
        __annotations__["values_list"] = StringProperty(default="N/A")
        __annotations__["keys_setter"] = StringProperty(default="N/A")"""

        """registry.add_missing_typeInfo(key_ref_name)
        registry.add_missing_typeInfo(value_ref_name)
        # the root component also becomes invalid (in practice it is not always a component, but good enough)
        registry.add_invalid_component(nesting_long_names[0])
        print("setting invalid flag for", nesting_long_names[0])"""

        return __annotations__

    # adds a component to an object (including metadata) using the provided component definition & optional value
    def add_component_to_object(self, object, long_name: str, value=None):
        cleanup_invalid_metadata(object)
        if object is not None:
            definition = self.type_data.type_infos[long_name]         
            print("adding component", definition)
            if not self.has_type_infos():
                raise Exception('registry type infos have not been loaded yet or are missing !')            
            
            # now we use our pre_generated property groups to set the initial value of our custom property
            (_, propertyGroup) = self.upsert_component_in_object(object, long_name=long_name)
            if value == None:
                value = self.property_group_value_to_custom_property_value(propertyGroup, definition, None)
            else: # we have provided a value, that is a raw , custom property value, to set the value of the propertyGroup
                object["__disable__update"] = True # disable update callback while we set the values of the propertyGroup "tree" (as a propertyGroup can contain other propertyGroups) 
                self.property_group_value_from_custom_property_value(propertyGroup, definition, value)
                del object["__disable__update"]

            upsert_bevy_component(object, long_name, value)

    def upsert_component_in_object(self, object, long_name: str):
        # print("upsert_component_in_object", object, "component name", component_name)
        # TODO: upsert this part too ?
        target_components_metadata = object.components_meta.components
        component_definition = self.type_data.type_infos.get(long_name, None)

        if component_definition != None:
            short_name = component_definition["short_name"]
            long_name = component_definition["long_name"]
            property_group_name = self.type_data.long_names_to_propgroup_names.get(long_name, None)
            propertyGroup = None

            component_meta = next(filter(lambda component: component["long_name"] == long_name, target_components_metadata), None)
            if not component_meta:
                component_meta = target_components_metadata.add()
                component_meta.short_name = short_name
                component_meta.long_name = long_name
                propertyGroup = getattr(component_meta, property_group_name, None)
            else: # this one has metadata but we check that the relevant property group is present
                propertyGroup = getattr(component_meta, property_group_name, None)

            # try to inject propertyGroup if not present
            if propertyGroup == None:
                #print("propertygroup not found in metadata attempting to inject")
                if property_group_name in self.type_data.component_propertyGroups:
                    # we have found a matching property_group, so try to inject it
                    # now inject property group
                    setattr(ComponentMetadata, property_group_name, self.type_data.component_propertyGroups[property_group_name]) # FIXME: not ideal as all ComponentMetadata get the propGroup, but have not found a way to assign it per instance
                    propertyGroup = getattr(component_meta, property_group_name, None)
            
            # now deal with property groups details
            if propertyGroup != None:
                if long_name in self.type_data.invalid_components:
                    component_meta.enabled = False
                    component_meta.invalid = True
                    component_meta.invalid_details = "component contains fields that are not in the registry, disabling"
            else:
                # if we still have not found the property group, mark it as invalid
                component_meta.enabled = False
                component_meta.invalid = True
                component_meta.invalid_details = "component not present in the registry, possibly renamed? Disabling for now"
            # property_group_value_from_custom_property_value(propertyGroup, component_definition, registry, object[component_name])

            return (component_meta, propertyGroup)
        else:
            return(None, None)

    #converts the value of a property group(no matter its complexity) into a single custom property value
    # this is more or less a glorified "to_ron()" method (not quite but close to)
    def property_group_value_to_custom_property_value(self, property_group, definition, parent=None, value=None):

        long_name = definition["long_name"]
        type_info = definition["typeInfo"] if "typeInfo" in definition else None
        type_def = definition["type"] if "type" in definition else None
        is_value_type = long_name in conversion_tables
        # print("computing custom property: component name:", long_name, "type_info", type_info, "type_def", type_def, "value", value)

        if is_value_type:
            value = conversion_tables[long_name](value)
        elif type_info == "Struct":
            values = {}
            if len(property_group.field_names) ==0:
                value = '()'
            else:
                for index, field_name in enumerate(property_group.field_names):
                    item_long_name = definition["properties"][field_name]["type"]["$ref"].replace("#/$defs/", "")
                    item_definition = self.type_data.type_infos[item_long_name] if item_long_name in self.type_data.type_infos else None

                    value = getattr(property_group, field_name)
                    is_property_group = isinstance(value, PropertyGroup)
                    child_property_group = value if is_property_group else None
                    if item_definition != None:
                        value = self.property_group_value_to_custom_property_value(child_property_group, item_definition, parent=long_name, value=value)
                    else:
                        value = '""'
                    values[field_name] = value
                value = values        
        elif type_info == "Tuple": 
            values = {}
            for index, field_name in enumerate(property_group.field_names):
                item_long_name = definition["prefixItems"][index]["type"]["$ref"].replace("#/$defs/", "")
                item_definition = self.type_data.type_infos[item_long_name] if item_long_name in self.type_data.type_infos else None

                value = getattr(property_group, field_name)
                is_property_group = isinstance(value, PropertyGroup)
                child_property_group = value if is_property_group else None
                if item_definition != None:
                    value = self.property_group_value_to_custom_property_value(child_property_group, item_definition, parent=long_name, value=value)
                else:
                    value = '""'
                values[field_name] = value
            value = tuple(e for e in list(values.values()))

        elif type_info == "TupleStruct":
            values = {}
            for index, field_name in enumerate(property_group.field_names):
                #print("toto", index, definition["prefixItems"][index]["type"]["$ref"])
                item_long_name = definition["prefixItems"][index]["type"]["$ref"].replace("#/$defs/", "")
                item_definition = self.type_data.type_infos[item_long_name] if item_long_name in self.type_data.type_infos else None

                value = getattr(property_group, field_name)
                is_property_group = isinstance(value, PropertyGroup)
                child_property_group = value if is_property_group else None
                if item_definition != None:
                    value = self.property_group_value_to_custom_property_value(child_property_group, item_definition, parent=long_name, value=value)
                else:
                    value = '""'
                values[field_name] = value
            
            value = tuple(e for e in list(values.values()))
        elif type_info == "Enum":
            selected = getattr(property_group, "selection")
            if type_def == "object":
                selection_index = property_group.field_names.index("variant_"+selected)
                variant_name = property_group.field_names[selection_index]
                variant_definition = definition["oneOf"][selection_index-1]
                if "prefixItems" in variant_definition:
                    value = getattr(property_group, variant_name)
                    is_property_group = isinstance(value, PropertyGroup)
                    child_property_group = value if is_property_group else None

                    value = self.property_group_value_to_custom_property_value(child_property_group, variant_definition, parent=long_name, value=value)
                    value = selected + str(value,) #"{}{},".format(selected ,value)
                elif "properties" in variant_definition:
                    value = getattr(property_group, variant_name)
                    is_property_group = isinstance(value, PropertyGroup)
                    child_property_group = value if is_property_group else None

                    value = self.property_group_value_to_custom_property_value(child_property_group, variant_definition, parent=long_name, value=value)
                    value = selected + str(value,)
                else:
                    value = getattr(property_group, variant_name)
                    is_property_group = isinstance(value, PropertyGroup)
                    child_property_group = value if is_property_group else None
                    if child_property_group:
                        value = self.property_group_value_to_custom_property_value(child_property_group, variant_definition, parent=long_name, value=value)
                        value = selected + str(value,)
                    else:
                        value = selected # here the value of the enum is just the name of the variant
            else: 
                value = selected

        elif type_info == "List":
            item_list = getattr(property_group, "list")
            value = []
            for item in item_list:
                item_long_name = getattr(item, "long_name")
                definition = self.type_data.type_infos[item_long_name] if item_long_name in self.type_data.type_infos else None
                if definition != None:
                    item_value = self.property_group_value_to_custom_property_value(item, definition, long_name, None)
                    if item_long_name.startswith("wrapper_"): #if we have a "fake" tupple for aka for value types, we need to remove one nested level
                        item_value = item_value[0]
                else:
                    item_value = '""'
                value.append(item_value) 

        elif type_info == "Map":
            keys_list = getattr(property_group, "list", {})
            values_list = getattr(property_group, "values_list")
            value = {}
            for index, key in enumerate(keys_list):
                # first get the keys
                key_long_name = getattr(key, "long_name")
                definition = self.type_data.type_infos[key_long_name] if key_long_name in self.type_data.type_infos else None
                if definition != None:
                    key_value = self.property_group_value_to_custom_property_value(key, definition, long_name, None)
                    if key_long_name.startswith("wrapper_"): #if we have a "fake" tupple for aka for value types, we need to remove one nested level
                        key_value = key_value[0]
                else:
                    key_value = '""'
                # and then the values
                val = values_list[index]
                value_long_name = getattr(val, "long_name")
                definition = self.type_data.type_infos[value_long_name] if value_long_name in self.type_data.type_infos else None
                if definition != None:
                    val_value = self.property_group_value_to_custom_property_value(val, definition, long_name, None)
                    if value_long_name.startswith("wrapper_"): #if we have a "fake" tupple for aka for value types, we need to remove one nested level
                        val_value = val_value[0]
                else:
                    val_value = '""'

                value[key_value] = val_value
            value = str(value).replace('{','@').replace('}','²') # FIXME: eeek !!
        else:
            value = conversion_tables[long_name](value) if is_value_type else value
            value = '""' if isinstance(value, PropertyGroup) else value
            
        #print("generating custom property value", value, type(value))
        if isinstance(value, str):
            value = value.replace("'", "")

        if parent == None:
            value = str(value).replace("'",  "")
            value = value.replace(",)",")")
            value = value.replace("{", "(").replace("}", ")") # FIXME: deal with hashmaps
            value = value.replace("True", "true").replace("False", "false")
            value = value.replace('@', '{').replace('²', '}')
        return value

    #converts the value of a single custom property into a value (values) of a property group 
    def property_group_value_from_custom_property_value(self, property_group, definition, value, nesting = []):
            
        type_info = definition["typeInfo"] if "typeInfo" in definition else None
        type_def = definition["type"] if "type" in definition else None
        properties = definition["properties"] if "properties" in definition else {}
        prefixItems = definition["prefixItems"] if "prefixItems" in definition else []
        long_name = definition["long_name"]
        
        is_value_type = long_name in VALUE_TYPES_DEFAULTS
        nesting = nesting + [definition["short_name"]]

        if is_value_type:
            value = value.replace("(", "").replace(")", "")# FIXME: temporary, incoherent use of nesting levels between parse_tuplestruct_string & parse_struct_string
            value = type_mappings[long_name](value) if long_name in type_mappings else value
            return value
        elif type_info == "Struct":
            if len(property_group.field_names) != 0 :
                custom_property_values = parse_struct_string(value, start_nesting=1 if value.startswith("(") else 0)
                for index, field_name in enumerate(property_group.field_names):
                    item_long_name = definition["properties"][field_name]["type"]["$ref"].replace("#/$defs/", "")
                    item_definition = self.type_data.type_infos[item_long_name] if item_long_name in self.type_data.type_infos else None

                    custom_prop_value = custom_property_values[field_name]
                    #print("field name", field_name, "value", custom_prop_value)
                    propGroup_value = getattr(property_group, field_name)
                    is_property_group = isinstance(propGroup_value, PropertyGroup)
                    child_property_group = propGroup_value if is_property_group else None
                    if item_definition != None:
                        custom_prop_value = self.property_group_value_from_custom_property_value(child_property_group, item_definition, value=custom_prop_value, nesting=nesting)
                    else:
                        custom_prop_value = custom_prop_value

                    if is_def_value_type(item_definition):
                        setattr(property_group , field_name, custom_prop_value)
                

            else:
                if len(value) > 2: #a unit struct should be two chars long :()
                    #print("struct with zero fields")
                    raise Exception("input string too big for a unit struct")

        elif type_info == "Tuple": 
            custom_property_values = parse_tuplestruct_string(value, start_nesting=1 if len(nesting) == 1 else 1)

            for index, field_name in enumerate(property_group.field_names):
                item_long_name = definition["prefixItems"][index]["type"]["$ref"].replace("#/$defs/", "")
                item_definition = self.type_data.type_infos[item_long_name] if item_long_name in self.type_data.type_infos else None
                
                custom_property_value = custom_property_values[index]

                propGroup_value = getattr(property_group, field_name)
                is_property_group = isinstance(propGroup_value, PropertyGroup)
                child_property_group = propGroup_value if is_property_group else None
                if item_definition != None:
                    custom_property_value = self.property_group_value_from_custom_property_value(child_property_group, item_definition, value=custom_property_value, nesting=nesting)
                if is_def_value_type(item_definition):
                    setattr(property_group , field_name, custom_property_value)

        elif type_info == "TupleStruct":
            custom_property_values = parse_tuplestruct_string(value, start_nesting=1 if len(nesting) == 1 else 0)
            for index, field_name in enumerate(property_group.field_names):
                item_long_name = definition["prefixItems"][index]["type"]["$ref"].replace("#/$defs/", "")
                item_definition = self.type_data.type_infos[item_long_name] if item_long_name in self.type_data.type_infos else None

                custom_prop_value = custom_property_values[index]

                value = getattr(property_group, field_name)
                is_property_group = isinstance(value, PropertyGroup)
                child_property_group = value if is_property_group else None
                if item_definition != None:
                    custom_prop_value = self.property_group_value_from_custom_property_value(child_property_group, item_definition, value=custom_prop_value, nesting=nesting)

                if is_def_value_type(item_definition):
                        setattr(property_group , field_name, custom_prop_value)

        elif type_info == "Enum":
            field_names = property_group.field_names
            if type_def == "object":
                regexp = re.search('(^[^\(]+)(\((.*)\))', value)
                try:
                    chosen_variant_raw = regexp.group(1)
                    chosen_variant_value = regexp.group(3)
                    chosen_variant_name = "variant_" + chosen_variant_raw 
                except:
                    chosen_variant_raw = value
                    chosen_variant_value = ""
                    chosen_variant_name = "variant_" + chosen_variant_raw 
                selection_index = property_group.field_names.index(chosen_variant_name)
                variant_definition = definition["oneOf"][selection_index-1]
                # first we set WHAT variant is selected
                setattr(property_group, "selection", chosen_variant_raw)

                # and then we set the value of the variant
                if "prefixItems" in variant_definition:
                    value = getattr(property_group, chosen_variant_name)
                    is_property_group = isinstance(value, PropertyGroup)
                    child_property_group = value if is_property_group else None
                    
                    chosen_variant_value = "(" +chosen_variant_value +")" # needed to handle nesting correctly
                    value = self.property_group_value_from_custom_property_value(child_property_group, variant_definition, value=chosen_variant_value, nesting=nesting)
                    
                elif "properties" in variant_definition:
                    value = getattr(property_group, chosen_variant_name)
                    is_property_group = isinstance(value, PropertyGroup)
                    child_property_group = value if is_property_group else None

                    value = self.property_group_value_from_custom_property_value(child_property_group, variant_definition, value=chosen_variant_value, nesting=nesting)
                    
            else:
                chosen_variant_raw = value
                setattr(property_group, field_names[0], chosen_variant_raw)

        elif type_info == "List":
            item_list = getattr(property_group, "list")
            item_long_name = getattr(property_group, "long_name")
            custom_property_values = parse_tuplestruct_string(value, start_nesting=2 if item_long_name.startswith("wrapper_") and value.startswith('(') else 1) # TODO : the additional check here is wrong, there is an issue somewhere in higher level stuff
            # clear list first
            item_list.clear()
            for raw_value in custom_property_values:
                new_entry = item_list.add()   
                item_long_name = getattr(new_entry, "long_name") # we get the REAL type name
                definition = self.type_data.type_infos[item_long_name] if item_long_name in self.type_data.type_infos else None

                if definition != None:
                    self.property_group_value_from_custom_property_value(new_entry, definition, value=raw_value, nesting=nesting)            
        else:
            try:
                value = value.replace("(", "").replace(")", "")# FIXME: temporary, incoherent use of nesting levels between parse_tuplestruct_string & parse_struct_string
                value = type_mappings[long_name](value) if long_name in type_mappings else value
                return value
            except:
                pass

    def copy_propertyGroup_values_to_another_object(self, source_object, target_object, component_name):
        if source_object == None or target_object == None or component_name == None:
            raise Exception('missing input data, cannot copy component propertryGroup')
        
        component_definition = self.type_data.type_infos.get(component_name, None)
        long_name = component_name
        property_group_name = self.type_data.long_names_to_propgroup_names.get(long_name, None)

        source_components_metadata = source_object.components_meta.components
        source_componentMeta = next(filter(lambda component: component["long_name"] == long_name, source_components_metadata), None)
        # matching component means we already have this type of component 
        source_propertyGroup = getattr(source_componentMeta, property_group_name)

        # now deal with the target object
        (_, target_propertyGroup) = self.upsert_component_in_object(target_object, component_name)
        # add to object
        value = self.property_group_value_to_custom_property_value(target_propertyGroup, component_definition, None)
        upsert_bevy_component(target_object, long_name, value)

        # copy the values over 
        for field_name in source_propertyGroup.field_names:
            if field_name in source_propertyGroup:
                target_propertyGroup[field_name] = source_propertyGroup[field_name]
        self.apply_propertyGroup_values_to_object_customProperties(target_object)

    def apply_propertyGroup_values_to_object_customProperties(self, object):
        cleanup_invalid_metadata(object)
        for component_name in get_bevy_components(object) :            
            (_, propertyGroup) =  self.upsert_component_in_object(object, component_name)
            component_definition = self.type_data.type_infos.get(component_name, None)
            if component_definition != None:
                value = self.property_group_value_to_custom_property_value(propertyGroup, component_definition, None)
                upsert_bevy_component(object=object, long_name=component_name, value=value)

    # apply component value(s) to custom property of a single component
    def apply_propertyGroup_values_to_object_customProperties_for_component(self, object, component_name):
        
        (_, propertyGroup) = self.upsert_component_in_object(object, component_name)
        component_definition = self.type_data.type_infos.get(component_name, None)
        if component_definition != None:
            value = self.property_group_value_to_custom_property_value(propertyGroup, component_definition, None)
            object[component_name] = value
        
        components_metadata = object.components_meta.components
        componentMeta = next(filter(lambda component: component["long_name"] == component_name, components_metadata), None)
        if componentMeta:
            componentMeta.invalid = False
            componentMeta.invalid_details = ""

    def apply_customProperty_values_to_object_propertyGroups(self, object):
        print("apply custom properties to ", object.name)
        
        for component_name in get_bevy_components(object) :
            if component_name == "components_meta":
                continue
            component_definition = self.type_data.type_infos.get(component_name, None)
            if component_definition != None:
                property_group_name = self.type_data.long_names_to_propgroup_names.get(component_name, None)
                components_metadata = object.components_meta.components
                source_componentMeta = next(filter(lambda component: component["long_name"] == component_name, components_metadata), None)
                # matching component means we already have this type of component 
                propertyGroup = getattr(source_componentMeta, property_group_name, None)
                customProperty_value = get_bevy_component_value_by_long_name(object, component_name)
                #value = property_group_value_to_custom_property_value(propertyGroup, component_definition, registry, None)
                
                object["__disable__update"] = True # disable update callback while we set the values of the propertyGroup "tree" (as a propertyGroup can contain other propertyGroups) 
                self.property_group_value_from_custom_property_value(propertyGroup, component_definition, customProperty_value)
                del object["__disable__update"]
                source_componentMeta.invalid = False
                source_componentMeta.invalid_details = ""

    def add_component_from_custom_property(self, object):
        self.add_metadata_to_components_without_metadata(object)
        self.apply_customProperty_values_to_object_propertyGroups(object)

    def rename_component(self, object, original_long_name: str, new_long_name: str):        
        component_ron_value = get_bevy_component_value_by_long_name(object=object, long_name=original_long_name)
        if component_ron_value is None and original_long_name in object:
            component_ron_value = object[original_long_name]

        remove_component_from_object(object, original_long_name)
        self.add_component_to_object(object, new_long_name, component_ron_value)

    # this helper creates a "fake"/wrapper property group that is NOT a real type in the registry
    # usefull for things like value types in list items etc
    def generate_wrapper_propertyGroup(self, wrapped_type_long_name_name, item_long_name, definition_link, update):
        is_item_value_type = item_long_name in VALUE_TYPES_DEFAULTS

        wrapper_name = "wrapper_" + wrapped_type_long_name_name

        wrapper_definition = {
            "isComponent": False,
            "isResource": False,
            "items": False,
            "prefixItems": [
                {
                    "type": {
                        "$ref": definition_link
                    }
                }
            ],
            "short_name": wrapper_name, # FIXME !!!
            "long_name": wrapper_name,
            "type": "array",
            "typeInfo": "TupleStruct"
        }

        # we generate a very small 'hash' for the component name
        property_group_name = self.generate_propGroup_name(nesting=[], longName=wrapper_name)
        self.add_custom_type(wrapper_name, wrapper_definition)

        blender_property = StringProperty(default="", update=update)
        if item_long_name in BLENDER_PROPERTY_MAPPING:
            value = VALUE_TYPES_DEFAULTS[item_long_name] if is_item_value_type else None
            blender_property_def = BLENDER_PROPERTY_MAPPING[item_long_name]
            blender_property = blender_property_def["type"](
                **blender_property_def["presets"],# we inject presets first
                name = "property_name",
                default = value,
                update = update
            )
            
        wrapper_annotations = {
            '0' : blender_property
        }
        property_group_params = {
            '__annotations__': wrapper_annotations,
            'tupple_or_struct': "tupple",
            'field_names': ['0'], 
            **dict(with_properties = False, with_items= True, with_enum= False, with_list= False, with_map =False, short_name=wrapper_name, long_name=wrapper_name),
        }
        property_group_class = type(property_group_name, (PropertyGroup,), property_group_params)
        #print(f"property_group_class: {property_group_name} - {property_group_class}")
        bpy.utils.register_class(property_group_class)

        return property_group_class

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

    # export scene to gltf with io_scene_gltf
    def export_scene(self, scene: bpy.types.Scene, settings: Dict[str, Any], gltf_output_path: str):

        # this are our default settings, can be overriden by settings
        #https://docs.blender.org/api/current/bpy.ops.export_scene.html#bpy.ops.export_scene.gltf        
        export_settings = dict(     
            log_info=False, # limit the output, was blowing up my console, requires material-info branch version of the io_scene_gltf
            check_existing=False,

            # export_format= 'GLB', #'GLB', 'GLTF_SEPARATE', 'GLTF_EMBEDDED'
            export_apply=True,
            export_cameras=True,
            export_extras=True, # For custom exported properties.
            export_lights=True,            
            export_yup=True,

            # TODO: add animations back
            export_animations=False,
            #export_draco_mesh_compression_enable=True,
            #export_skins=True,
            #export_morph=False,
            #export_optimize_animation_size=False

            # use only one of these at a time
            use_active_collection_with_nested=True, # these 2
            use_active_collection=True,
            use_active_scene=True, 

            # other filters
            use_selection=False,
            use_visible=False, # Export visible and hidden objects
            use_renderable=False,
            
            #export_attributes=True,
            #export_shared_accessors=True,
            #export_hierarchy_flatten_objs=False, # Explore this more
            #export_texcoords=True, # used by material info and uv sets
            #export_normals=True,
            #export_tangents=False,
            #export_materials
            #export_colors=True,
            #use_mesh_edges
            #use_mesh_vertices
        )        
        export_settings = {
            **export_settings, 
            **settings,
            "filepath": gltf_output_path 
        }
        # we set our active scene to be this one
        bpy.context.window.scene = scene              
        layer_collection = scene.view_layers['ViewLayer'].layer_collection
        bpy.context.view_layer.active_layer_collection = recurLayerCollection(layer_collection, scene.collection.name)
        bpy.ops.export_scene.gltf(**export_settings)

    # TODO: this should also take the split/embed mode into account: if a nested collection changes AND embed is active, its container collection should also be exported
    def get_blueprints_to_export(self, library_scenes: list[bpy.types.Scene]) -> list[Blueprint]:        
        blueprints_to_export = []


        # if the export parameters have changed, bail out early
        # we need to re_export everything if the export parameters have been changed
        # changes_per_scene = {}
        # changed_export_parameters = True
        # if CHANGE_DETECTION and not changed_export_parameters:
        #     changed_blueprints = []

        #     # first check if all collections have already been exported before (if this is the first time the exporter is run
        #     # in your current Blender session for example)       

        #     # check if the blueprints are already on disk
        #     blueprints_not_on_disk = []
        #     for blueprint in self.data.internal_blueprints:
        #         gltf_output_path = os.path.join(self.assets_path, BLUEPRINTS_PATH, blueprint.name + GLTF_EXTENSION)
        #         found = os.path.exists(gltf_output_path) and os.path.isfile(gltf_output_path)
        #         if not found:
        #             blueprints_not_on_disk.append(blueprint)

        #     for scene in library_scenes:
        #         if scene.name in changes_per_scene:
        #             changed_objects = list(changes_per_scene[scene.name].keys())
        #             changed_blueprints = [self.data.blueprints_from_objects[changed] for changed in changed_objects if changed in self.data.blueprints_from_objects]
        #             # we only care about local blueprints/collections
        #             changed_local_blueprints = [blueprint for blueprint in changed_blueprints if blueprint.name in self.data.blueprints_per_name.keys() and blueprint.local]
        #             # FIXME: double check this: why are we combining these two ?
        #             changed_blueprints += changed_local_blueprints

        #     blueprints_to_export = list(set(changed_blueprints + blueprints_not_on_disk))
        # else:
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
                    # combine_mode = blueprint_instance['_combine'] if '_combine' in blueprint_instance else self.collection_instances_combine_mode
                    # if combine_mode == "Split": # we only keep changed blueprints if mode is set to split for at least one instance (aka if ALL instances of a blueprint are merged, do not export ? )  
                    filtered_blueprints.append(blueprint)

            blueprints_to_export =  list(set(filtered_blueprints))
        
        # changed/all blueprints to export     
        return blueprints_to_export

    # set MaterialInfo for export, and returns list of used materials
    def get_all_materials(self, library_scenes) -> list[str]: 
        used_material_names = []
        
        for scene in library_scenes:
            root_collection = scene.collection
            for cur_collection in traverse_tree(root_collection):
                if cur_collection.name in self.data.blueprint_names:
                    for object in cur_collection.all_objects:
                        for m in object.material_slots:            
                            used_material_names.append(m.material.name)            

        used_material_names = list(set(used_material_names))
        return used_material_names

    # create the directories for the exported assets if they do not exist
    def create_dirs(self):
        for path in [LEVELS_PATH, BLUEPRINTS_PATH, MATERIALS_PATH]:
            folder = os.path.join(self.assets_path, path)
            if not os.path.exists(folder):
                os.makedirs(folder)



# https://blender.stackexchange.com/questions/157828/how-to-duplicate-a-certain-collection-using-python
custom_properties_to_filter_out = ['template', 'components_meta']


# will copy the collection without linking, duplicating all objects
# Notes: Instead of just export our existing collection we duplicate here for 2 reason I am aware of:
#    1. We want want to replace collection instances with a blueprint object (valid - TODO: look for any io_scene_gltf setting could handle this)
#    2. remove components_meta from the objects:
#       - we could remove use of components_meta since there should only be one at a time ever for 
#         selected object, story it on BevySettings instead of every select object) (invalid)
#       - without this there is also no need to copy obj data, could stay linked 
# One might say Rename we well, but its only because we are copying its needed
def copy_collection(src_col: bpy.types.Collection, dst_col: bpy.types.Collection):
    # store a mapping of src to duplicated
    object_map: dict[bpy.types.Object, bpy.types.Object] = dict()

    # copy all objects then fixing parenting instead of recursively copying
    for o in src_col.all_objects:
        # this is to cleanup if the last run failed and left some objects with the backup suffix
        if o.name.endswith(NAME_BACKUP_SUFFIX + ".001"): 
            o.name = o.name.replace(NAME_BACKUP_SUFFIX + ".001", "")
        elif o.name.endswith(NAME_BACKUP_SUFFIX):
            o.name = o.name.replace(NAME_BACKUP_SUFFIX, "")
        
        # we need to backup the name, so we can use the name in the export,
        orginal_name = o.name
        o.name = o.name + NAME_BACKUP_SUFFIX

        # for debugging
        #if any(s in src_col.name for s in ["Player", "Tia"]):             
        #    print(f"{src_col.name} - {o.name} - {o.type}")   
                
        # we treat all collection instances as Blueprint        
        dupe = None 
        if o.instance_type == 'COLLECTION':
            # replace with blueprint object
            collection_name = o.instance_collection.name
            dupe = make_empty(orginal_name, o.location, o.rotation_euler, o.scale)                                            
            dupe['BlueprintName'] = '("'+collection_name+'")'                                
            # we copy custom properties over from our original object to our empty
            for property_name, property_value in o.items():
                # bevy_components will be copied, dont need the components_meta
                if property_name == "components_meta":
                    continue                
                #print(f"copy {orginal_name} - {property_name}: {property_value}")                
                # this should copy all custom properties over, include the bevy_components
                dupe[property_name] = property_value     
                # if property_name not in custom_properties_to_filter_out and is_component_valid_and_enabled(o, property_name): #copy only valid properties
                #     empty_obj[property_name] = property_value                    
        else:            
            # copy the object
            dupe = o.copy()
            dupe.name = orginal_name            
            # at the point data is linked, so we need to copy it, 
            if o.data:
                dupe.data = dupe.data.copy()
            

            # remove components_meta
            to_delete = []
            for property_name, property_value in dupe.items():
                if property_name == "components_meta":
                    to_delete.append(property_name)       
                #else:             
                #   print(f"{orginal_name} - {property_name}: {property_value}")

            for property_name in to_delete:
                #print(f"{orginal_name} - deleting {property_name} from copy")
                del dupe[property_name]

        dst_col.objects.link(dupe)
        object_map[o] = dupe

    # now we need to fix the parenting    
    for src_obj, dst_obj in object_map.items():
        p = object_map.get(src_obj.parent)
        if p is not None:
            dst_obj.parent = p

def delete_scene(temp_scene: bpy.types.Scene):
    # remove any data we created        
    for object in temp_scene.collection.all_objects:        
        bpy.data.objects.remove(object, do_unlink=True)
    bpy.data.scenes.remove(temp_scene, do_unlink=True)

# recursively restore original names
def restore_original_names(collection: bpy.types.Collection):
    if collection.name.endswith(NAME_BACKUP_SUFFIX):
        collection.name = collection.name.replace(NAME_BACKUP_SUFFIX, "")
    for object in collection.objects:
        if object.name.endswith(NAME_BACKUP_SUFFIX):
            object.name = object.name.replace(NAME_BACKUP_SUFFIX, "")        
    for child_collection in collection.children:
        restore_original_names(child_collection)