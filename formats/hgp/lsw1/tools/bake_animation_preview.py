"""Bake explicitly bound ANI samples into a new Blender action for research.

This helper is not registered as an addon operator. Use a fresh imported rig,
with preview-pose corrections disabled. No guessing from names or bone counts.
"""
import hashlib
import json
import math
from pathlib import Path

from animation_pose import sample_pose
from animation_records import AnimationRecords


def load_binding(model, animation, binding_path):
    path = Path(binding_path)
    if path.stat().st_size > 128 * 1024:
        raise ValueError('Animation binding is too large')
    binding = json.loads(path.read_text(encoding='utf-8'))
    if binding.get('profile') != 'lsw1-pc-ani-preview-v1':
        raise ValueError('Unknown animation binding profile')
    if binding.get('model_sha256') != hashlib.sha256(model.data).hexdigest():
        raise ValueError('Model differs from the reviewed animation binding')
    with Path(animation).open('rb') as stream:
        data = stream.read(AnimationRecords.MAX_BYTES + 1)
    if binding.get('animation_sha256') != hashlib.sha256(data).hexdigest():
        raise ValueError('Animation differs from the reviewed binding')
    clip = AnimationRecords(data, 'ANI')
    names = binding.get('track_bones')
    if names != [bone['name'] for bone in model.bones] or len(set(names)) != len(names):
        raise ValueError('Binding must name every native bone exactly once in track order')
    fps = binding.get('fps')
    if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not math.isfinite(fps) or not 1 <= fps <= 240:
        raise ValueError('An explicit preview rate between 1 and 240 fps is required')
    if not isinstance(binding.get('evidence'), str) or not binding['evidence'].strip():
        raise ValueError('Binding must describe its ownership evidence and limitations')
    # Refuse unsupported flags/layouts before mutating Blender data.
    sample_pose(model, clip, 1., names)
    return clip, binding


def bake(rig, model, clip, binding, scene):
    import bpy
    from mathutils import Matrix
    if rig.type != 'ARMATURE' or rig.animation_data is not None:
        raise ValueError('Bake into a fresh armature without existing animation')
    names = binding['track_bones']
    if list(rig.data.bones.keys()) != names:
        raise ValueError('Blender bone order differs from the reviewed source')
    if any(abs(bone.matrix_basis[r][c] - (1 if r == c else 0)) > 1e-6
           for bone in rig.pose.bones for r in range(4) for c in range(4)):
        raise ValueError('Disable preview poses before baking ANI playback')
    end = math.ceil(clip.duration) - 1
    if end * model.count > 100000:
        raise ValueError('Preview bake exceeds the frame/bone allocation limit')
    # Evaluate all source samples first, so unsupported data cannot leave a partial action.
    samples = [sample_pose(model, clip, frame, names) for frame in range(1, end + 1)]
    for name, flags in zip(names, clip.flags):
        if flags & 0x10:
            # Otherwise Blender reintroduces parent scale/shear that the native
            # local transform cancels; decomposing that basis loses the pose.
            rig.data.bones[name].inherit_scale = 'NONE'
    conversion = Matrix(((1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1)))
    previous = {}
    maximum_error = 0.
    for frame, worlds in enumerate(samples, 1):
        scene.frame_set(frame)
        for name, native in zip(names, worlds):
            world = conversion @ Matrix([native[i:i+4] for i in range(0,16,4)]).transposed() @ conversion
            bone = rig.pose.bones[name]
            bone.rotation_mode = 'QUATERNION'
            bone.matrix = world
            if name in previous and bone.rotation_quaternion.dot(previous[name]) < 0:
                bone.rotation_quaternion.negate()
            previous[name] = bone.rotation_quaternion.copy()
            bpy.context.view_layer.update()
            maximum_error = max(maximum_error, max(abs(bone.matrix[r][c]-world[r][c])
                                                   for r in range(4) for c in range(4)))
            for channel in ('location', 'rotation_quaternion', 'scale'):
                bone.keyframe_insert(channel, frame=frame, group=name)
    action = rig.animation_data.action
    action.name = 'LSW1 ANI research preview'
    action['lsw1_binding'] = json.dumps(binding)
    # LINEAR interpolation makes the per-frame bake explicit; subframes are approximate.
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    for point in curve.keyframe_points:
                        point.interpolation = 'LINEAR'
    scene.frame_start = 1; scene.frame_end = end
    scene.render.fps = round(binding['fps']); scene.render.fps_base = round(binding['fps']) / binding['fps']
    scene.frame_set(1)
    rig['lsw1_animation_preview'] = 'Explicit research binding; integer samples; no game export or facial playback'
    if maximum_error > 2e-4:
        raise ValueError(f'Blender could not represent sampled pose accurately: {maximum_error}')
    return dict(frames=end, bones=model.count, maximum_matrix_error=maximum_error,
                compensated_bones=[name for name,flags in zip(names,clip.flags) if flags & 0x10],
                fps=binding['fps'], evidence=binding['evidence'])
