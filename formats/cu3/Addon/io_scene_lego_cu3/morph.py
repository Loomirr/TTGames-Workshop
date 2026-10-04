"""Recover observed NXG/DX11 relative-position targets using extractor offsets.

This is a companion to the private mesh extractor, not a general GHG reader.
Target IDs are preserved. Observed ANI-D BSA control curves are decoded below;
semantic expression names remain unknown. The old extractor discards the arrays.
"""
import math
import re
from .cu3 import Reader, FormatError
from .cu3 import Animation


def decode_runs(data, start, size, vertices):
    """BE (repeat_count, dx, dy, dz) records, including a zero terminal run."""
    r = Reader(data)
    if size % 16 or start < 0 or start + size > len(data):
        raise FormatError('Relative-position run buffer outside file or misaligned')
    offsets = []
    for at in range(start, start + size, 16):
        count, x, y, z = r.get('I3f', at)
        if not all(math.isfinite(v) for v in (x, y, z)):
            raise FormatError('Non-finite relative position')
        if count > vertices - len(offsets):
            raise FormatError('Relative-position run exceeds vertex count')
        if count == 0 and (at != start + size - 16 or any((x, y, z))):
            raise FormatError('Invalid zero-length relative-position run')
        offsets.extend([[x, y, z] for _ in range(count)])
    if len(offsets) != vertices:
        raise FormatError('Relative-position runs do not cover the mesh part')
    return offsets


def read_targets(data, terminal, count, vertices, dx):
    r = Reader(data)
    if not 0 < count <= 4096 or not 0 < vertices <= 1000000:
        raise FormatError('Unreasonable relative-position counts')
    table = terminal - count * 8
    entries = [r.get('2I', table + i * 8) for i in range(count)]
    if r.get('I', terminal) or any(flag != 1 for flag, _ in entries):
        raise FormatError('Unrecognised relative-position target table')
    ids = [idx for _, idx in entries]
    if len(set(ids)) != count:
        raise FormatError('Duplicate relative-position target ID')
    if dx and data[terminal + 4:terminal + 8] != b'ROTV':
        raise FormatError('DX11 relative-position array marker missing')
    at, targets = terminal + (8 if dx else 4), []
    for target in ids:
        record = at
        dense_count = r.get('I', at)
        at += 4
        if dense_count:
            if dense_count != vertices:
                raise FormatError('Dense relative-position count differs from mesh')
            offsets = [list(r.get('3f', at + i * 12)) for i in range(vertices)]
            at += vertices * 12
            trailer = data[at:at + 21]
            at += 21
            encoding = 'dense_be_vec3'
        else:
            at += 4 if dx else 13
            size = r.get('I', at)
            at += 4
            offsets = decode_runs(data, at, size, vertices)
            at += size
            tail = at
            if dx:
                # Two observed ROTV fields; preserve the unknown companion.
                if data[at:at + 4] != b'ROTV':
                    raise FormatError('DX11 relative-position companion marker missing')
                at += 20
            else:
                n = r.get('I', at)
                if n > 65536:
                    raise FormatError('Unreasonable relative-position companion count')
                at += 4 + n * 4
            trailer = data[tail:at]
            encoding = 'rle_be_count_vec3'
        if at > len(data) or not all(math.isfinite(v) for d in offsets for v in d):
            raise FormatError('Invalid relative-position record')
        targets.append(dict(id=target, record_offset=record, encoding=encoding,
                            companion_hex=trailer.hex(), offsets=offsets))
    return dict(table_offset=table, end_offset=at, vertex_count=vertices, targets=targets)


