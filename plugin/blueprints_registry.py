from types import SimpleNamespace
import bpy
from bpy.props import (StringProperty, BoolProperty, FloatProperty, FloatVectorProperty, IntProperty, IntVectorProperty, EnumProperty, PointerProperty, CollectionProperty)

from .helpers.helpers_scenes import get_scenes
from .helpers.blueprints import blueprints_scan

# this is where we store the information for all available Blueprints
class BlueprintsRegistry(bpy.types.PropertyGroup):
    blueprints_data = {}
    blueprints_list = []

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
        return

    @classmethod
    def unregister(cls):
        return

    def add_blueprint(self, blueprint): 
        self.blueprints_list.append(blueprint)

    def add_blueprints_data(self):
        [main_scene_names, level_scenes, library_scene_names, library_scenes] = get_scenes()
        blueprints_data = blueprints_scan(level_scenes, library_scenes)
        self.blueprints_data = blueprints_data
