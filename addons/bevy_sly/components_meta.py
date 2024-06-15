import bpy
import json

from bpy.props import (StringProperty, BoolProperty, PointerProperty)
from bpy_types import (PropertyGroup)

from .propGroups.conversions_from_prop_group import property_group_value_to_custom_property_value
from .propGroups.conversions_to_prop_group import property_group_value_from_custom_property_value

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
    infos_per_component:  StringProperty(
        name="infos per component",
        description="component"
    ) # type: ignore
    components: bpy.props.CollectionProperty(type = ComponentMetadata)  # type: ignore

    @classmethod
    def register(cls):
        return
        #bpy.types.Object.components_meta = PointerProperty(type=ComponentsMeta)

    @classmethod
    def unregister(cls):
        return
        #del bpy.types.Object.components_meta

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


def upsert_bevy_component(object, long_name, value):
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

def get_bevy_component_value_by_long_name(object, long_name):
    bevy_components = get_bevy_components(object)
    if len(bevy_components.keys()) == 0 :
        return None
    return bevy_components.get(long_name, None)

def is_bevy_component_in_object(object, long_name):
    return get_bevy_component_value_by_long_name(object, long_name) is not None

# adds metadata to object only if it is missing
def add_metadata_to_components_without_metadata(object):
    bevy = bpy.context.window_manager.bevy

    for component_name in get_bevy_components(object) :
        if component_name == "components_meta":
            continue
        upsert_component_in_object(object, component_name, bevy)
                    
# adds a component to an object (including metadata) using the provided component definition & optional value
def add_component_to_object(object, component_definition, value=None):
    cleanup_invalid_metadata(object)
    if object is not None:
        # print("add_component_to_object", component_definition)
        long_name = component_definition["long_name"]
        bevy = bpy.context.window_manager.bevy
        if not bevy.has_type_infos():
            raise Exception('registry type infos have not been loaded yet or are missing !')
        definition = bevy.type_data.type_infos[long_name]
        # now we use our pre_generated property groups to set the initial value of our custom property
        (_, propertyGroup) = upsert_component_in_object(object, long_name=long_name, bevy=bevy)
        if value == None:
            value = property_group_value_to_custom_property_value(propertyGroup, definition, bevy, None)
        else: # we have provided a value, that is a raw , custom property value, to set the value of the propertyGroup
            object["__disable__update"] = True # disable update callback while we set the values of the propertyGroup "tree" (as a propertyGroup can contain other propertyGroups) 
            property_group_value_from_custom_property_value(propertyGroup, definition, bevy, value)
            del object["__disable__update"]

        upsert_bevy_component(object, long_name, value)
       
def upsert_component_in_object(object, long_name, bevy):
    # print("upsert_component_in_object", object, "component name", component_name)
    # TODO: upsert this part too ?
    target_components_metadata = object.components_meta.components
    component_definition = bevy.type_data.type_infos.get(long_name, None)
    if component_definition != None:
        short_name = component_definition["short_name"]
        long_name = component_definition["long_name"]
        property_group_name = bevy.type_data.long_names_to_propgroup_names.get(long_name, None)
        propertyGroup = None

        component_meta = next(filter(lambda component: component["long_name"] == long_name, target_components_metadata), None)
        if not component_meta:
            component_meta = target_components_metadata.add()
            component_meta.short_name = short_name
            component_meta.long_name = long_name
            propertyGroup = getattr(component_meta, property_group_name, None)
        else: # this one has metadata but we check that the relevant property group is present
            propertyGroup = getattr(component_meta, property_group_name, None)

        # try to inject propertyGroup if not present
        if propertyGroup == None:
            #print("propertygroup not found in metadata attempting to inject")
            if property_group_name in bevy.type_data.component_propertyGroups:
                # we have found a matching property_group, so try to inject it
                # now inject property group
                setattr(ComponentMetadata, property_group_name, bevy.type_data.component_propertyGroups[property_group_name]) # FIXME: not ideal as all ComponentMetadata get the propGroup, but have not found a way to assign it per instance
                propertyGroup = getattr(component_meta, property_group_name, None)
        
        # now deal with property groups details
        if propertyGroup != None:
            if long_name in bevy.type_data.invalid_components:
                component_meta.enabled = False
                component_meta.invalid = True
                component_meta.invalid_details = "component contains fields that are not in the registry, disabling"
        else:
            # if we still have not found the property group, mark it as invalid
            component_meta.enabled = False
            component_meta.invalid = True
            component_meta.invalid_details = "component not present in the registry, possibly renamed? Disabling for now"
        # property_group_value_from_custom_property_value(propertyGroup, component_definition, registry, object[component_name])

        return (component_meta, propertyGroup)
    else:
        return(None, None)


