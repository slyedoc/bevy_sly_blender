import bpy

from .object_makers import make_empty

# Create custom compoents based on the scene settings
def add_scene_settings(scene: bpy.types.Scene):
    lighting_components_name = f"lighting_components_{scene.name}"
    lighting_components = bpy.data.objects.get(lighting_components_name, None)
    # adding no information
    if not lighting_components:                    
        lighting_components = make_empty('lighting_components_'+scene.name, [0,0,0], [0,0,0], [0,0,0])
        scene.collection.objects.link(lighting_components)  
    if scene.world is not None:
        lighting_components['BlenderBackgroundShader'] = ambient_color_to_component(scene.world)
    lighting_components['BlenderShadowSettings'] = scene_shadows_to_component(scene)

    if scene.eevee.use_bloom:
        lighting_components['BloomSettings'] = scene_bloom_to_component(scene)
    elif 'BloomSettings' in lighting_components:
        del lighting_components['BloomSettings']

    if scene.eevee.use_gtao: 
        lighting_components['SSAOSettings'] = scene_ao_to_component(scene)
    elif 'SSAOSettings' in lighting_components:
        del lighting_components['SSAOSettings']
        
    #inject/ update light shadow information
    # TODO: this is the only thing here that accesses another part of blender other than the scene    
    for light in bpy.data.lights:
        enabled = 'true' if light.use_shadow else 'false'
        light['BlenderLightShadows'] = f"(enabled: {enabled}, buffer_bias: {light.shadow_buffer_bias})"

def ambient_color_to_component(world: bpy.types.World):
    color = None
    strength = None
    try:
        color = world.node_tree.nodes['Background'].inputs[0].default_value
        strength = world.node_tree.nodes['Background'].inputs[1].default_value
    except Exception as ex:
        print("failed to parse ambient color: Only background is supported")
   

    if color is not None and strength is not None:
        colorRgba = f"Rgba(red: {color[0]}, green: {color[1]}, blue: {color[2]}, alpha: {color[3]})"
        component = f"( color: {colorRgba}, strength: {strength})"
        return component
    return None

def scene_shadows_to_component(scene: bpy.types.Scene):
    cascade_size = scene.eevee.shadow_cascade_size
    component = f"(cascade_size: {cascade_size})"
    return component

def scene_bloom_to_component(scene: bpy.types.Scene):
    component = f"BloomSettings(intensity: {scene.eevee.bloom_intensity})"
    return component

def scene_ao_to_component(scene: bpy.types.Scene):
    ssao = scene.eevee.use_gtao
    component= "SSAOSettings()"
    return component