def extract_morphs(data, log):
    """Fail on unsupported observed morph blocks; never silently relabel IDs."""
    r = Reader(data)
    mesh_at = data.find(b'HSEM')
    if mesh_at < 0:
        raise FormatError('MESH block missing')
    version = r.get('I', mesh_at + 4)
    if version not in (0xa9, 0xaf):
        raise FormatError(f'Relative-position layout not verified for MESH {version:#x}')
    blocks = re.split(r'^([0-9a-f]{8})\s+Part 0x([0-9a-f]+)\s*$', log, flags=re.M)
    parts = {}
    for start, idx, block in zip(blocks[1::3], blocks[2::3], blocks[3::3]):
        marker = re.search(r'([0-9a-f]{8})\s+Relative Position Lists: 0x([0-9a-f]+)', block)
        if not marker:
            continue
        terminal, count = (int(x, 16) for x in marker.groups())
        nv = re.search(r'Number Vertices: 0x([0-9a-f]+)', block)
        if not nv:
            raise FormatError('Morph part has no vertex count')
        result = read_targets(data, terminal, count, int(nv[1], 16), version == 0xaf)
        # Cross-check logged packed buffer boundaries against the new decoder.
        logged = {int(m, 16) for m in re.findall(r'([0-9a-f]{8})\s+Size of Relative Positions:', block)}
        decoded = {t['record_offset'] + (8 if version == 0xaf else 17)
                   for t in result['targets'] if t['encoding'].startswith('rle')}
        if logged != decoded:
            raise FormatError('Morph decoder and extractor buffer boundaries differ')
        parts[str(int(idx, 16))] = result
    return dict(schema='tt.relative-position-targets.v1', mesh_version=version,
                semantics='Source-space additive vertex offsets; observed BSA ANI-D weights are separate', parts=parts)


def add_shape_keys(obj, targets, transform):
    """Attach editable keys to an existing mesh with verified source vertex order."""
    from mathutils import Vector
    if len(obj.data.vertices) != targets['vertex_count']:
        raise FormatError('Blender/source morph vertex count differs')
    if obj.data.shape_keys:
        raise FormatError('Mesh already has shape keys; refusing to replace them')
    basis = obj.shape_key_add(name='Basis', from_mix=False)
    rotation = transform.to_3x3()
    for target in targets['targets']:
        key = obj.shape_key_add(name=f'TT_Target_{target["id"]:03d}', from_mix=False)
        key.slider_min, key.slider_max = -1.0, 1.0
        # Blender versions differ in the initial weight. Static companions
        # must start in Basis, rather than summing every expression at 1.
        key.value = 0.0
        for vertex, base, delta in zip(key.data, basis.data, target['offsets']):
            vertex.co = base.co + rotation @ Vector(delta)
    obj['cu3_morph_status'] = 'Recovered source offsets. Target names and CU3 weight timing unresolved.'
    obj['cu3_morph_count'] = len(targets['targets'])
    return len(targets['targets'])


def actor_morph_animation(cut, actor):
    """Observed AN4 node +36 -> BSA header -> 53-channel ANI-D scalar block."""
    relative = cut.reader.get('I', actor['offset'] + 36, '<')
    if not relative:
        return None
    at = cut.root + relative
    if cut.reader.data[at:at + 4] != b'\0ASB':
        raise FormatError('Unsupported AN4 facial-control block')
    header_size = cut.reader.get('I', at + 4, '<')
    if header_size != 20:
        raise FormatError('Unsupported BSA facial header')
    padded, size = cut.reader.get('2I', at + 8, '<')
    if size < header_size + 80 or not size <= padded <= size + 4 or at + padded > cut.blob_end:
        raise FormatError('BSA facial block outside animation tree')
    animation = Animation(cut.reader, at + header_size, at + size)
    animation.prepare(morph_channels=True)
    return animation


def animate_shape_keys(obj, animation, frames):
    """Use preserved target IDs as scalar indices; do not clamp source weights."""
    import bpy
    keys = obj.data.shape_keys
    if not keys:
        raise FormatError('No recovered shape keys on mesh')
    action = bpy.data.actions.new(obj.name + ' / source facial targets')
    slot = action.slots.new('KEY', keys.name)
    bag = action.layers.new('Source facial weights').strips.new(type='KEYFRAME').channelbag(slot, ensure=True)
    rows = [animation.sample(f)[0] for f in range(frames)]
    for key in keys.key_blocks:
        if not key.name.startswith('TT_Target_'):
            continue
        idx = int(key.name.rsplit('_', 1)[1])
        values = [row[idx] for row in rows]
        key.slider_min = min(-1.0, min(values))
        key.slider_max = max(1.0, max(values))
        fc = bag.fcurves.new(data_path=key.path_from_id('value'))
        fc.keyframe_points.add(frames)
        fc.keyframe_points.foreach_set('co', [v for f, value in enumerate(values, 1) for v in (f, value)])
        for point in fc.keyframe_points:
            point.interpolation = 'LINEAR'
        fc.update()
    keys.animation_data_create()
    keys.animation_data.action, keys.animation_data.action_slot = action, slot
    obj['cu3_morph_status'] = 'Source target offsets + observed BSA 53-channel weights. Game shader details unresolved.'
    return action
