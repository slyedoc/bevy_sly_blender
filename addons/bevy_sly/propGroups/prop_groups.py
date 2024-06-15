import bpy


from .conversions_from_prop_group import property_group_value_to_custom_property_value
from .process_component import process_component
from .utils import update_calback_helper

import json
## main callback function, fired whenever any property changes, no matter the nesting level
def update_component(self, context, definition, component_name):
    bevy = bpy.context.window_manager.bevy ## type: BevySettings
    current_object = bpy.context.object
    update_disabled = current_object["__disable__update"] if "__disable__update" in current_object else False
    update_disabled = bevy.disable_all_object_updates or update_disabled # global settings
    if update_disabled:
        return
    print("")
    print("update in component", component_name, self, "current_object", current_object.name)
    components_in_object = current_object.components_meta.components
    component_meta =  next(filter(lambda component: component["long_name"] == component_name, components_in_object), None)

    if component_meta != None:
        property_group_name = bevy.type_data.long_names_to_propgroup_names.get(component_name, None)
        property_group = getattr(component_meta, property_group_name)
        # we use our helper to set the values
        object = context.object
        previous = json.loads(object['bevy_components'])
        previous[component_name] = property_group_value_to_custom_property_value(property_group, definition, bevy, None)
        object['bevy_components'] = json.dumps(previous)

