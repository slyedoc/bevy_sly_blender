# helper function that returns a lambda, used for the PropertyGroups update function
def update_calback_helper(definition, update, component_name_override):
    return lambda self, context: update(self, context, definition, component_name_override)

import bpy
from bpy.props import (StringProperty)
from bpy_types import PropertyGroup

from ..util import BLENDER_PROPERTY_MAPPING, VALUE_TYPES_DEFAULTS

# this helper creates a "fake"/wrapper property group that is NOT a real type in the registry
# usefull for things like value types in list items etc
def generate_wrapper_propertyGroup(wrapped_type_long_name_name, item_long_name, definition_link, registry, update):
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
    property_group_name = registry.generate_propGroup_name(nesting=[], longName=wrapper_name)
    registry.add_custom_type(wrapper_name, wrapper_definition)


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
    bpy.utils.register_class(property_group_class)

    return property_group_class