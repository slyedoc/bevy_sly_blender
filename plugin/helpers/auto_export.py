
import os
import bpy
import traceback
import json

from plugin.blueprints_registry import BlueprintsRegistry
from plugin.settings import BevySettings
from plugin.util import BLUEPRINTS_PATH, CHANGE_DETECTION, EXPORT_BLUEPRINTS, EXPORT_MATERIALS_LIBRARY, EXPORT_SCENE_SETTINGS, GLTF_EXTENSION, LEVELS_PATH

from .levels import get_levels_to_export, export_main_scene
from .blueprints import export_blueprints, get_blueprints_to_export
from .export_materials import cleanup_materials, export_materials
from .object_makers import make_empty

def ambient_color_to_component(world):
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

def scene_shadows_to_component(scene):
    cascade_size = scene.eevee.shadow_cascade_size
    component = f"(cascade_size: {cascade_size})"
    return component

def scene_bloom_to_component(scene):
    component = f"BloomSettings(intensity: {scene.eevee.bloom_intensity})"
    return component

def scene_ao_to_component(scene):
    ssao = scene.eevee.use_gtao
    component= "SSAOSettings()"
    return component


def get_standard_exporter_settings():
    standard_gltf_exporter_settings = bpy.data.texts[".gltf_auto_export_gltf_settings"] if ".gltf_auto_export_gltf_settings" in bpy.data.texts else None
    if standard_gltf_exporter_settings != None:
        try:
            standard_gltf_exporter_settings = json.loads(standard_gltf_exporter_settings.as_string())
        except:
            standard_gltf_exporter_settings = {}
    else:
        standard_gltf_exporter_settings = {}
    
    return standard_gltf_exporter_settings

"""this is the main 'central' function for all auto export """
def auto_export(changes_per_scene, changed_export_parameters, bevy: BevySettings):
    blueprints_registry = bpy.context.window_manager.blueprints_registry # type: BlueprintsRegistry
   
    [level_scene_names, level_scenes, library_scene_names, library_scenes] = bevy.get_scenes()

    # have the export parameters (not auto export, just gltf export) have changed: if yes (for example switch from glb to gltf, compression or not, animations or not etc), we need to re-export everything
    print ("changed_export_parameters", changed_export_parameters)
    try:
        # update the blueprints registry
        blueprints_registry.scan()
        blueprints_data =  blueprints_registry.blueprints_data

        # we inject the blueprints export path
        for blueprint in blueprints_data.internal_blueprints:
            blueprint_exported_path = os.path.join(bevy.assets_path, BLUEPRINTS_PATH, f"{blueprint.name}{GLTF_EXTENSION}")
            blueprint.collection["export_path"] = blueprint_exported_path           

        for blueprint in blueprints_data.blueprints:
            blueprints_registry.add_blueprint(blueprint)

        # TODO: IMPORTANT: this is where custom components are injected        
        if EXPORT_SCENE_SETTINGS:
            for scene in level_scenes:
                lighting_components_name = f"lighting_components_{scene.name}"
                lighting_components = bpy.data.objects.get(lighting_components_name, None)
                if not lighting_components:
                    root_collection = scene.collection
                    lighting_components = make_empty('lighting_components_'+scene.name, [0,0,0], [0,0,0], [0,0,0], root_collection)

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
                for light in bpy.data.lights:
                    enabled = 'true' if light.use_shadow else 'false'
                    light['BlenderLightShadows'] = f"(enabled: {enabled}, buffer_bias: {light.shadow_buffer_bias})"

        # export
        if EXPORT_BLUEPRINTS:
            print("EXPORTING", blueprints_data)
            # get blueprints/collections infos
            (blueprints_to_export) = get_blueprints_to_export(changes_per_scene, changed_export_parameters, blueprints_data, bevy)
             
            # get level/main scenes infos
            (main_scenes_to_export) = get_levels_to_export(changes_per_scene, changed_export_parameters, blueprints_data, bevy)

            # since materials export adds components we need to call this before blueprints are exported
            # export materials & inject materials components into relevant objects
            if EXPORT_MATERIALS_LIBRARY:
                export_materials(blueprints_data.blueprint_names, library_scenes, bevy)

            # update the list of tracked exports
            exports_total = len(blueprints_to_export) + len(main_scenes_to_export) + (1 if EXPORT_MATERIALS_LIBRARY else 0)
            bpy.context.window_manager.auto_export_tracker.exports_total = exports_total
            bpy.context.window_manager.auto_export_tracker.exports_count = exports_total

            """bpy.context.window_manager.exportedCollections.clear()
            for  blueprint in blueprints_to_export:
                bla = bpy.context.window_manager.exportedCollections.add()
                bla.name = blueprint.name"""
            print("-------------------------------")
            #print("collections:               all:", collections)
            #print("collections: not found on disk:", collections_not_on_disk)
            print("BLUEPRINTS:    local/internal:", [blueprint.name for blueprint in blueprints_data.internal_blueprints])
            print("BLUEPRINTS:          external:", [blueprint.name for blueprint in blueprints_data.external_blueprints])
            print("BLUEPRINTS:         per_scene:", blueprints_data.blueprints_per_scenes)
            print("-------------------------------")
            print("BLUEPRINTS:          to export:", [blueprint.name for blueprint in blueprints_to_export])
            print("-------------------------------")
            print("MAIN SCENES:         to export:", main_scenes_to_export)
            print("-------------------------------")
            # backup current active scene
            old_current_scene = bpy.context.scene
            # backup current selections
            old_selections = bpy.context.selected_objects

            # first export any main/level/world scenes
            if len(main_scenes_to_export) > 0:
                print("export MAIN scenes")
                for scene_name in main_scenes_to_export:
                    export_main_scene(bpy.data.scenes[scene_name], blueprints_data, bevy)

            # now deal with blueprints/collections
            do_export_library_scene = not CHANGE_DETECTION or changed_export_parameters or len(blueprints_to_export) > 0
            if do_export_library_scene:
                print("export LIBRARY")
                export_blueprints(blueprints_to_export, blueprints_data, bevy)

            # reset current scene from backup
            bpy.context.window.scene = old_current_scene

            # reset selections
            for obj in old_selections:
                obj.select_set(True)
            if EXPORT_MATERIALS_LIBRARY:
                cleanup_materials(blueprints_data.blueprint_names, library_scenes)

        else:
            for scene_name in level_scene_names:
                export_main_scene(bpy.data.scenes[scene_name], blueprints_data, bevy)

    except Exception as error:
        print(traceback.format_exc())

        def error_message(self, context):
            self.layout.label(text="Failure during auto_export: Error: "+ str(error))

        bpy.context.window_manager.popup_menu(error_message, title="Error", icon='ERROR')

    finally:
        # FIXME: error handling ? also redundant
        if EXPORT_SCENE_SETTINGS:
            # TODO: IMPORTANT: this where those custom components are removed
                for scene in level_scenes:
                    lighting_components_name = f"lighting_components_{scene.name}"
                    lighting_components = bpy.data.objects.get(lighting_components_name, None)
                    if lighting_components:
                        bpy.data.objects.remove(lighting_components, do_unlink=True)
                        

