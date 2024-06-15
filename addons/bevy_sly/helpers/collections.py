import bpy

# traverse all collections
def traverse_tree(t):
    yield t
    for child in t.children:
        yield from traverse_tree(child)

#Recursivly transverse layer_collection for a particular name
def recurLayerCollection(layerColl, collName):
    found = None
    if (layerColl.name == collName):
        return layerColl
    for layer in layerColl.children:
        found = recurLayerCollection(layer, collName)
        if found:
            return found
