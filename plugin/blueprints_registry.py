from types import SimpleNamespace
import bpy
from bpy.props import (StringProperty, BoolProperty, FloatProperty, FloatVectorProperty, IntProperty, IntVectorProperty, EnumProperty, PointerProperty, CollectionProperty)

from plugin.settings import BevySettings
from plugin.util import EXPORT_MARKED_ASSETS
from .helpers.blueprints import Blueprint, BlueprintData

# this is where we store the information for all available Blueprints
class BlueprintsRegistry(bpy.types.PropertyGroup):
    blueprints_data = BlueprintData
    blueprints_list = [] # not this may be going away

    asset_name_selector: StringProperty(
        name="asset name",
        description="name of asset to add",
    ) # type: ignore

    asset_type_selector: EnumProperty(
        name="asset type",
        description="type of asset to add",
         items=(
                ('MODEL', "Model", ""),
                ('AUDIO', "Audio", ""),
                ('IMAGE', "Image", ""),
                )
    ) # type: ignore

    asset_path_selector: StringProperty(
        name="asset path",
        description="path of asset to add",
        subtype='FILE_PATH'
    ) # type: ignore

    @classmethod
    def register(cls):
        pass

    @classmethod
    def unregister(cls):
        pass

    def add_blueprint(self, blueprint): 
        self.blueprints_list.append(blueprint)

    # blueprints: any collection with either
    # - an instance
    # - marked as asset
    # - with the "auto_export" flag
    # https://blender.stackexchange.com/questions/167878/how-to-get-all-collections-of-the-current-scene
    def scan(self):
        # will update blueprints_data
        bevy = bpy.context.window_manager.bevy # type: BevySettings
        [level_names, main_scenes, library_scene_names, library_scenes] = bevy.get_scenes()

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

        self.blueprints_data = BlueprintData(
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
        
        # data = {
        #     "blueprints": blueprints,
        #     "blueprints_per_name": blueprints_per_name,
        #     "blueprint_names": list(blueprints_per_name.keys()),
        #     "blueprints_from_objects": blueprints_from_objects,

        #     "internal_blueprints": internal_blueprints,
        #     "external_blueprints": external_blueprints,
        #     "blueprints_per_scenes": blueprints_per_scenes,

        #     "blueprint_instances_per_main_scene": blueprint_instances_per_main_scene,
        #     "blueprint_instances_per_library_scene": blueprint_instances_per_library_scene,

        #     # not sure about these two
        #     "internal_collection_instances": internal_collection_instances,
        #     "external_collection_instances": external_collection_instances,

        #     "blueprint_name_from_instances": blueprint_name_from_instances
        # }
