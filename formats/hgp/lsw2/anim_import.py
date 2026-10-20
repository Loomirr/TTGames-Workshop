"""Turn LEGO Star Wars II animation clips into Blender actions on an imported armature.

Only clips proven to belong to the model's skeleton are used: declared by the character's own .txt
with a matching node count, or holding its fixed bones at the skeleton's bind translations. The user
may opt in to unproven clips of the same bone count; such actions say so in `lsw2_proof`. Each becomes an action named after the clip,
keyed on every frame, spaced by the clip's own rate (the character .txt's fpsec, else 30, flagged).
"""
import os

import bpy
from mathutils import Quaternion

from . import anim
from .importer import to_blender_matrix


def _fcurve_store(action, arm):
    """F-curve collection of an action for this armature (Blender 4.4+ slots, or the older API)."""
    if hasattr(action, 'slots'):
        slot = action.slots.new(id_type='OBJECT', name=arm.name)
        layer = action.layers.new('Layer')
        strip = layer.strips.new(type='KEYFRAME')
        return strip.channelbag(slot, ensure=True).fcurves, slot
    return action.fcurves, None


def _world(locals_, bones):
    out = []
    for j, b in enumerate(bones):
        m = locals_[j]
        if b['parent'] >= 0:
            p = out[b['parent']]
            m = [sum(m[r * 4 + k] * p[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4)]
        out.append(m)
    return out


def _find(folder, name):
    """`name`.an3 in `folder`, matched without regard to case."""
    try:
        for entry in os.listdir(folder):
            if entry.lower() == name + '.an3':
                return os.path.join(folder, entry)
    except OSError:
        pass
    return None


def candidates(model_path, folder_override=''):
    """[(clip name, path, declared)]: the clips the model's own .txt declares (looked up beside the model,
    then in chars/commonanims), then any other clip beside the model (or in the chosen folder)."""
    folder = folder_override or os.path.dirname(os.path.abspath(model_path))
    common = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(model_path))), 'commonanims')
    txt_path = os.path.splitext(model_path)[0] + '.txt'
    declared = []
    if os.path.exists(txt_path):
        with open(txt_path, encoding='latin-1') as f:
            declared = anim.declared_clips(f.read())
    out, seen = [], set()
    for name in declared:
        path = _find(folder, name) or _find(common, name)
        if path:
            out.append((name, path, True))
            seen.add(os.path.normcase(path))
    for entry in sorted(os.listdir(folder)):
        path = os.path.join(folder, entry)
        if entry.lower().endswith('.an3') and os.path.normcase(path) not in seen:
            out.append((os.path.splitext(entry)[0].lower(), path, False))
    return out, txt_path


