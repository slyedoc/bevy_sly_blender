import bpy

# Safty
change = True

info_list = ["Bridge"]

print("\n\n\nDelete Scene\n\n\n")

for scene in bpy.data.scenes:
    if scene.name in info_list:        
        print(scene.name)        
        if change == True:
            bpy.data.scenes.remove(scene)
    