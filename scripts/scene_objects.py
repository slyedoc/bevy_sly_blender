import bpy
import json



print("\nScene Objects\n")
delete_list = list([]) #"shipwright_collection", "shape_generator_collection"
delete_for_real = False

# Iterate over all objects in the current scene
# Iterate over all scenes in the Blender project
for scene in bpy.data.scenes:
    # Iterate over all objects in the current scene
    for obj in scene.objects:
        # delete properties we dont want
        to_delete = []
        for key in obj.keys():
            if key in delete_list:
                print(f"Delete Object: {obj.name}, because {key} is in delete_list")
                to_delete.append(key)
        

        if 'bevy_components' in obj:
            bevy_components = json.loads(obj['bevy_components'])
            print(f"{obj.name} - bevy_components:\n\t {bevy_components}")
        elif 'components_meta' in obj:
            meta = getattr(obj, 'components_meta', None) ## type: ComponentsMeta
            
            if len(meta.components) == 0:
                print(f"Delete Object: {obj.name}, because components_meta is empty")
                to_delete.append('components_meta')            
            else:
                print(f"{obj.name} _------------------------ components_meta:")            
            for c in meta.components:
                print(f"- {c.long_name}")
        else:
            print(f"Object: {obj.name} {list(obj.keys()).remove(['bevy_components','components_meta'])}")        

        # delete the properties after we are done iterating
        if delete_for_real:
            for key in to_delete:
                del obj[key]


