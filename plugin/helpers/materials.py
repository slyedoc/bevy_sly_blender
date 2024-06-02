import bpy

from pathlib import Path

from .collections import (traverse_tree)
from .object_makers import make_cube

# creates a new object with the applied material, for the material library
def make_material_object(name, location=[0,0,0], rotation=[0,0,0], scale=[1,1,1], material=None, collection=None): 
    #original_active_object = bpy.context.active_object
    #bpy.ops.mesh.primitive_cube_add(size=0.1, location=location)  
    object = make_cube(name, location=location, rotation=rotation, scale=scale, collection=collection)
    if material:
        if object.data.materials:
            # assign to 1st material slot
            object.data.materials[0] = material
        else:
            # no slots
            object.data.materials.append(material)
    return object


# generates a materials scene: 
def generate_materials_scene_content(root_collection, used_material_names):
    for index, material_name in enumerate(used_material_names):
        material = bpy.data.materials[material_name]
        make_material_object("Material_"+material_name, [index * 0.2,0,0], material=material, collection=root_collection)
    return {}

def clear_materials_scene(temp_scene):
    root_collection = temp_scene.collection 
    scene_objects = [o for o in root_collection.objects]
    for object in scene_objects:
        #print("removing ", object)
        try:
            mesh = bpy.data.meshes[object.name+"_Mesh"]
            bpy.data.meshes.remove(mesh, do_unlink=True)
        except Exception as error:
            pass
            #print("could not remove mesh", error)
            
        try:
            bpy.data.objects.remove(object, do_unlink=True)
        except:pass

    bpy.data.scenes.remove(temp_scene)

# get materials per object, and injects the materialInfo component
def get_materials(object):
    material_slots = object.material_slots
    used_materials_names = []
    #materials_per_object = {}
    current_project_name = Path(bpy.context.blend_data.filepath).stem

    for m in material_slots:
        material = m.material
        # print("    slot", m, "material", material)
        used_materials_names.append(material.name)
        # TODO:, also respect slots & export multiple materials if applicable ! 
        # TODO: do NOT modify objects like this !! do it in a different function
        object['MaterialInfo'] = '(name: "'+material.name+'", source: "'+current_project_name + '")' 

    return used_materials_names


def get_all_materials(collection_names, library_scenes): 
    used_material_names = []
    for scene in library_scenes:
        root_collection = scene.collection
        for cur_collection in traverse_tree(root_collection):
            if cur_collection.name in collection_names:
                for object in cur_collection.all_objects:
                    used_material_names = used_material_names + get_materials(object)

    # we only want unique names
    used_material_names = list(set(used_material_names))
    return used_material_names
