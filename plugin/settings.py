import json
import bpy

from bpy.props import (BoolProperty, StringProperty, CollectionProperty, IntProperty, PointerProperty, EnumProperty)

class SceneSelector(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty() # type: ignore
    display: bpy.props.BoolProperty() # type: ignore

# save the to a text datablock
def save_settings(self, context):
    bevy = context.window_manager.bevy # type: BevySettings

    # TODO: serialized self, stupid manually creating it here
    json_str = json.dumps({ 
        'mode': self.mode,
        'schema_file': self.schema_file,
        'assets_path': self.assets_path,
        'auto_export': self.auto_export,
        'main_scene_names': [scene.name for scene in self.main_scenes],
        'library_scene_names': [scene.name for scene in self.library_scenes],
    })

    if bevy.settings_save_path in bpy.data.texts:
        bpy.data.texts[bevy.settings_save_path].clear()
        bpy.data.texts[bevy.settings_save_path].write(json_str)
    else:
        stored_settings = bpy.data.texts.new(bevy.settings_save_path)
        stored_settings.write(json_str)
    return None        
 
class BevySettings(bpy.types.PropertyGroup):
    settings_save_path = ".bevy_settings" # where to store data in bpy.texts
    mode: EnumProperty(
        items=(
            ('COMPONENTS', "Components", ""),
            ('BLUEPRINTS', "Blueprints", ""),
            ('ASSETS', "Assets", ""),
            ('SETTINGS', "Settings", ""),
            ('TOOLS', "Tools", ""),
        ),
        #update=update_mode
    ) # type: ignore    
    assets_path: StringProperty(
        name='Export folder',
        description='The root folder for all exports(relative to the root folder/path) Defaults to "assets" ',
        default='./assets',
        options={'HIDDEN'},
        update= save_settings
    ) # type: ignore
    schema_file: StringProperty(
        name='Schema File',
        description='The registry.json file',
        default='./assets/registry.json',
        options={'HIDDEN'},
        update= save_settings
    ) # type: ignore
    auto_export: BoolProperty(
        name='Auto Export',
        description='Automatically export to gltf on save',
        default=False,
        update= save_settings
    ) # type: ignore
    main_scenes: CollectionProperty(name="main scenes",type=SceneSelector) # type: ignore
    main_scenes_index: IntProperty(name = "Index for main scenes list", default = 0, update= save_settings) # type: ignore
    library_scenes: CollectionProperty(name="library scenes", type=SceneSelector ) # type: ignore
    library_scenes_index: IntProperty(name = "Index for library scenes list", default = 0, update= save_settings) # type: ignore    
    collection_instances_combine_mode : EnumProperty(
        name='Collection instances',
        items=(
           ('Split', 'Split', 'replace collection instances with an empty + blueprint, creating links to sub blueprints (Default, Recomended)'),
           ('Embed', 'Embed', 'treat collection instances as embeded objects and do not replace them with an empty'),
           ('EmbedExternal', 'EmbedExternal', 'treat instances of external (not specifified in the current blend file) collections (aka assets etc) as embeded objects and do not replace them with empties'),
           #('Inject', 'Inject', 'inject components from sub collection instances into the curent object')
        ),
        default='Split'
    ) # type: ignore


    @classmethod
    def register(cls):
        pass
        #bpy.types.WindowManager.main_scene = bpy.props.PointerProperty(type=bpy.types.Scene, name="main scene", description="main_scene_picker", poll=cls.is_scene_ok)
        #bpy.types.WindowManager.library_scene = bpy.props.PointerProperty(type=bpy.types.Scene, name="library scene", description="library_scene_picker", poll=cls.is_scene_ok)

    @classmethod
    def unregister(cls):
        pass
        #del bpy.types.WindowManager.main_scene
        #del bpy.types.WindowManager.library_scene

    @classmethod 
    def get_all_modes(cls):
        # Return a list of all possible mode values
        return [item[0] for item in cls.__annotations__['mode'].keywords['items']]

    def get_scenes(self):        
        level_scene_names= list(map(lambda scene: scene.name, self.main_scenes))
        library_scene_names = list(map(lambda scene: scene.name, self.library_scenes))
        level_scenes = list(map(lambda name: bpy.data.scenes[name], level_scene_names))
        library_scenes = list(map(lambda name: bpy.data.scenes[name], library_scene_names))        
        return [level_scene_names, level_scenes, library_scene_names, library_scenes]

    # not sure where i will put this
    def generate_gltf_export_preferences(self): 
        # default values
        gltf_export_preferences = dict(
            # export_format= 'GLB', #'GLB', 'GLTF_SEPARATE', 'GLTF_EMBEDDED'
            check_existing=False,

            use_selection=False,
            use_visible=True, # Export visible and hidden objects. See Object/Batch Export to skip.
            use_renderable=False,
            use_active_collection= False,
            use_active_collection_with_nested=False,
            use_active_scene = False,

            export_cameras=True,
            export_extras=True, # For custom exported properties.
            export_lights=True,

            #export_texcoords=True,
            #export_normals=True,
            # here add draco settings
            #export_draco_mesh_compression_enable = False,

            #export_tangents=False,
            #export_materials
            #export_colors=True,
            #export_attributes=True,
            #use_mesh_edges
            #use_mesh_vertices
        
            
            #export_yup=True,
            #export_skins=True,
            #export_morph=False,
            #export_apply=False,
            #export_animations=False,
            #export_optimize_animation_size=False
        )
            
        # for key in self.__annotations__.keys():
        #     if str(key) not in AutoExportGltfPreferenceNames:
        #         #print("overriding setting", key, "value", getattr(addon_prefs,key))
        #         gltf_export_preferences[key] = getattr(addon_prefs, key)

        standard_gltf_exporter_settings = bpy.data.texts[".gltf_auto_export_gltf_settings"] if ".gltf_auto_export_gltf_settings" in bpy.data.texts else None
        if standard_gltf_exporter_settings != None:
            try:
                standard_gltf_exporter_settings = json.loads(standard_gltf_exporter_settings.as_string())
            except:
                standard_gltf_exporter_settings = {}
        else:
            standard_gltf_exporter_settings = {}

        constant_keys = [
            'use_selection',
            'use_visible',
            'use_active_collection',
            'use_active_collection_with_nested',
            'use_active_scene',
            'export_cameras',
            'export_extras', # For custom exported properties.
            'export_lights',
        ]

        # a certain number of essential params should NEVER be overwritten , no matter the settings of the standard exporter
        for key in standard_gltf_exporter_settings.keys():
            if str(key) not in constant_keys:
                gltf_export_preferences[key] =  standard_gltf_exporter_settings.get(key)
        return gltf_export_preferences

    def load_settings(self):
        stored_settings = bpy.data.texts[self.settings_save_path] if self.settings_save_path in bpy.data.texts else None        
        if stored_settings != None:
            settings =  json.loads(stored_settings.as_string())        
            for prop in ['assets_path', 'schema_file', 'auto_export', 'mode']:
                if prop in settings:
                    setattr(self, prop, settings[prop])
            if "main_scene_names" in settings:
                for name in settings["main_scene_names"]:
                    added = self.main_scenes.add()
                    added.name = name
            if "library_scene_names" in settings:
                for name in settings["library_scene_names"]:
                    added = self.library_scenes.add()
                    added.name = name

        # save the setting back, so its updated if need be, or added if need be
        save_settings(self, bpy.context)

        # main_scene_names = [scene.name for scene in self.main_scenes]
        # library_scene_names = [scene.name for scene in self.library_scenes]

# def update_asset_folders(self, context):
#     print("updating asset folders")
#     # blenvy = context.window_manager.blenvy
#     # asset_path_names = ['project_root_path', 'assets_path', 'blueprints_path', 'levels_path', 'materials_path']
#     # for asset_path_name in asset_path_names:
#     #     upsert_settings(blenvy.settings_save_path, {asset_path_name: getattr(blenvy, asset_path_name)})

# def update_mode(self, context):
#     print("updating mode")
#     # blenvy = self # context.window_manager.blenvy
#     # upsert_settings(blenvy.settings_save_path, {"mode": blenvy.mode })

# class BevySettings(bpy.types.PropertyGroup):
#     settings_save_path = ".bevy_settings" # where to store data in bpy.texts
#     mode: EnumProperty(
#         items=(
#                 ('COMPONENTS', "Components", ""),
#                 ('BLUEPRINTS', "Blueprints", ""),
#                 ('ASSETS', "Assets", ""),
#                 ('SETTINGS', "Settings", ""),
#                 ('TOOLS', "Tools", ""),
#         ),
#         update=update_mode
#     ) # type: ignore    

#     @classmethod
#     def register(cls):
#         print("registering BevySettings")
#         #bpy.types.WindowManager.main_scene = bpy.props.PointerProperty(type=bpy.types.Scene, name="main scene", description="main_scene_picker", poll=cls.is_scene_ok)
#         #bpy.types.WindowManager.library_scene = bpy.props.PointerProperty(type=bpy.types.Scene, name="library scene", description="library_scene_picker", poll=cls.is_scene_ok)
#         #bpy.types.WindowManager.bevy = PointerProperty(type=BevySettings)

#     @classmethod
#     def unregister(cls):
#         print("unregistering BevySettings")
#         #del bpy.types.WindowManager.main_scene
#         #del bpy.types.WindowManager.library_scene
#         #del bpy.types.WindowManager.bevy
#     # project_root_path: StringProperty(
#     #     name = "Project Root Path",
#     #     description="The root folder of your (Bevy) project (not assets!)",
#     #     default='../',
#     #     update= update_asset_folders
#     # ) # type: ignore

#     # assets_path: StringProperty(
#     #     name='Export folder',
#     #     description='The root folder for all exports(relative to the root folder/path) Defaults to "assets" ',
#     #     default='./assets',
#     #     options={'HIDDEN'},
#     #     update= update_asset_folders
#     # ) # type: ignore

#     # blueprints_path: StringProperty(
#     #     name='Blueprints path',
#     #     description='path to export the blueprints to (relative to the assets folder)',
#     #     default='blueprints',
#     #     update= update_asset_folders
#     # ) # type: ignore

#     # levels_path: StringProperty(
#     #     name='Levels path',
#     #     description='path to export the levels (main scenes) to (relative to the assets folder)',
#     #     default='levels',
#     #     update= update_asset_folders
#     # ) # type: ignore

#     # materials_path: StringProperty(
#     #     name='Materials path',
#     #     description='path to export the materials libraries to (relative to the assets folder)',
#     #     default='materials',
#     #     update= update_asset_folders
#     # ) # type: ignore

#     #main_scenes: CollectionProperty(name="main scenes", type=SceneSelector) # type: ignore
#     #main_scenes_index: IntProperty(name = "Index for main scenes list", default = 0, update=update_scene_lists) # type: ignore
#     #main_scene_names = [] # FIXME: unsure

#     #library_scenes: CollectionProperty(name="library scenes", type=SceneSelector) # type: ignore
#     #library_scenes_index: IntProperty(name = "Index for library scenes list", default = 0, update=update_scene_lists) # type: ignore
#     #library_scene_names = [] # FIXME: unsure

#     # sub ones
#     #auto_export: PointerProperty(type=auto_export_settings.AutoExportSettings) # type: ignore
#     #components: PointerProperty(type=bevy_component_settings.ComponentSettings) # type: ignore

#     # def is_scene_ok(self, scene):
#     #     try:
#     #         operator = bpy.context.space_data.active_operator
#     #         return scene.name not in operator.main_scenes and scene.name not in operator.library_scenes
#     #     except:
#     #         return True
        


#     # def load_settings(self):
#     #     settings = load_settings(self.settings_save_path)
#     #     if settings is not None:
#     #         if "mode" in settings:
#     #             self.mode = settings["mode"]
#     #         if "common_main_scene_names" in settings:
#     #             for main_scene_name in settings["common_main_scene_names"]:
#     #                 added = self.main_scenes.add()
#     #                 added.name = main_scene_name
#     #         if "common_library_scene_names" in settings:
#     #             for main_scene_name in settings["common_library_scene_names"]:
#     #                 added = self.library_scenes.add()
#     #                 added.name = main_scene_name

#     #         asset_path_names = ['project_root_path', 'assets_path', 'blueprints_path', 'levels_path', 'materials_path']
#     #         for asset_path_name in asset_path_names:
#     #             if asset_path_name in settings:
#     #                 setattr(self, asset_path_name, settings[asset_path_name])
#     #     settings
        

       


# # def upsert_settings(name, data):
# #     stored_settings = bpy.data.texts[name] if name in bpy.data.texts else None#bpy.data.texts.new(name)
# #     if stored_settings is None:
# #         stored_settings = bpy.data.texts.new(name)
# #         stored_settings.write(json.dumps(data))
# #     else:
# #         current_settings = json.loads(stored_settings.as_string())
# #         current_settings = {**current_settings, **data}
# #         stored_settings.clear()
# #         stored_settings.write(json.dumps(current_settings))

# # def load_settings(name):
# #     print("loading settings", name)
# #     stored_settings = bpy.data.texts[name] if name in bpy.data.texts else None
# #     if stored_settings != None:
# #         return json.loads(stored_settings.as_string())
# #     return None

# # # checks if old & new settings (dicts really) are identical
# # def are_settings_identical(old, new, white_list=None):
# #     if old is None and new is None:
# #         return True
# #     if old is None and new is not None:
# #         return False
# #     if old is not None and new is None:
# #         return False
    
# #     old_items = sorted(old.items())
# #     new_items = sorted(new.items())
# #     if white_list is not None:
# #         old_items_override = {}
# #         new_items_override = {}
# #         for key in white_list:
# #             if key in old_items:
# #                 old_items_override[key] = old_items[key]
# #             if key in new_items:
# #                 new_items_override[key] = new_items[key]
# #         old_items = old_items_override
# #         new_items = new_items_override
            
# #     return old_items != new_items if new is not None else False