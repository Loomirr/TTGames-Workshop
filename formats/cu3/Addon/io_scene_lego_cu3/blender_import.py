"""Blender scene inspection and source-skeleton animation application."""
import json
import math
from pathlib import Path
import bpy
from mathutils import Matrix, Vector, Euler, Quaternion
from .cu3 import Cutscene, FormatError
from .skeleton import read_skeleton

C = Matrix.Rotation(math.pi / 2, 4, 'X')
CI = C.inverted()


def row_matrix(values):
    return Matrix([values[i:i + 4] for i in (0, 4, 8, 12)]).transposed()


def action_bag(action, obj):
    slot = action.slots.new('CAMERA' if isinstance(obj, bpy.types.Camera) else 'LIGHT' if isinstance(obj, bpy.types.Light) else 'OBJECT', obj.name)
    bag = action.layers.new('CU3 source animation').strips.new(type='KEYFRAME').channelbag(slot, ensure=True)
    return slot, bag


def curve(bag, path, index, values, group=''):
    f = bag.fcurves.new(data_path=path, index=index, group_name=group)
    f.keyframe_points.add(len(values))
    f.keyframe_points.foreach_set('co', [v for frame, value in enumerate(values, 1) for v in (frame, value)])
    for k in f.keyframe_points:
        k.interpolation = 'LINEAR'
    f.update()


def rotations(anim, frame):
    pos = anim.position(frame)
    key, frac = int(pos), pos - int(pos)
    before = anim.sample(frame, key_position=key)
    after = anim.sample(frame, key_position=min(key + 1, anim.keys - 1))
    result = []
    for node, (a, b) in enumerate(zip(before, after)):
        for axis in range(3, 6):
            if anim.descriptors[node * anim.curves + axis]['step']:
                b[axis] = a[axis]
        qa = Euler((-a[3], -a[4], a[5]), 'XYZ').to_quaternion()
        qb = Euler((-b[3], -b[4], b[5]), 'XYZ').to_quaternion()
        if qa.dot(qb) < 0:
            qb.negate()
        q = Quaternion(tuple(x + (y - x) * frac for x, y in zip(qa, qb)))
        q.normalize()
        result.append(q)
    return result


def prepare_pose(anim):
    if anim.curves not in (6, 9):
        raise FormatError(f'Not a verified Euler skeletal record: {anim.curves} channels per node. Inspect the actor report and select another record.')
    anim.prepare(scene_channels=True)
    if getattr(anim, 'discrete_scene_controls', False):
        raise FormatError('This is a discrete scene-control track, not skeletal pose data')


