import bpy
import json

from bpy.props import (StringProperty, BoolProperty, PointerProperty)
from bpy_types import (PropertyGroup)

class ComponentMetadata(bpy.types.PropertyGroup):
    short_name : bpy.props.StringProperty(
        name = "name",
        default = ""
    ) # type: ignore

    long_name : bpy.props.StringProperty(
        name = "long name",
        default = ""
    ) # type: ignore

    values: bpy.props.StringProperty(
        name = "Value",
        default = ""
    ) # type: ignore

    enabled: BoolProperty(
        name="enabled",
        description="component enabled",
        default=True
    ) # type: ignore

    invalid: BoolProperty(
        name="invalid",
        description="component is invalid, because of missing registration/ other issues",
        default=False
    ) # type: ignore

    invalid_details: StringProperty(
        name="invalid details",
        description="detailed information about why the component is invalid",
        default=""
    ) # type: ignore

    visible: BoolProperty( # REALLY dislike doing this for UI control, but ok hack for now
        default=True
    ) # type: ignore

class ComponentsMeta(PropertyGroup):
    components: bpy.props.CollectionProperty(type = ComponentMetadata)  # type: ignore

    @classmethod
    def register(cls):
        return

    @classmethod
    def unregister(cls):
        return

# remove no longer valid metadata from object
def cleanup_invalid_metadata(object):
    bevy_components = get_bevy_components(object)
    if len(bevy_components.keys()) == 0: # no components, bail out
        return
    components_metadata = object.components_meta.components
    to_remove = []
    for index, component_meta in enumerate(components_metadata):
        long_name = component_meta.long_name
        if long_name not in bevy_components.keys():
            print("component:", long_name, "present in metadata, but not in object")
            to_remove.append(index)
    for index in to_remove:
        components_metadata.remove(index)


def upsert_bevy_component(object, long_name: str, value):
    if not 'bevy_components' in object:
        object['bevy_components'] = '{}'
    bevy_components = json.loads(object['bevy_components'])
    bevy_components[long_name] = value
    object['bevy_components'] = json.dumps(bevy_components)
    #object['bevy_components'][long_name] = value # Sigh, this does not work, hits Blender's 63 char length limit

def remove_bevy_component(object, long_name):
    if 'bevy_components' in object:
        bevy_components = json.loads(object['bevy_components'])
        if long_name in bevy_components:
            del bevy_components[long_name]
            object['bevy_components'] = json.dumps(bevy_components)
    if long_name in object:
        del object[long_name]

def get_bevy_components(object):
    if 'bevy_components' in object:
        bevy_components = json.loads(object['bevy_components'])
        return bevy_components
    return {}

def get_bevy_component_value_by_long_name(object, long_name: str):
    bevy_components = get_bevy_components(object)
    if len(bevy_components.keys()) == 0 :
        return None
    return bevy_components.get(long_name, None)

def is_bevy_component_in_object(object, long_name):
    return get_bevy_component_value_by_long_name(object, long_name) is not None
       
# removes the given component from the object: removes both the custom property and the matching metadata from the object
def remove_component_from_object(object, component_name):
    # remove the component value
    remove_bevy_component(object, component_name)

    # now remove the component's metadata
    components_metadata = getattr(object, "components_meta", None)
    if components_metadata == None:
        return False
    
    components_metadata = components_metadata.components
    to_remove = []
    for index, component_meta in enumerate(components_metadata):
        long_name = component_meta.long_name
        if long_name == component_name:
            to_remove.append(index)
            break
    for index in to_remove:
        components_metadata.remove(index)
    return True

def toggle_component(object, component_name):
    components_in_object = object.components_meta.components
    component_meta =  next(filter(lambda component: component["long_name"] == component_name, components_in_object), None)
    if component_meta != None: 
        component_meta.visible = not component_meta.visible
