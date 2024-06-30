import json
import bpy

from ..auto_export_tracker import AutoExportTracker
from ..settings import BevySettings

class AutoExportGLTF(bpy.types.Operator):
    bl_idname = "export_scenes.auto_gltf"
    bl_label = "Apply settings"
    bl_options = {'PRESET'} 
    # we do not add UNDO otherwise it leads to an invisible operation that resets the state of the saved serialized scene, breaking compares for normal undo/redo operations

    @classmethod
    def register(cls):
       pass

    @classmethod
    def unregister(cls):
       pass
    
    """
    This should ONLY be run when actually doing exports/aka calling auto_export function, because we only care about the difference in settings between EXPORTS
    """
    def did_export_settings_change(self):
        return True
        # compare both the auto export settings & the gltf settings
        previous_auto_settings = bpy.data.texts[".gltf_auto_export_settings_previous"] if ".gltf_auto_export_settings_previous" in bpy.data.texts else None
        previous_gltf_settings = bpy.data.texts[".gltf_auto_export_gltf_settings_previous"] if ".gltf_auto_export_gltf_settings_previous" in bpy.data.texts else None

        current_auto_settings = bpy.data.texts[".gltf_auto_export_settings"] if ".gltf_auto_export_settings" in bpy.data.texts else None
        current_gltf_settings = bpy.data.texts[".gltf_auto_export_gltf_settings"] if ".gltf_auto_export_gltf_settings" in bpy.data.texts else None

        #check if params have changed
        
        # if there were no setting before, it is new, we need export
        changed = False
        if previous_auto_settings == None:
            #print("previous settings missing, exporting")
            changed = True
        elif previous_gltf_settings == None:
            #print("previous gltf settings missing, exporting")
            previous_gltf_settings = bpy.data.texts.new(".gltf_auto_export_gltf_settings_previous")
            previous_gltf_settings.write(json.dumps({}))
            if current_gltf_settings == None:
                current_gltf_settings = bpy.data.texts.new(".gltf_auto_export_gltf_settings")
                current_gltf_settings.write(json.dumps({}))

            changed = True

        else:
            auto_settings_changed = sorted(json.loads(previous_auto_settings.as_string()).items()) != sorted(json.loads(current_auto_settings.as_string()).items()) if current_auto_settings != None else False
            gltf_settings_changed = sorted(json.loads(previous_gltf_settings.as_string()).items()) != sorted(json.loads(current_gltf_settings.as_string()).items()) if current_gltf_settings != None else False
            
            """print("auto settings previous", sorted(json.loads(previous_auto_settings.as_string()).items()))
            print("auto settings current", sorted(json.loads(current_auto_settings.as_string()).items()))
            print("auto_settings_changed", auto_settings_changed)

            print("gltf settings previous", sorted(json.loads(previous_gltf_settings.as_string()).items()))
            print("gltf settings current", sorted(json.loads(current_gltf_settings.as_string()).items()))
            print("gltf_settings_changed", gltf_settings_changed)"""

            changed = auto_settings_changed or gltf_settings_changed
        # now write the current settings to the "previous settings"
        if current_auto_settings != None:
            previous_auto_settings = bpy.data.texts[".gltf_auto_export_settings_previous"] if ".gltf_auto_export_settings_previous" in bpy.data.texts else bpy.data.texts.new(".gltf_auto_export_settings_previous")
            previous_auto_settings.clear()
            previous_auto_settings.write(current_auto_settings.as_string()) # TODO : check if this is always valid

        if current_gltf_settings != None:
            previous_gltf_settings = bpy.data.texts[".gltf_auto_export_gltf_settings_previous"] if ".gltf_auto_export_gltf_settings_previous" in bpy.data.texts else bpy.data.texts.new(".gltf_auto_export_gltf_settings_previous")
            previous_gltf_settings.clear()
            previous_gltf_settings.write(current_gltf_settings.as_string())

        return changed
    
    # def did_objects_change(self):
    #     # FIXME: add it back
    #     return {}

    def execute(self, context):        
        bevy = context.window_manager.bevy # type: BevySettings
        auto_export_tracker =  bpy.context.window_manager.auto_export_tracker # type: AutoExportTracker
        auto_export_tracker.disable_change_detection()

        if bevy.auto_export: # only do the actual exporting if auto export is actually enabled
            print("auto export")

            #changes_per_scene = context.window_manager.auto_export_tracker.changed_objects_per_scene
            #& do the export
            # determine changed objects
            #changes_per_scene = self.did_objects_change()
            # determine changed parameters 
            # TODO: Assming true for now
            #params_changed = self.did_export_settings_change()
            
            # do the export
            bevy.export() #changes_per_scene, params_changed
            
            # cleanup 
            # reset the list of changes in the tracker
            auto_export_tracker.clear_changes()
            print("AUTO EXPORT DONE")            
            bpy.app.timers.register(auto_export_tracker.enable_change_detection, first_interval=0.1)
        else: 
            print("auto export disabled, skipping")
        return {'FINISHED'}    
    
    def invoke(self, context, event):
        print("invoke")
        auto_export_tracker =  bpy.context.window_manager.auto_export_tracker # type: AutoExportTracker
        auto_export_tracker.disable_change_detection()
        return context.window_manager.invoke_props_dialog(self, title="Auto export", width=640)
    
    def cancel(self, context):
        print("cancel")
        #bpy.context.window_manager.auto_export_tracker.enable_change_detection()
        bpy.app.timers.register(bpy.context.window_manager.auto_export_tracker.enable_change_detection, first_interval=1)