def import_clips(context, arm, model, model_path, folder_override='', report=print, unproven=False):
    """Actions for every proven clip; returns (made, refused) lists.

    Proof, in order: the character's own .txt declares the clip and its node count equals the bone
    count; or the bones the clip holds still sit at this skeleton's bind translations (anim.ownership).
    With `unproven`, other clips of the same bone count are bound by bone order and marked."""
    clips, txt_path = candidates(model_path, folder_override)
    rates = {}
    if os.path.exists(txt_path):
        with open(txt_path, encoding='latin-1') as f:
            rates = anim.frame_rates(f.read())
    scene_fps = context.scene.render.fps / context.scene.render.fps_base
    bone_names = {int(b['lsw2_bone']): b.name for b in arm.data.bones if 'lsw2_bone' in b}
    rest = {i: arm.data.bones[n].matrix_local for i, n in bone_names.items()}
    made, refused = [], []
    for clip_name, path, declared in clips:
        name = os.path.basename(path)
        try:
            with open(path, 'rb') as f:
                clip = anim.Clip(f.read(), name)
        except (anim.AnimationError, OSError) as e:
            refused.append(f'{name}: {e}')
            continue
        n = clip.nodes
        bones = model.bones[:n]
        # a clip may drive only the first bones when every extra one is a trailing root (or hangs under
        # one), such as a tauntaun's 'IK' or a Jedi's '|LightSabre': those stay at rest. Then the bones it
        # drives must also pass the proportions test, declared or not.
        extra_ok = n < len(model.bones) and all(b['parent'] < 0 or b['parent'] >= n for b in model.bones[n:])
        if n != len(model.bones) and not extra_ok:
            refused.append(f'{name}: {n} nodes for {len(model.bones)} bones')
            continue
        share = anim.ownership(clip, bones)
        if n == len(model.bones):
            proof = 'declared' if declared else 'proportions' if share >= anim.OWNED else None
        else:
            proof = (f'first {n} bones' + (', declared' if declared else '')) if share >= anim.OWNED else None
        if proof is None and not (unproven and n == len(model.bones)):
            refused.append(f'{name}: not declared by the character file, and {share:.0%} of its fixed bones sit '
                           f'at this skeleton\'s bind pose')
            continue
        fps = rates.get(clip_name.lower())
        assumed = fps is None
        fps = fps or 30.0
        step = scene_fps / fps
        action = bpy.data.actions.new(clip_name)
        action.use_fake_user = True
        action['lsw2_fps'] = fps
        action['lsw2_fps_assumed'] = assumed
        action['lsw2_proof'] = proof or 'unproven: bound by bone order at the user\'s request'
        action['lsw2_source'] = path
        fcurves, slot = _fcurve_store(action, arm)
        series = {(j, path, k): [] for j in range(n) for path, size in
                  (('location', 3), ('rotation_quaternion', 4), ('scale', 3)) for k in range(size)}
        previous = {}
        # each key comes from the clip's own local matrix, relative to the bone's rest: nothing posed is
        # inverted (clips may scale a bone to zero to hide it)
        rest_local = {j: (rest[b['parent']].inverted() @ rest[j]) if b['parent'] >= 0 else rest[j]
                      for j, b in enumerate(bones)}
        rest_inverse = {j: m.inverted() for j, m in rest_local.items()}
        for frame in range(clip.frames):
            locals_ = clip.local_matrices(frame, bones)
            for j, b in enumerate(bones):
                basis = rest_inverse[j] @ to_blender_matrix(locals_[j])
                loc, scl = basis.to_translation(), basis.to_scale()
                if min(abs(x) for x in scl) < 1e-6:
                    rot = previous.get(j, Quaternion()).copy()   # a hidden (zero-scale) bone: hold its turn
                else:
                    rot = basis.to_3x3().normalized().to_quaternion()
                if j in previous and previous[j].dot(rot) < 0:
                    rot.negate()                         # neighbouring keys in the same hemisphere
                previous[j] = rot
                t = frame * step + 1.0
                for k in range(3):
                    series[(j, 'location', k)].append((t, loc[k]))
                    series[(j, 'scale', k)].append((t, scl[k]))
                for k in range(4):
                    series[(j, 'rotation_quaternion', k)].append((t, rot[k]))
        for (j, path, k), keys in series.items():
            fc = fcurves.new(f'pose.bones["{bone_names[j]}"].{path}', index=k)
            fc.keyframe_points.add(len(keys))
            fc.keyframe_points.foreach_set('co', [v for key in keys for v in key])
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
            fc.update()
        action.frame_range = (1.0, max(1.0, (clip.frames - 1) * step + 1.0))
        made.append((clip_name, action, slot))
    if made:
        for pb in arm.pose.bones:
            pb.rotation_mode = 'QUATERNION'
        pick = next((m for m in made if m[0].lower() == 'idle'), made[0])
        arm.animation_data_create()
        arm.animation_data.action = pick[1]
        if pick[2] is not None:
            arm.animation_data.action_slot = pick[2]
    if refused:
        report(f'{len(refused)} clip(s) not imported; first: {refused[0]}')
    return [m[0] for m in made], refused
