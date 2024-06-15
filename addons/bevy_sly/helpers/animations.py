import bpy

# reference https://github.com/KhronosGroup/glTF-Blender-IO/blob/main/addons/io_scene_gltf2/blender/exp/animation/gltf2_blender_gather_action.py#L481
def copy_animation_data(source, target):
    if source.animation_data:
        ad = source.animation_data

        blender_actions = []
        blender_tracks = {}

        # TODO: this might need to be modified/ adapted to match the standard gltf exporter settings
        for track in ad.nla_tracks:
            non_muted_strips = [strip for strip in track.strips if strip.action is not None and strip.mute is False]
            for strip in non_muted_strips: #t.strips:
                # print("  ", source.name,'uses',strip.action.name, "active", strip.active, "action", strip.action)
                blender_actions.append(strip.action)
                blender_tracks[strip.action.name] = track.name

        # Remove duplicate actions.
        blender_actions = list(set(blender_actions))
        # sort animations alphabetically (case insensitive) so they have a defined order and match Blender's Action list
        blender_actions.sort(key = lambda a: a.name.lower())
        
        markers_per_animation = {}
        animations_infos = []

        for action in blender_actions:
            animation_name = blender_tracks[action.name]
            animations_infos.append(
                f'(name: "{animation_name}", frame_start: {action.frame_range[0]}, frame_end: {action.frame_range[1]}, frames_length: {action.frame_range[1] - action.frame_range[0]}, frame_start_override: {action.frame_start}, frame_end_override: {action.frame_end})'
            )
            markers_per_animation[animation_name] = {}

            for marker in action.pose_markers:
                if marker.frame not in markers_per_animation[animation_name]:
                    markers_per_animation[animation_name][marker.frame] = []
                markers_per_animation[animation_name][marker.frame].append(marker.name)

        # best method, using the built-in link animation operator
        with bpy.context.temp_override(active_object=source, selected_editable_objects=[target]): 
            bpy.ops.object.make_links_data(type='ANIMATION')
        
        """if target.animation_data == None:
            target.animation_data_create()
        target.animation_data.action = source.animation_data.action.copy()

        print("copying animation data for", source.name, target.animation_data)
        properties = [p.identifier for p in source.animation_data.bl_rna.properties if not p.is_readonly]
        for prop in properties:
            print("copying stuff", prop)
            setattr(target.animation_data, prop, getattr(source.animation_data, prop))"""
        
        # we add an "AnimationInfos" component 
        target['AnimationInfos'] = f'(animations: {animations_infos})'.replace("'","")
        
        # and animation markers
        markers_formated = '{'
        for animation in markers_per_animation.keys():
            markers_formated += f'"{animation}":'
            markers_formated += "{"
            for frame in markers_per_animation[animation].keys():
                markers = markers_per_animation[animation][frame]
                markers_formated += f"{frame}:{markers}, ".replace("'", '"')
            markers_formated += '}, '             
        markers_formated += '}' 
        target["AnimationMarkers"] = f'( {markers_formated} )'