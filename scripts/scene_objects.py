import bpy
import json

# For debugging;
#   Utility for cleaining up scene objects and  
#   viewing: bevy_components and components_meta states

# Safety first
delete_for_real = False

# List of objects to print out debug info for
debug_objects = list(["Cockpit1"]) # ["*"] for all objects

# List of properties to delete if found on object
delete_props = list(["shipwright_collection", "plating_generator", "shape_generator_collection", "MaterialInfo"]) 

delete_bevy_components = list(["orbit::shaders::Skybox"])
debug_bevy_components = list(["orbit::ships::gun::ProxyGun"]) # ["*"] for all objects

# List of components to delete if found in components_meta
delete_meta_components = list(["bevy_gltf_blueprints::materials::MaterialInfo"])

print("\n\n\nScene Objects\n\n\n")

# Constants property names
BC = 'bevy_components'
CM = 'components_meta'

def is_debug_obj(obj):
    for name in debug_objects:
        if name in obj.name or name == "*":
            return True
    return False

# Get all properties on object to see what is left
def other_props(obj):
    props = list(obj.keys())
    exclude: list[str] = [BC, CM]
    exclude.extend(delete_props)
    for p in exclude:
        if p in props:
            props.remove(p)
    return props

for scene in bpy.data.scenes:
    # Iterate over all objects in the current scene
    for obj in scene.objects:
        # delete properties we dont want
        to_delete = []

        for key in obj.keys():
            if key in delete_props:
                print(f"[WARNING] Delete {key} on {obj.name} - in delete_props")
                to_delete.append(key)            
                    
        if BC in obj:
            bevy_components = json.loads(obj[BC])
            to_delete_bevy_components = []
            if is_debug_obj(obj):
                print(f"[INFO] {obj.name} - bevy_components: {json.dumps(bevy_components, indent=4)}")   

            for key in bevy_components.keys():
                if "_ui" in key and key not in delete_bevy_components:
                    print(f"[ERROR-------------] {obj.name} - {key} - {bevy_components[key]}")         
                if key in delete_bevy_components:
                    print(f"[WARNING] Delete {key} in bevy_components on {obj.name} - in delete_bevy_components")
                    to_delete_bevy_components.append(key)
                for name in debug_bevy_components:
                    if name in key:
                        print(f"[INFO] {obj.name} - {key} - {bevy_components[key]}")
                    #print(f"[INFO] {obj.name} - {key} - {bevy_components[key]}")
            if delete_for_real:
                for key in to_delete_bevy_components:
                    del bevy_components[key]
                    obj[BC] = json.dumps(bevy_components)     

        if CM in obj:
            meta = getattr(obj, CM, None) ## type: ComponentsMeta   
            if is_debug_obj(obj):
                print(f"[INFO] {obj.name} - {CM}:")

            if len(meta.components) == 0:
                print(f"[WARNING]: Delete components_meta on {obj.name} - empty")
                to_delete.append(CM)            
            else:
                for index, c in enumerate(meta.components): ## type: ComponentMetadata                    
                    if is_debug_obj(obj):
                        print(f"[INFO] \t{c.long_name}")
                    if c.long_name in delete_meta_components:
                        print(f"[WARNING] Delete {c.long_name} on {obj.name} - in delete_components")
                        if delete_for_real:
                            meta.components.remove(index)
                
        # print out any other properties that are left                           
        props = other_props(obj)            
        if len(props) > 0 and is_debug_obj(obj):            
            print(f"[INFO] {obj.name} - {props}")        

        # delete the properties after we are done iterating
        if delete_for_real:
           for key in to_delete:
                del obj[key]

