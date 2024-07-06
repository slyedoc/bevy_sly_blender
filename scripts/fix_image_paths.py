import bpy

# Safty
change = False

info_list = ["D:"]
replace_list = [("D:/project/Control Room Science Fiction Station/3D/sell/blender/texture/", "/home/slyedoc/code/p/assets/cgtrader/Sci Fi Interior Station 3D/texture/")]

print("\n\n\nImage Paths\n\n\n")

# Iterate over all materials
for material in bpy.data.materials:
    # Iterate over all nodes in the material
    if material.use_nodes:
        for node in material.node_tree.nodes:
            # Check if the node is an image texture
            if node.type == 'TEX_IMAGE':
                # Get the image filepath
                image = node.image
                if image:
                    print(f"Found: {image.name} in {image.filepath_raw}")
                    for name in info_list:
                       if name in image.filepath_raw:
                            
                            #print(f"Found: {name} in {image.filepath}")

                            # Get the filename
                            for (old_dir, new_dir) in replace_list:
                                if old_dir in image.filepath_raw:
                                    filename = image.filepath_raw
                                    filename = filename.replace(old_dir, new_dir)
                                    if change:                                
                                        image.filepath_raw = filename
                                        image.filepath = filename
                                        image.reload()                                    
                                    #print(f"Updated: {image.filepath}")

