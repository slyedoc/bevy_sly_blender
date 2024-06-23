from bpy_types import PropertyGroup
import re

from .util import VALUE_TYPES_DEFAULTS

def parse_struct_string(string, start_nesting=0):
    #print("processing struct string", string, "start_nesting", start_nesting)
    fields = {}
    buff = []
    current_fieldName = None
    nesting_level = 0 

    start_offset = 0
    end_offset = 0

    for index, char in enumerate(string):
        buff.append(char)
        if char == "," and nesting_level == start_nesting:
            #print("first case", end_offset)
            end_offset = index
            end_offset = len(string) if end_offset == 0 else end_offset

            val = "".join(string[start_offset:end_offset])
            fields[current_fieldName] = val.strip()
            start_offset = index + 1
            #print("done with field name", current_fieldName, "value", fields[current_fieldName])

        if char == "[" or char == "(":
            nesting_level  += 1
            if nesting_level == start_nesting:
                start_offset = index + 1 
                #print("nesting & setting start offset", start_offset)
            #print("nesting down", nesting_level)

        if char == "]" or char == ")" :
            #print("nesting up", nesting_level)
            if nesting_level == start_nesting:
                end_offset = index
                #print("unesting & setting end offset", end_offset)
            nesting_level  -= 1


        if char == ":" and nesting_level == start_nesting:
            end_offset = index
            fieldName = "".join(string[start_offset:end_offset])
            current_fieldName = fieldName.strip()
            start_offset = index + 1
            end_offset = 0 #hack
            #print("starting field name", fieldName, "index", index)
            buff = []
            
    end_offset = len(string) if end_offset == 0 else end_offset
    #print("final start and end offset", start_offset, end_offset, "total length", len(string))

    val = "".join(string[start_offset:end_offset])

    fields[current_fieldName] = val.strip()
    #print("done with all fields", fields)
    return fields

def parse_tuplestruct_string(string, start_nesting=0):
    #print("processing tuppleStruct", string, "start_nesting", start_nesting)
    fields = []
    buff = []
    nesting_level = 0 
    field_index = 0

    start_offset = 0
    end_offset = 0
    # todo: strip all stuff before start_nesting

    for index, char in enumerate(string):
        buff.append(char)
        if char == "," and nesting_level == start_nesting:
            end_offset = index
            end_offset = len(string) if end_offset == 0 else end_offset

            val = "".join(string[start_offset:end_offset])
            fields.append(val.strip())
            field_index += 1
            #print("start and end offset", start_offset, end_offset, "total length", len(string))
            #print("done with field name", field_index, "value", fields)
            start_offset = index + 1
            end_offset = 0 # hack

        if char == "[" or char == "(":
            nesting_level  += 1
            if nesting_level == start_nesting:
                start_offset = index + 1 
                #print("nesting & setting start offset", start_offset)
            #print("nesting down", nesting_level)

        if char == "]" or char == ")" :
            if nesting_level == start_nesting:
                end_offset = index
                #print("unesting & setting end offset", end_offset)
            #print("nesting up", nesting_level)
            nesting_level  -= 1


    end_offset = len(string) if end_offset == 0 else end_offset
    #print("final start and end offset", start_offset, end_offset, "total length", len(string))

    val = "".join(string[start_offset:end_offset]) #if end_offset != 0 else buff)
    fields.append(val.strip())
    fields = list(filter(lambda entry: entry != '', fields))
    #print("done with all fields", fields)
    return fields


def parse_vec2(value, caster, typeName):
    parsed = parse_struct_string(value.replace(typeName,"").replace("(", "").replace(")","") )
    return [caster(parsed['x']), caster(parsed['y'])]

def parse_vec3(value, caster, typeName):
    parsed = parse_struct_string(value.replace(typeName,"").replace("(", "").replace(")","") )
    return [caster(parsed['x']), caster(parsed['y']), caster(parsed['z'])]

def parse_vec4(value, caster, typeName):
    parsed = parse_struct_string(value.replace(typeName,"").replace("(", "").replace(")","") )
    return [caster(parsed['x']), caster(parsed['y']), caster(parsed['z']), caster(parsed['w'])]

def parse_color(value, caster, typeName):
    parsed = parse_struct_string(value.replace(typeName,"").replace("(", "").replace(")","") )
    return [caster(parsed['red']), caster(parsed['green']), caster(parsed['blue']), caster(parsed['alpha'])]

