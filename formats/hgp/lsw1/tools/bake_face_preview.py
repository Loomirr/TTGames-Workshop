"""Bake an explicitly reviewed LSW1 PC BSA/HGP pairing, at integer native frames.

Source-tree research helper for fresh imported shapes. No automatic ownership,
gameplay timing, unsupported-channel padding, or BSA export is inferred here.
"""
import hashlib
import json
import math
from pathlib import Path

from animation_records import AnimationRecords
from face_channels import sample_layers


def prepare(model, clip, binding):
    if not isinstance(binding, dict) or binding.get('profile') != 'lsw1-pc-bsa-preview-v1' or clip.family != 'BSA':
        raise ValueError('Expected an explicit LSW1 PC BSA preview binding')
    if binding.get('model_sha256') != hashlib.sha256(model.data).hexdigest():
        raise ValueError('Model differs from the reviewed facial binding')
    if binding.get('animation_sha256') != clip.sha256:
        raise ValueError('BSA differs from the reviewed facial binding')
    layers = binding.get('layers')
    if (not isinstance(layers, list) or not layers or len(layers) > 32
        or any(type(i) is not int or not 0 <= i < model.layer_count for i in layers)
        or len(set(layers)) != len(layers)):
        raise ValueError('Binding needs unique available native layer IDs')
    fps = binding.get('fps')
    if type(fps) not in (int, float) or not math.isfinite(fps) or not 1 <= fps <= 240:
        raise ValueError('Choose an explicit preview rate from 1 to 240 fps')
    if not isinstance(binding.get('evidence'), str) or not binding['evidence'].strip():
        raise ValueError('Describe the pairing evidence and remaining ownership limits')
    parts = [part for layer in layers for part in model.layer_meshes(layer) if part.get('morph')]
    if not parts or {part['layer'] for part in parts} != set(layers):
        raise ValueError('Every declared layer must contain native facial targets')
    for part in parts:
        ids = [target['id'] for target in part['morph']['targets']]
        if (part['layer'] >= clip.tracks or not ids or len(set(ids)) != len(ids)
            or any(type(i) is not int or not 0 <= i < clip.components for i in ids)):
            raise ValueError('BSA lacks explicit channels for the requested targets; padding is unverified')
    end = math.ceil(clip.duration) - 1
    if end * sum(len(p['morph']['targets']) for p in parts) > 100000:
        raise ValueError('Facial bake exceeds the frame/target limit')
    frames = [sample_layers(clip, frame, layers) for frame in range(1, end + 1)]
    if any(abs(value) > 10 for frame in frames for layer in frame for value in layer):
        raise ValueError('Native weight exceeds Blender shape-key slider limits')
    return parts, frames


def load_binding(model, animation, path):
    with Path(path).open('rb') as stream:
        raw = stream.read(128 * 1024 + 1)
    if len(raw) > 128 * 1024:
        raise ValueError('Facial binding is too large')
    binding = json.loads(raw)
    if not isinstance(binding, dict):
        raise ValueError('Facial binding must be a JSON object')
    with Path(animation).open('rb') as stream:
        clip = AnimationRecords(stream.read(AnimationRecords.MAX_BYTES + 1), 'BSA')
    prepare(model, clip, binding)
    return clip, binding


def bake(objects, model, clip, binding, scene):
    parts, frames = prepare(model, clip, binding)
    key = lambda p: (p['layer'], p['geometry'], p['primitive'])
    sources = {key(p): p for p in parts}
    targets = []
    seen = set()
    for obj in objects:
        if obj.type != 'MESH' or not obj.data.shape_keys:
            continue
        identity = (int(obj['lsw1_layer_index']), int(obj['lsw1_geometry_offset'], 16),
                    int(obj['lsw1_primitive_offset'], 16))
        if identity not in sources or identity in seen:
            raise ValueError('Imported facial meshes differ from the explicit binding')
        part = sources[identity]; seen.add(identity)
        shapes = obj.data.shape_keys
        names = ['Basis'] + [f"morph {t['id']}" for t in part['morph']['targets']]
        if list(shapes.key_blocks.keys()) != names or len(obj.data.vertices) != len(part['vertices']):
            raise ValueError('Imported shape targets differ from source IDs/topology')
        if shapes.animation_data is not None or any(k.value != 0 for k in shapes.key_blocks[1:]):
            raise ValueError('Use fresh unanimated shape keys with every weight at zero')
        targets.append((obj, part))
    if seen != set(sources):
        raise ValueError('Import all facial parts from the declared layers')
    # Complete source and object validation before changing any action.
    for obj, part in targets:
        layer = binding['layers'].index(part['layer'])
        for target in part['morph']['targets']:
            shape = obj.data.shape_keys.key_blocks[f"morph {target['id']}"]
            values = [frame[layer][target['id']] for frame in frames]
            shape.slider_min = min(0., min(values)); shape.slider_max = max(1., max(values))
            for frame, value in enumerate(values, 1):
                shape.value = value
                shape.keyframe_insert('value', frame=frame)
        action = obj.data.shape_keys.animation_data.action
        action.name = 'LSW1 decoded BSA preview'
        action['lsw1_binding'] = json.dumps(binding)
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for point in curve.keyframe_points:
                            point.interpolation = 'LINEAR'
        obj['lsw1_face_animation_status'] = 'Decoded BSA integer samples; explicit research pairing'
    scene.frame_start = 1; scene.frame_end = len(frames)
    scene.render.fps = round(binding['fps'])
    scene.render.fps_base = round(binding['fps']) / binding['fps']
    scene.frame_set(1)
    return dict(frames=len(frames), meshes=len(targets), binding=binding,
                scope='Decoded integer BSA samples; subframes approximate; gameplay ownership/rate unverified')
