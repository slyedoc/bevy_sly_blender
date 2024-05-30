from bpy.props import (StringProperty)

from ..util import BLENDER_PROPERTY_MAPPING, VALUE_TYPES_DEFAULTS
from . import process_component

def process_tupples(bevy, definition, prefixItems, update, nesting=[], nesting_long_names=[]):
    type_infos = bevy.type_data.type_infos
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
                        update= update
                    )
                  
                    __annotations__[property_name] = blender_property
            else:
                original_long_name = original["long_name"]
                (sub_component_group, _) = process_component.process_component(bevy, original, update, {"nested": True, "long_name": original_long_name}, nesting)
                __annotations__[property_name] = sub_component_group
        else: 
            # component not found in type_infos, generating placeholder
            __annotations__[property_name] = StringProperty(default="N/A")
            bevy.add_missing_typeInfo(ref_name)
            # the root component also becomes invalid (in practice it is not always a component, but good enough)
            bevy.add_invalid_component(nesting_long_names[0])


    return __annotations__