def copy_propertyGroup_values_to_another_object(source_object, target_object, component_name, bevy):
    if source_object == None or target_object == None or component_name == None:
        raise Exception('missing input data, cannot copy component propertryGroup')
    
    component_definition = bevy.type_data.type_infos.get(component_name, None)
    long_name = component_name
    property_group_name = bevy.self.type_data.long_names_to_propgroup_names.get(long_name, None)

    source_components_metadata = source_object.components_meta.components
    source_componentMeta = next(filter(lambda component: component["long_name"] == long_name, source_components_metadata), None)
    # matching component means we already have this type of component 
    source_propertyGroup = getattr(source_componentMeta, property_group_name)

    # now deal with the target object
    (_, target_propertyGroup) = upsert_component_in_object(target_object, component_name, bevy)
    # add to object
    value = property_group_value_to_custom_property_value(target_propertyGroup, component_definition, bevy, None)
    upsert_bevy_component(target_object, long_name, value)

    # copy the values over 
    for field_name in source_propertyGroup.field_names:
        if field_name in source_propertyGroup:
            target_propertyGroup[field_name] = source_propertyGroup[field_name]
    apply_propertyGroup_values_to_object_customProperties(target_object, bevy)


# TODO: move to propgroups ?
def apply_propertyGroup_values_to_object_customProperties(object, bevy):
    cleanup_invalid_metadata(object)
    for component_name in get_bevy_components(object) :
        """if component_name == "components_meta":
            continue"""
        (_, propertyGroup) =  upsert_component_in_object(object, component_name, bevy)
        component_definition = bevy.type_data.type_infos.get(component_name, None)
        if component_definition != None:
            value = property_group_value_to_custom_property_value(propertyGroup, component_definition, bevy, None)
            upsert_bevy_component(object=object, long_name=component_name, value=value)

# apply component value(s) to custom property of a single component
def apply_propertyGroup_values_to_object_customProperties_for_component(object, component_name):
    bevy = bpy.context.window_manager.bevy
    (_, propertyGroup) =  upsert_component_in_object(object, component_name, bevy)
    component_definition = bevy.type_data.type_infos.get(component_name, None)
    if component_definition != None:
        value = property_group_value_to_custom_property_value(propertyGroup, component_definition, bevy, None)
        object[component_name] = value
    
    components_metadata = object.components_meta.components
    componentMeta = next(filter(lambda component: component["long_name"] == component_name, components_metadata), None)
    if componentMeta:
        componentMeta.invalid = False
        componentMeta.invalid_details = ""


def apply_customProperty_values_to_object_propertyGroups(object):
    print("apply custom properties to ", object.name)
    bevy = bpy.context.window_manager.bevy
    for component_name in get_bevy_components(object) :
        if component_name == "components_meta":
            continue
        component_definition = bevy.type_data.type_infos.get(component_name, None)
        if component_definition != None:
            property_group_name = bevy.self.type_data.long_names_to_propgroup_names.get(component_name, None)
            components_metadata = object.components_meta.components
            source_componentMeta = next(filter(lambda component: component["long_name"] == component_name, components_metadata), None)
            # matching component means we already have this type of component 
            propertyGroup = getattr(source_componentMeta, property_group_name, None)
            customProperty_value = get_bevy_component_value_by_long_name(object, component_name)
            #value = property_group_value_to_custom_property_value(propertyGroup, component_definition, registry, None)
            
            object["__disable__update"] = True # disable update callback while we set the values of the propertyGroup "tree" (as a propertyGroup can contain other propertyGroups) 
            property_group_value_from_custom_property_value(propertyGroup, component_definition, bevy, customProperty_value)
            del object["__disable__update"]
            source_componentMeta.invalid = False
            source_componentMeta.invalid_details = ""

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

def add_component_from_custom_property(object):
    add_metadata_to_components_without_metadata(object)
    apply_customProperty_values_to_object_propertyGroups(object)

def rename_component(object, original_long_name, new_long_name):
    bevy = bpy.context.window_manager.bevy
    type_infos = bevy.type_data.type_infos
    component_definition = type_infos[new_long_name]

    component_ron_value = get_bevy_component_value_by_long_name(object=object, long_name=original_long_name)
    if component_ron_value is None and original_long_name in object:
        component_ron_value = object[original_long_name]

    remove_component_from_object(object, original_long_name)
    add_component_to_object(object, component_definition, component_ron_value)


def toggle_component(object, component_name):
    components_in_object = object.components_meta.components
    component_meta =  next(filter(lambda component: component["long_name"] == component_name, components_in_object), None)
    if component_meta != None: 
        component_meta.visible = not component_meta.visible
