"""Separate character viewing scene with reversible native facial mask helpers."""
import bpy
from mathutils import Vector
from ._core.face_live import prepare_live
from ._core.face_preview import prepare_render
from .preview_settings import copy_settings, isolate_materials, apply_settings
from .preview_identity import record_copy


def create_preview(context, rig, *, composed_faces=False):
    previous = context.window.scene
    stores = ('objects','collections','meshes','armatures','cameras','lights','worlds','scenes','shape_keys','node_groups','materials')
    before = {name:set(getattr(bpy.data,name)) for name in stores}
    try:
        return build_preview(context, rig, composed_faces=composed_faces)
    except Exception:
        context.window.scene = previous
        bpy.data.batch_remove(ids={item for name in stores for item in getattr(bpy.data,name) if item not in before[name]})
        raise


def build_preview(context, rig, *, composed_faces=False):
    scene = bpy.data.scenes.new(rig.name + (' / Composed face preview' if composed_faces else ' / Animation preview'))
    copy_settings(context.scene, scene)
    scene['tt_character_preview'] = True
    scene.tt_character_game = context.scene.tt_character_game
    scene.render.fps = 30
    copies = {}
    for source in [rig] + list(rig.children_recursive):
        obj = source.copy()
        if source.data:
            obj.data = source.data.copy()
        # A user may request a composed scene from the live viewing copy.
        # Rebuild only our preview modifiers, retaining native skin/morphs.
        for modifier in list(obj.modifiers):
            if modifier.name in ('TT live facial clipping','TT facial depth bias'):
                obj.modifiers.remove(modifier)
        record_copy(source, obj)
        scene.collection.objects.link(obj)
        copies[source] = obj
    for source, obj in copies.items():
        obj.parent = copies.get(source.parent)
        for modifier in obj.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object in copies:
                modifier.object = copies[modifier.object]
        for constraint in obj.constraints:
            if hasattr(constraint, 'target') and constraint.target in copies:
                constraint.target = copies[constraint.target]
    preview_rig = copies[rig]
    context.window.scene = scene
    context.view_layer.update()
    if preview_rig.tt_clips:
        preview_rig.tt_clip_index = rig.tt_clip_index
    scene.frame_set(1)
    depsgraph = context.evaluated_depsgraph_get()
    points = [obj.matrix_world @ Vector(corner) for source in copies.values()
              if source.type == 'MESH' and not source.hide_render
              for obj in [source.evaluated_get(depsgraph)] for corner in obj.bound_box]
    if not points:
        raise ValueError('Character has no visible mesh bounds')
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    center, extent = (low+high)/2, max((high-low).length, .1)
    front = -1 if rig.get('tt_fortnite_static') else 1
    data = bpy.data.cameras.new('Character preview camera')
    camera = bpy.data.objects.new(data.name, data)
    scene.collection.objects.link(camera)
    camera.location = center + Vector((0, front*extent*2.5, extent*.12))
    camera.rotation_euler = (center-camera.location).to_track_quat('-Z','Y').to_euler()
    data.type, data.ortho_scale = 'ORTHO', extent*1.2
    data.clip_start = max(extent*.001, .00001)
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 720, 900, 100
    scene.world = bpy.data.worlds.new('Character preview world')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.1,.1,.1,1)
    for name, offset, power in [('Key',(-1,2,2),500),('Fill',(1,1,1),250)]:
        light = bpy.data.lights.new('Character preview '+name, 'AREA')
        light.energy, light.shape, light.size = power*extent*extent*.05, 'DISK', extent*2
        obj = bpy.data.objects.new(light.name, light)
        scene.collection.objects.link(obj)
        obj.location = center + Vector((offset[0],front*offset[1],offset[2]))*extent
        obj.rotation_euler = (center-obj.location).to_track_quat('-Z','Y').to_euler()
    if preview_rig.type == 'ARMATURE' and preview_rig.pose.bones:
        evaluated = preview_rig.evaluated_get(depsgraph)
        root = evaluated.pose.bones[0]
        root_position = evaluated.matrix_world @ root.head
        for obj in scene.objects:
            if obj.type not in ('CAMERA', 'LIGHT'):
                continue
            obj.location -= root_position
            follow = obj.constraints.new('COPY_LOCATION')
            follow.target, follow.subtarget, follow.use_offset = preview_rig, root.name, True
    context.window.scene = scene
    context.view_layer.update()
    if composed_faces:
        prepare_render(scene)
        scene['tt_character_preview_notes'] = 'F12 renders the composed facial depth-mask passes. Native shaders and expression timing remain approximate; source scene is preserved.'
    else:
        prepare_live(scene, detail_level=scene.tt_face_detail)
        scene['tt_character_preview_notes'] = ('Static LEGO Fortnite model, source colors/printing/normals; facial atlases and special shaders remain incomplete. Source scene is preserved.'
            if rig.get('tt_fortnite_static') else
            'Use camera view and Material Preview for live depth-mask clipping. Geometry-node clipping approximates native depth tests; source scene is preserved.')
    context.window.scene = scene
    context.view_layer.objects.active = preview_rig
    preview_rig.select_set(True)
    if preview_rig.tt_clips:
        preview_rig.tt_clip_index = rig.tt_clip_index
    isolate_materials(scene)
    apply_settings(context, scene)
    if context.screen:
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
                area.spaces.active.shading.type = 'MATERIAL'
    return scene
