import bpy
from mathutils import Vector

from ..settings import BevySettings

# Based on https://github.com/SuperFLEB/BlenderEditCollectionAddon

def edit_collection_menu(self, context):
    if bpy.context.active_object.instance_collection:
        self.layout.operator(EditCollectionInstance.bl_idname)

class EditCollectionInstance(bpy.types.Operator):
    """Edit the Collection referenced by this Collection Instance in a new Scene"""
    bl_idname = "object.edit_collection_instance"
    bl_label = "Edit Instanced Collection"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):        
        bevy = context.window_manager.bevy # type: BevySettings        
        coll = bpy.context.active_object.instance_collection

        # Store original scene
        bevy.edit_collection_last_scene = bpy.context.scene.name

        # set mode to components
        bevy.mode = "COMPONENTS"

        if not coll:
            print("Active item is not a collection instance")
            self.report({"WARNING"}, "Active item is not a collection instance")
            return {"CANCELLED"}

        scene_name = f"temp:{coll.name}"
        bpy.ops.scene.new(type="EMPTY")
        new_scene = bpy.context.scene
        new_scene.name = scene_name
        bpy.context.window.scene = new_scene
        new_scene.collection.children.link(coll)

        # Assuming you want to focus on the objects from the linked collection
        # Switch to the new scene context        

        if bevy.edit_collection_world_texture != "none":
            world = bpy.data.worlds.new(bpy.context.scene.name)
            new_scene.world = world
            world.use_nodes = True
            tree = world.node_tree

            if bevy.edit_collection_world_texture in ["checker", "checker_view"]:
                checker_texture = tree.nodes.new("ShaderNodeTexChecker")
                checker_texture.inputs["Scale"].default_value = 20
                checker_texture.location = Vector((-250, 0))
                if bevy.edit_collection_world_texture == "checker_view":
                    coord = tree.nodes.new("ShaderNodeTexCoord")
                    coord.location = Vector((-500, 0))
                    for op in coord.outputs:
                        op.hide = True
                    tree.links.new(coord.outputs["Window"], checker_texture.inputs["Vector"])
                tree.links.new(checker_texture.outputs["Color"], tree.nodes["Background"].inputs["Color"])
            elif bevy.edit_collection_world_texture == "gray":
                tree.nodes["Background"].inputs["Color"].default_value = (.3, .3, .3, 1)

        # deselect all objects then select the first object in new scene
        bpy.ops.object.select_all(action='DESELECT')        

        # def find_root_objects(collection):
        #     root_objects = [obj for obj in collection.objects if obj.parent is None or obj.parent not in collection.objects]
        #     return root_objects  
        # for obj in find_root_objects(coll):
        #     print(obj.type, obj.name)

        # find the root object
        root_obj = coll.objects[0]
        while root_obj.parent:
            root_obj = root_obj.parent            
        
        # select object and children
        new_scene.objects[root_obj.name].select_set(True)        
        def select_children(parent):
            for child in parent.children:
                child.select_set(True)
                select_children(child)  # Recursively select further descendants
        select_children(root_obj);

        # Select the view layer and view the selected objects
        bpy.context.view_layer.objects.active = new_scene.objects[root_obj.name]
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[coll.name]

        # zoom to selected
        bpy.ops.view3d.view_selected()

        return {"FINISHED"}
    
class ExitCollectionInstance(bpy.types.Operator):    
    bl_idname = "object.detele_tmp_scene"
    bl_label = "Delete Temp Scene"
    bl_options = {"UNDO"}
    
    def execute(self, context):
        bevy = context.window_manager.bevy # type: BevySettings
        
        current_scene = bpy.context.scene      
        prev_scene = bpy.data.scenes.get(bevy.edit_collection_last_scene)

        if prev_scene is None:
            print("No scene to return to")
            return {'CANCELLED'}
        
        if current_scene.name.startswith("temp:"):
            bpy.data.scenes.remove(bpy.context.scene)
            bpy.context.window.scene = prev_scene
        else:
            print("Not in temp scene")
            return {'CANCELLED'}

        return {'FINISHED'}