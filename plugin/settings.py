import json
import bpy
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any

from bpy.props import (BoolProperty, StringProperty, CollectionProperty, IntProperty, PointerProperty, EnumProperty)

from plugin.helpers.generate_and_export import generate_and_export
from plugin.helpers.helpers_scenes import clear_hollow_scene, copy_hollowed_collection_into

from .util import BLUEPRINTS_PATH, EXPORT_MARKED_ASSETS, EXPORT_MATERIALS_LIBRARY, SETTING_NAME, TEMPSCENE_PREFIX

class SceneSelector(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty() # type: ignore
    display: bpy.props.BoolProperty() # type: ignore

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

# auto save to a text datablock
# TODO: serialized manually feels stupid
def save_settings(self, context):
    json_str = json.dumps({ 
        'mode': self.mode,
        'schema_file': self.schema_file,
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
    return None        
 
class BevySettings(bpy.types.PropertyGroup):   
    #
    # Blueprint Data
    #
    data = BlueprintData
    blueprints_list = [] # not this may be going away
    
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
    schema_file: StringProperty(
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
    # TODO: ui disabled for this, right now assuming default
    collection_instances_combine_mode : EnumProperty(
        name='Collection instances',
        items=(
           ('Split', 'Split', 'replace collection instances with an empty + blueprint, creating links to sub blueprints (Default, Recomended)'),
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

    # not sure where i will put this
    def generate_gltf_export_preferences(self): 
        # default values
        #https://docs.blender.org/api/current/bpy.ops.export_scene.html#bpy.ops.export_scene.gltf
        gltf_export_preferences = dict(
            # export_format= 'GLB', #'GLB', 'GLTF_SEPARATE', 'GLTF_EMBEDDED'
            check_existing=False,

            use_selection=False,
            use_visible=True, # Export visible and hidden objects. See Object/Batch Export to skip.
            use_renderable=False,
            use_active_collection= False,
            use_active_collection_with_nested=False,
            use_active_scene = False,

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
            
        # for key in self.__annotations__.keys():
        #     if str(key) not in AutoExportGltfPreferenceNames:
        #         #print("overriding setting", key, "value", getattr(addon_prefs,key))
        #         gltf_export_preferences[key] = getattr(addon_prefs, key)

        # standard_gltf_exporter_settings = bpy.data.texts[".gltf_auto_export_gltf_settings"] if ".gltf_auto_export_gltf_settings" in bpy.data.texts else None
        # if standard_gltf_exporter_settings != None:
        #     try:
        #         standard_gltf_exporter_settings = json.loads(standard_gltf_exporter_settings.as_string())
        #     except:
        #         standard_gltf_exporter_settings = {}
        # else:
        #     standard_gltf_exporter_settings = {}

        # constant_keys = [
        #     'use_selection',
        #     'use_visible',
        #     'use_active_collection',
        #     'use_active_collection_with_nested',
        #     'use_active_scene',
        #     'export_cameras',
        #     'export_extras', # For custom exported properties.
        #     'export_lights',
        # ]

        # # a certain number of essential params should NEVER be overwritten , no matter the settings of the standard exporter
        # for key in standard_gltf_exporter_settings.keys():
        #     if str(key) not in constant_keys:
        #         gltf_export_preferences[key] =  standard_gltf_exporter_settings.get(key)
        return gltf_export_preferences

    def load_settings(self):
        stored_settings = bpy.data.texts[SETTING_NAME] if SETTING_NAME in bpy.data.texts else None        
        if stored_settings != None:
            settings =  json.loads(stored_settings.as_string())        
            for prop in ['assets_path', 'schema_file', 'auto_export', 'mode']:
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

        # save the setting back, so its updated if need be, or default added if need be
        save_settings(self, bpy.context)

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

    def export_blueprints(self, blueprints):
        gltf_export_preferences = self.generate_gltf_export_preferences()
        
        try:
            # save current active collection
            active_collection =  bpy.context.view_layer.active_layer_collection

            for blueprint in blueprints:
                print("exporting collection", blueprint.name)
                gltf_output_path = os.path.join(self.assets_path, BLUEPRINTS_PATH, blueprint.name)
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
                    tempScene_filler= lambda temp_collection: copy_hollowed_collection_into(collection, temp_collection, blueprints_data=self.data),
                    tempScene_cleaner= lambda temp_scene, params: clear_hollow_scene(original_root_collection=collection, temp_scene=temp_scene)
                )

            # reset active collection to the one we save before
            bpy.context.view_layer.active_layer_collection = active_collection

        except Exception as error:
            print("failed to export collections to gltf: ", error)
            raise error