def to_int(input):
    return int(float(input))



def is_def_value_type(definition):
    if definition == None:
        return True    
    long_name = definition["long_name"]
    is_value_type = long_name in VALUE_TYPES_DEFAULTS
    return is_value_type

type_mappings = {
    "bool": lambda value: True if value == "true" else False,

    "u8": lambda value: int(value),
    "u16": lambda value: int(value),
    "u32": lambda value: int(value),
    "u64": lambda value: int(value),
    "u128": lambda value: int(value),
    "u64": lambda value: int(value),
    "usize": lambda value: int(value),

    "i8": lambda value: int(value),
    "i16": lambda value: int(value),
    "i32": lambda value: int(value),
    "i64": lambda value: int(value),
    "i128": lambda value: int(value),
    "isize": lambda value: int(value),

    'f32': lambda value: float(value),
    'f64': lambda value: float(value),

    "glam::Vec2": lambda value: parse_vec2(value, float, "Vec2"),
    "glam::DVec2": lambda value: parse_vec2(value, float, "DVec2"),
    "glam::UVec2": lambda value: parse_vec2(value, to_int, "UVec2"),

    'glam::Vec3': lambda value: parse_vec3(value, float, "Vec3"),
    "glam::Vec3A": lambda value: parse_vec3(value, float, "Vec3A"),
    "glam::UVec3": lambda value: parse_vec3(value, to_int, "UVec3"),

    "glam::Vec4": lambda value: parse_vec4(value, float, "Vec4"),
    "glam::DVec4": lambda value: parse_vec4(value, float, "DVec4"),
    "glam::UVec4": lambda value: parse_vec4(value, to_int, "UVec4"),

    "glam::Quat": lambda value: parse_vec4(value, float, "Quat"),

    'alloc::string::String': lambda value: str(value.replace('"', "")),
    'alloc::borrow::Cow<str>': lambda value: str(value.replace('"', "")),

    'bevy_render::color::Color': lambda value: parse_color(value, float, "Rgba"),
    'bevy_ecs::entity::Entity': lambda value: int(value),
}

conversion_tables = {
    "bool": lambda value: value,

    "char": lambda value: '"'+value+'"',
    "str": lambda value: '"'+value+'"',
    "alloc::string::String": lambda value: '"'+str(value)+'"',
    "alloc::borrow::Cow<str>": lambda value: '"'+str(value)+'"',

    "glam::Vec2": lambda value: "Vec2(x:"+str(value[0])+ ", y:"+str(value[1])+")",
    "glam::DVec2": lambda value: "DVec2(x:"+str(value[0])+ ", y:"+str(value[1])+")",
    "glam::UVec2": lambda value: "UVec2(x:"+str(value[0])+ ", y:"+str(value[1])+")",

    "glam::Vec3": lambda value: "Vec3(x:"+str(value[0])+ ", y:"+str(value[1])+ ", z:"+str(value[2])+")",
    "glam::Vec3A": lambda value: "Vec3A(x:"+str(value[0])+ ", y:"+str(value[1])+ ", z:"+str(value[2])+")",
    "glam::UVec3": lambda value: "UVec3(x:"+str(value[0])+ ", y:"+str(value[1])+ ", z:"+str(value[2])+")",

    "glam::Vec4": lambda value: "Vec4(x:"+str(value[0])+ ", y:"+str(value[1])+ ", z:"+str(value[2])+ ", w:"+str(value[3])+")",
    "glam::DVec4": lambda value: "DVec4(x:"+str(value[0])+ ", y:"+str(value[1])+ ", z:"+str(value[2])+ ", w:"+str(value[3])+")",
    "glam::UVec4": lambda value: "UVec4(x:"+str(value[0])+ ", y:"+str(value[1])+ ", z:"+str(value[2])+ ", w:"+str(value[3])+")",

    "glam::Quat":  lambda value: "Quat(x:"+str(value[0])+ ", y:"+str(value[1])+ ", z:"+str(value[2])+ ", w:"+str(value[3])+")",

    "bevy_render::color::Color": lambda value: "Rgba(red:"+str(value[0])+ ", green:"+str(value[1])+ ", blue:"+str(value[2])+ ", alpha:"+str(value[3])+   ")",
}