def apply_scene_placement(cut, actor, record_index, rig):
    """Keep CU3 scene movement on the object, separate from its bone pose."""
    flip = Matrix.Diagonal((1, 1, -1, 1))
    identity = [1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
    group = flip @ row_matrix(actor.get('scene_matrix', identity)) @ flip
    base = flip @ row_matrix(actor['records'][record_index]['matrix']) @ flip
    rig.matrix_world = C @ group @ base @ CI
    rig['cu3_placement_status'] = 'Static source AN4 placement.'
    anim = actor.get('visibility_animation')
    if not anim:
        return
    anim.prepare(scene_channels=True)
    if anim.curves < 6 or not anim.node_flags[0] & 3:
        return
    bag = rig.animation_data.action.layers[0].strips[0].channelbag(rig.animation_data.action_slot)
    rows, previous = [], None
    for frame in range(cut.frames):
        v = anim.sample(frame)[0]
        m = Euler((-v[3], -v[4], v[5]), 'XYZ').to_matrix().to_4x4()
        m.translation = (v[0], v[1], -v[2])
        m = C @ group @ m @ Matrix.Diagonal((*base.to_scale(), 1)) @ CI
        loc, quat, scale = m.decompose()
        if previous and previous.dot(quat) < 0:
            quat.negate()
        previous = quat.copy()
        rows.append((loc, quat, scale))
    rig.rotation_mode = 'QUATERNION'
    for prop, count, item in [('location', 3, 0), ('rotation_quaternion', 4, 1), ('scale', 3, 2)]:
        for axis in range(count):
            curve(bag, prop, axis, [r[item][axis] for r in rows])
    rig['cu3_placement_status'] = 'Source animated scene transform, separate from skeletal pose.'


def apply_actor_visibility(cut, actor, objects):
    from .cinematic import visibility
    states = visibility(cut, actor)
    events = [(i+1, not value) for i, value in enumerate(states) if i == 0 or value != states[i-1]]
    for obj in objects:
        obj.animation_data_create()
        action = obj.animation_data.action
        if action:
            slot = obj.animation_data.action_slot
            bag = action.layers[0].strips[0].channelbag(slot)
        else:
            action = bpy.data.actions.new(obj.name + ' source visibility')
            slot, bag = action_bag(action, obj)
            obj.animation_data.action, obj.animation_data.action_slot = action, slot
        for prop in ('hide_viewport', 'hide_render'):
            old = bag.fcurves.find(prop)
            if old:
                bag.fcurves.remove(old)
            fc = bag.fcurves.new(data_path=prop)
            fc.keyframe_points.add(len(events))
            fc.keyframe_points.foreach_set('co', [v for event in events for v in event])
            for key in fc.keyframe_points:
                key.interpolation = 'CONSTANT'
            fc.update()


def create_rig(rigdata, name, collection):
    arm = bpy.data.armatures.new(name + ' source skeleton')
    rig = bpy.data.objects.new(name, arm)
    collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for joint in rigdata['joints']:
        bone = arm.edit_bones.new(joint['name'])
        bone.head, bone.tail = (0, 0, 0), (0, 0.008, 0)
        bone.matrix = C @ row_matrix(joint['inverse_world_bind_row_major']).inverted() @ CI
        if joint['parent'] is not None:
            bone.parent = arm.edit_bones[rigdata['joints'][joint['parent']]['name']]
    bpy.ops.object.mode_set(mode='OBJECT')
    rig.show_in_front = True
    arm.display_type = 'STICK'
    rig['cu3_source_skeleton'] = rigdata.get('source', '')
    rig['cu3_bone_order'] = json.dumps([j['name'] for j in rigdata['joints']])
    rig['cu3_geometry_status'] = 'Source armature only; meshes are external companion assets.'
    return rig


def check_rig(rig, rigdata):
    if rig.type != 'ARMATURE':
        raise FormatError('Select the matching source armature')
    if len(rig.data.bones) != len(rigdata['joints']):
        raise FormatError('Selected armature joint count differs from the source skeleton')
    for j in rigdata['joints']:
        bone = rig.data.bones.get(j['name'])
        if bone is None:
            raise FormatError('Missing source bone: ' + j['name'])
        parent = rigdata['joints'][j['parent']]['name'] if j['parent'] is not None else None
        if (bone.parent.name if bone.parent else None) != parent:
            raise FormatError('Source bone hierarchy differs: ' + j['name'])
        expected = C @ row_matrix(j['inverse_world_bind_row_major']).inverted() @ CI
        error = max(abs(bone.matrix_local[row][col] - expected[row][col]) for row in range(4) for col in range(4))
        if error > 0.0001:
            raise FormatError('Selected rig rest pose differs from the source: ' + j['name'])


def duplicate_rig(source, name, collection):
    objects = [source] + list(source.children_recursive)
    copies = {}
    for obj in objects:
        dup = obj.copy()
        dup.animation_data_clear()
        if obj.type == 'ARMATURE':
            dup.data = obj.data.copy()
        dup.name = name if obj == source else name + ' / ' + obj.name
        collection.objects.link(dup)
        copies[obj] = dup
    for obj, dup in copies.items():
        if obj.parent in copies:
            dup.parent = copies[obj.parent]
        for modifier in dup.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object in copies:
                modifier.object = copies[modifier.object]
    copies[source].parent = None
    return copies[source]


def apply_pose(cut, actor, record_index, rig, rigdata, place_in_scene=False, scene_channels=False):
    rec = actor['records'][record_index]
    anim = rec['animation']
    prepare_pose(anim)
    check_rig(rig, rigdata)
    if len(rigdata['joints']) != anim.nodes:
        raise FormatError('Animation and source skeleton joint counts differ')
    joints = rigdata['joints']
    action = bpy.data.actions.new(f'{cut.name} / {actor["name"]} / record {record_index}')
    action.use_fake_user = True
    action.use_frame_range = True
    action.frame_start, action.frame_end = 1, cut.frames
    action['cu3_source'] = str(cut.path.resolve())
    action['cu3_sha256'] = cut.sha256
    action['cu3_actor'] = actor['name']
    action['cu3_record'] = record_index
    action['cu3_fps'] = cut.fps
    action['cu3_first_key_frame'] = anim.first
    action['cu3_status'] = 'Source skeletal pose; placement and visibility are separate optional tracks. Facial events, cameras and effects remain separate.'
    slot, bag = action_bag(action, rig)
    values = {j['name']: [] for j in joints}
    previous, expected = {}, {}
    for f in range(cut.frames):
        samples = anim.sample(f)
        rots = rotations(anim, f)
        world, cumulative_scales = [], []
        for j, channels in zip(joints, samples):
            flags = anim.node_flags[j['index']]
            local = rots[j['index']].to_matrix().to_4x4()
            if flags & 0x20:
                # NU's row-vector rotation * bind becomes bind * rotation
                # after transposing and conjugating the source Z basis.
                flip = Matrix.Diagonal((1, 1, -1, 1))
                orient = flip @ row_matrix(j['orient_row_major']) @ flip
                orient.translation = (0, 0, 0)
                local = orient @ local
            parent_scale = cumulative_scales[j['parent']] if j['parent'] is not None else Vector((1, 1, 1))
            own_scale = Vector(channels[6:9]) if anim.curves == 9 and flags & 8 else Vector((1, 1, 1))
            cumulative = Vector(tuple(a*b for a,b in zip(parent_scale,own_scale)))
            if anim.curves == 9 and flags & 8:
                local = local @ Matrix.Diagonal((*own_scale, 1))
            if flags & 0x10:
                # Runtime cancels cumulative parent scale in source axes,
                # before translation and Blender's up-axis conversion.
                inverse = Vector(tuple(1/x for x in parent_scale)) if all(abs(x)>1e-8 for x in parent_scale) else Vector((0,0,0))
                local = Matrix.Diagonal((*inverse, 1)) @ local
                cumulative = Vector(tuple(a*b for a,b in zip(cumulative,inverse)))
            local.translation = Vector((channels[0], channels[1], -channels[2]))
            local = C @ local @ CI
            parent_world = world[j['parent']] if j['parent'] is not None else None
            desired = local if parent_world is None else parent_world @ local
            world.append(desired)
            cumulative_scales.append(Vector((1,1,1)) if j['parent'] is None and flags & 0x40 else cumulative)
            bone = rig.data.bones[j['name']]
            kwargs = {}
            if bone.parent:
                kwargs = dict(parent_matrix=world[j['parent']], parent_matrix_local=bone.parent.matrix_local)
            loc, quat, scale = bone.convert_local_to_pose(desired, bone.matrix_local, invert=True, **kwargs).decompose()
            if j['name'] in previous and previous[j['name']].dot(quat) < 0:
                quat.negate()
            previous[j['name']] = quat.copy()
            if not all(math.isfinite(v) for v in (*loc, *quat, *scale)):
                raise FormatError('Non-finite Blender pose')
            values[j['name']].append((loc, quat, scale))
        if f in (0, cut.frames // 4, cut.frames // 2, cut.frames * 3 // 4, cut.frames - 1):
            expected[f + 1] = world
    for name, row in values.items():
        rig.pose.bones[name].rotation_mode = 'QUATERNION'
        for prop, count, component in [('location', 3, 0), ('rotation_quaternion', 4, 1), ('scale', 3, 2)]:
            for axis in range(count):
                curve(bag, f'pose.bones[{json.dumps(name)}].{prop}', axis,
                      [v[component][axis] for v in row], name)
    rig.animation_data_create()
    rig.animation_data.action, rig.animation_data.action_slot = action, slot
    if place_in_scene:
        apply_scene_placement(cut, actor, record_index, rig)
    rig['cu3_actor'] = actor['name']
    rig['cu3_source'] = str(cut.path.resolve())
    return action, expected


def inspect_scene(cut, scene):
    collection = bpy.data.collections.new('CU3 / ' + cut.name)
    scene.collection.children.link(collection)
    scene.render.fps = round(cut.fps)
    scene.render.fps_base = round(cut.fps) / cut.fps
    scene.frame_start, scene.frame_end = 1, cut.frames
    report = cut.report()
    txt = bpy.data.texts.new(cut.name + ' / CU3 report.json')
    txt.write(json.dumps(report, indent=2))
    for actor in cut.actors:
        obj = bpy.data.objects.new(actor['name'], None)
        collection.objects.link(obj)
        obj.empty_display_type, obj.empty_display_size = 'ARROWS', 0.05
        obj.show_name = True
        obj['cu3_actor'] = actor['name']
        obj['cu3_node_index'] = actor['index']
        obj['cu3_parent_node'] = -1 if actor['parent'] is None else actor['parent']
        obj['cu3_records'] = len(actor['records'])
        obj['cu3_status'] = 'Actor reference marker; character mesh is a companion asset.'
        if actor['records']:
            rec = actor['records'][0]
            obj.matrix_world = C @ row_matrix(rec['matrix']) @ CI
            obj['cu3_joint_count'] = rec['animation'].nodes
    scene['cu3_source'] = str(cut.path.resolve())
    scene['cu3_status'] = 'Experimental source-animation import. Camera, effect and event reconstruction remains separate.'
    return collection
