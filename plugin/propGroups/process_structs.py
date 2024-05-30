from bpy.props import (StringProperty)

from ..util import BLENDER_PROPERTY_MAPPING, VALUE_TYPES_DEFAULTS
from . import process_component

def process_structs(bevy, definition, properties, update, nesting, nesting_long_names): 
    type_infos = bevy.type_data.type_infos
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
                        name = property_name,
                        default = value,
                        update = update
                    )
                    __annotations__[property_name] = blender_property
            else:
                original_long_name = original["long_name"]
                (sub_component_group, _) = process_component.process_component(bevy, original, update, {"nested": True, "long_name": original_long_name}, nesting, nesting_long_names)
                __annotations__[property_name] = sub_component_group
        # if there are sub fields, add an attribute "sub_fields" possibly a pointer property ? or add a standard field to the type , that is stored under "attributes" and not __annotations (better)
        else:
            # component not found in type_infos, generating placeholder
            __annotations__[property_name] = StringProperty(default="N/A")
            bevy.add_missing_typeInfo(ref_name)
            # the root component also becomes invalid (in practice it is not always a component, but good enough)
            bevy.add_invalid_component(nesting_long_names[0])

    return __annotations__
