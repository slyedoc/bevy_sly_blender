from bpy.props import (StringProperty, IntProperty, CollectionProperty)

from ..util import VALUE_TYPES_DEFAULTS
from .utils import generate_wrapper_propertyGroup
from . import process_component

def process_list(bevy, definition, update, nesting=[], nesting_long_names=[]):
    
    type_infos = bevy.type_data.type_infos

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
        property_group_class = generate_wrapper_propertyGroup(long_name, item_long_name, definition["items"]["type"]["$ref"], bevy, update)
    else:
        (_, list_content_group_class) = process_component.process_component(bevy, item_definition, update, {"nested": True, "long_name": item_long_name}, nesting)
        property_group_class = list_content_group_class

    item_collection = CollectionProperty(type=property_group_class)

    item_long_name = item_long_name if not is_item_value_type else  "wrapper_" + item_long_name
    __annotations__ = {
        "list": item_collection,
        "list_index": IntProperty(name = "Index for list", default = 0,  update=update),
        "long_name": StringProperty(default=item_long_name)
    }

    return __annotations__