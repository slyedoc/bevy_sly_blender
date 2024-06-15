import json
import bpy



from bpy.types import (PropertyGroup)
from bpy.props import (PointerProperty, IntProperty, StringProperty)

from .util import TEMPSCENE_PREFIX

class AutoExportTracker(PropertyGroup):

    changed_objects_per_scene = {}
    change_detection_enabled = True
    export_params_changed = False

    gltf_settings_backup = None
    last_operator = None
    dummy_file_path = ""

    exports_total : IntProperty(
        name='exports_total',
        description='Number of total exports',
        default=0
    ) # type: ignore

    exports_count : IntProperty(
        name='exports_count',
        description='Number of exports in progress',
        default=0
    ) # type: ignore

    @classmethod
    def register(cls):
        pass

    @classmethod
    def unregister(cls):
        pass

    @classmethod
    def save_handler(cls, scene, depsgraph):
        print("saved", bpy.data.filepath)
        # auto_export(changes_per_scene, export_parameters_changed)
        bpy.ops.export_scenes.auto_gltf()

        # (re)set a few things after exporting
        # reset wether the gltf export paramters were changed since the last save 
        cls.export_params_changed = False
        
        # reset whether there have been changed objects since the last save 
        cls.changed_objects_per_scene.clear()
        # all our logic is done, mark this as done
    
    @classmethod
    def deps_post_update_handler(cls, scene, depsgraph):
        # print("change detection enabled", cls.change_detection_enabled)

        #ops = bpy.context.window_manager.operators
        #print("last operators", ops)
        #for op in ops:
        #   print("operator", op)

        # TODO: this is to capture export settings, will come back to this, going with hardcode settings for now
        # active_operator = bpy.context.active_operator # type: bpy.types.Operator
        # if active_operator:
        #     #print("Operator", active_operator.bl_label, active_operator.bl_idname)
        #     if active_operator.bl_idname == "EXPORT_SCENE_OT_gltf" and active_operator.gltf_export_id == "gltf_auto_export":                
        #         # we backup any existing gltf export settings, if there were any
        #         scene = bpy.context.scene
        #         if "glTF2ExportSettings" in scene:
        #             existing_setting = scene["glTF2ExportSettings"]
        #             bpy.context.window_manager.gltf_settings_backup = json.dumps(dict(existing_setting))

        #         # we force saving params
        #         active_operator.will_save_settings = True
        #         # we set the last operator here so we can clear the specific settings (yeah for overly complex logic)
        #         cls.last_operator = active_operator
        #         #print("active_operator", active_operator.has_active_exporter_extensions, active_operator.__annotations__.keys(), active_operator.filepath, active_operator.gltf_export_id)
        #         return
            
        #     if active_operator.bl_idname == "EXPORT_SCENES_OT_auto_gltf":
        #         # we force saving params
        #         active_operator.will_save_settings = True
        #         active_operator.auto_export = True
        #         # if we are using the operator, bail out for the rest
        #         print("setting stuff for auto_export")
        #         return

        # only deal with changes if we are NOT in the mids of saving/exporting
        if cls.change_detection_enabled:
            # ignore anything going on with temporary scenes
            if not scene.name.startswith(TEMPSCENE_PREFIX):
                #print("depsgraph_update_post", scene.name)
                changed_scene = scene.name or ""
                #print("-------------")
                if not changed_scene in cls.changed_objects_per_scene:
                    cls.changed_objects_per_scene[changed_scene] = {}
                # print("cls.changed_objects_per_scene", cls.changed_objects_per_scene)
                # depsgraph = bpy.context.evaluated_depsgraph_get()
                for obj in depsgraph.updates:
                    #print("depsgraph update", obj)
                    if isinstance(obj.id, bpy.types.Object):
                        # get the actual object
                        object = bpy.data.objects[obj.id.name]
                        #print("  changed object", obj.id.name, "changes", obj, "evalutated", obj.id.is_evaluated, "transforms", obj.is_updated_transform, "geometry", obj.is_updated_geometry)
                        if obj.is_updated_transform or obj.is_updated_geometry:
                            cls.changed_objects_per_scene[scene.name][obj.id.name] = object
                        
                    elif isinstance(obj.id, bpy.types.Material): # or isinstance(obj.id, bpy.types.ShaderNodeTree):
                        # print("  changed material", obj.id, "scene", scene.name,)
                        material = bpy.data.materials[obj.id.name]
                        #now find which objects are using the material
                        for obj in bpy.data.objects:
                            for slot in obj.material_slots:
                                if slot.material == material:
                                    cls.changed_objects_per_scene[scene.name][obj.name] = obj
                #print("changed_objects_per_scene", cls.changed_objects_per_scene)
                #for obj_name_original in cls.changed_objects_per_scene[scene_name]:
                #   if obj_name_original != ls.changed_objects_per_scene[scene_name][obj_name_original]
                items = 0
                for scene_name in cls.changed_objects_per_scene:
                    items += len(cls.changed_objects_per_scene[scene_name].keys())
                if items == 0:
                    cls.changed_objects_per_scene.clear()
                #print("changed_objects_per_scene", cls.changed_objects_per_scene)

        # filter out invalid objects
        #for scene_name in cls.changed_objects_per_scene.keys():
        #    bla = {}
        #    for object_name in cls.changed_objects_per_scene[scene.name]:
        #        object = cls.changed_objects_per_scene[scene.name][object_name]
        #        #print("sdfsd", object, object.valid)
                #if not cls.changed_objects_per_scene[scene.name][object_name].invalid:
                #    bla[object_name] = cls.changed_objects_per_scene[scene.name][object_name]
            #cls.changed_objects_per_scene[scene.name]= bla
            #cls.changed_objects_per_scene[scene_name] = [o for o in cls.changed_objects_per_scene[scene_name] if not o.invalid]
        
        # get a list of exportable collections for display
        # keep it simple, just use Simplenamespace for compatibility with the rest of our code
        # TODO: debounce

    def disable_change_detection(self):
        #print("disable change detection")
        self.change_detection_enabled = False
        self.__class__.change_detection_enabled = False
        return None
    
    def enable_change_detection(self):
        #print("enable change detection")
        self.change_detection_enabled = True
        self.__class__.change_detection_enabled = True
        #print("bpy.context.window_manager.auto_export_tracker.change_detection_enabled", bpy.context.window_manager.auto_export_tracker.change_detection_enabled)
        return None
    
    def clear_changes(self):
        self.changed_objects_per_scene.clear()
        self.__class__.changed_objects_per_scene.clear()

    def export_finished(self):
        #print("export_finished")
        self.exports_count -= 1
        if self.exports_count == 0:
            print("preparing to reset change detection")
            bpy.app.timers.register(self.enable_change_detection, first_interval=0.1)
            #self.enable_change_detection()
        return None

