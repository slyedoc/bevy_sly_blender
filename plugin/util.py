import uuid
import bpy
import os
import rna_prop_ui


from bpy.props import (BoolProperty, StringProperty, CollectionProperty, IntProperty, PointerProperty, EnumProperty, FloatProperty,FloatVectorProperty )


# TODO: settings that maybe should just be the default
# can move to setttings if really needed
SETTING_NAME = ".bevy_settings"

EXPORT_MARKED_ASSETS = True
#EXPORT_BLUEPRINTS = Only True - Not longer an option
EXPORT_STATIC_DYNAMIC = False # dont use this yet
EXPORT_SCENE_SETTINGS = True
CHANGE_DETECTION = True

GLTF_EXTENSION = ".glb" #".gltf"
TEMPSCENE_PREFIX = "__temp_scene"

BLUEPRINTS_PATH = "blueprints"
LEVELS_PATH = "levels"
MATERIALS_PATH = "materials"


BLENDER_PROPERTY_MAPPING = {
    "bool": dict(type=BoolProperty, presets=dict()),

    "u8": dict(type=IntProperty, presets=dict(min=0, max=255)),
    "u16": dict(type=IntProperty, presets=dict(min=0, max=65535)),
    "u32": dict(type=IntProperty, presets=dict(min=0)),
    "u64": dict(type=IntProperty, presets=dict(min=0)),
    "u128": dict(type=IntProperty, presets=dict(min=0)),
    "u64": dict(type=IntProperty, presets=dict(min=0)),
    "usize": dict(type=IntProperty, presets=dict(min=0)),

    "i8": dict(type=IntProperty, presets=dict()),
    "i16":dict(type=IntProperty, presets=dict()),
    "i32":dict(type=IntProperty, presets=dict()),
    "i64":dict(type=IntProperty, presets=dict()),
    "i128":dict(type=IntProperty, presets=dict()),
    "isize": dict(type=IntProperty, presets=dict()),

    "f32": dict(type=FloatProperty, presets=dict()),
    "f64": dict(type=FloatProperty, presets=dict()),

    "glam::Vec2": {"type": FloatVectorProperty, "presets": dict(size = 2) },
    "glam::DVec2": {"type": FloatVectorProperty, "presets": dict(size = 2) },
    "glam::UVec2": {"type": FloatVectorProperty, "presets": dict(size = 2) },

    "glam::Vec3": {"type": FloatVectorProperty, "presets": {"size":3} },
    "glam::Vec3A":{"type": FloatVectorProperty, "presets": {"size":3} },
    "glam::DVec3":{"type": FloatVectorProperty, "presets": {"size":3} },
    "glam::UVec3":{"type": FloatVectorProperty, "presets": {"size":3} },

    "glam::Vec4": {"type": FloatVectorProperty, "presets": {"size":4} },
    "glam::Vec4A": {"type": FloatVectorProperty, "presets": {"size":4} },
    "glam::DVec4": {"type": FloatVectorProperty, "presets": {"size":4} },
    "glam::UVec4":{"type": FloatVectorProperty, "presets": {"size":4, "min":0.0} },

    "glam::Quat": {"type": FloatVectorProperty, "presets": {"size":4} },

    "bevy_render::color::Color": dict(type = FloatVectorProperty, presets=dict(subtype='COLOR', size=4)),

    "char": dict(type=StringProperty, presets=dict()),
    "str":  dict(type=StringProperty, presets=dict()),
    "alloc::string::String":  dict(type=StringProperty, presets=dict()),
    "alloc::borrow::Cow<str>": dict(type=StringProperty, presets=dict()),


    "enum":  dict(type=EnumProperty, presets=dict()), 

    'bevy_ecs::entity::Entity': {"type": IntProperty, "presets": {"min":0} },
    'bevy_utils::Uuid':  dict(type=StringProperty, presets=dict()),

}

VALUE_TYPES_DEFAULTS = {
    "string":" ",
    "boolean": True,
    "float": 0.0,
    "uint": 0,
    "int":0,

    # todo : we are re-doing the work of the bevy /rust side here, but it seems more pratical to alway look for the same field name on the blender side for matches
    "bool": True,

    "u8": 0,
    "u16":0,
    "u32":0,
    "u64":0,
    "u128":0,
    "usize":0,

    "i8": 0,
    "i16":0,
    "i32":0,
    "i64":0,
    "i128":0,
    "isize":0,

    "f32": 0.0,
    "f64":0.0,

    "char": " ",
    "str": " ",
    "alloc::string::String": " ",
    "alloc::borrow::Cow<str>":  " ",

    "glam::Vec2": [0.0, 0.0],
    "glam::DVec2":  [0.0, 0.0],
    "glam::UVec2": [0, 0],

    "glam::Vec3": [0.0, 0.0, 0.0],
    "glam::Vec3A":[0.0, 0.0, 0.0],
    "glam::UVec3": [0, 0, 0],

    "glam::Vec4": [0.0, 0.0, 0.0, 0.0], 
    "glam::DVec4": [0.0, 0.0, 0.0, 0.0], 
    "glam::UVec4": [0, 0, 0, 0], 

    "glam::Quat":  [0.0, 0.0, 0.0, 0.0], 

    "bevy_render::color::Color": [1.0, 1.0, 0.0, 1.0],

    'bevy_ecs::entity::Entity': 0,#4294967295, # this is the same as Bevy's Entity::Placeholder, too big for Blender..sigh
    'bevy_utils::Uuid': '"'+str(uuid.uuid4())+'"'

}

# fake way to make our operator's changes be visible to the change/depsgraph update handler in gltf_auto_export
def ping_depsgraph_update(object):
    rna_prop_ui.rna_idprop_ui_create(object, "________temp", default=0)
    rna_prop_ui.rna_idprop_ui_prop_clear(object, "________temp")

def absolute_path_from_blend_file(path):
    # path to the current blend file
    blend_file_path = bpy.data.filepath
    # Get the folder
    blend_file_folder_path = os.path.dirname(blend_file_path) 

    # absolute path
    return os.path.abspath(os.path.join(blend_file_folder_path, path))
