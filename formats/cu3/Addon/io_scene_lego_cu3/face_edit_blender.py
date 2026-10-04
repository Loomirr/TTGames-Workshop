"""Bind and export existing source shape keys without evaluated skinning.

Object placement, armature poses, timeline weights and modifiers are previews.
Only edits to TT_Target_### key coordinates become native target offsets.
"""
import copy
import hashlib
import json
import struct
from .cu3 import FormatError


def topology_hash(mesh):
    # Shape coordinates are separate. Connectivity and source vertex order
    # must survive the editing workflow, including polygon winding.
    rows = [len(mesh.vertices), [[int(i) for i in p.vertices] for p in mesh.polygons]]
    return hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest()


def basis_hash(basis):
    return hashlib.sha256(b''.join(struct.pack('<3f', *v.co) for v in basis.data)).hexdigest()


def bind_source(obj, companion, part_id, transform):
    """Call immediately after importing verified native coordinates and keys."""
    part_id = str(part_id)
    part = companion['parts'][part_id]
    keys = obj.data.shape_keys
    if len(obj.data.vertices) != part['vertex_count'] or not keys or keys.reference_key.name != 'Basis':
        raise FormatError('Face editing requires the original Basis and vertex count')
    rotation = transform.to_3x3()
    from mathutils import Vector
    for target in part['targets']:
        key = keys.key_blocks.get(f'TT_Target_{target["id"]:03d}')
        if key is None or key.relative_key != keys.reference_key:
            raise FormatError('Missing or non-Basis-relative native target')
        for vertex, base, delta in zip(key.data, keys.reference_key.data, target['offsets']):
            if tuple(vertex.co) != tuple(base.co + rotation @ Vector(delta)):
                raise FormatError('Bind source before editing the original target coordinates')
    obj['tt_face_source_sha256'] = companion['sha256']
    obj['tt_face_part'] = part_id
    obj['tt_face_topology_sha256'] = topology_hash(obj.data)
    obj['tt_face_basis_sha256'] = basis_hash(keys.reference_key)
    obj['tt_face_rotation'] = json.dumps([list(row) for row in rotation])


def edited_companion(objects, original):
    """Return a native-space companion. Unrepresented parts remain unchanged."""
    from mathutils import Matrix, Vector
    result, seen = copy.deepcopy(original), set()
    for obj in objects:
        if obj.type != 'MESH' or not obj.get('tt_face_source_sha256'):
            continue
        if obj['tt_face_source_sha256'] != original['sha256']:
            raise FormatError('Mixed source GHG files; export each model separately')
        part_id = obj['tt_face_part']
        if part_id in seen:
            raise FormatError(f'Duplicate part {part_id}; choose one actor or editing collection')
        seen.add(part_id)
        if part_id not in result['parts']:
            raise FormatError('Part is missing from the original companion')
        keys = obj.data.shape_keys
        if not keys or not keys.use_relative or keys.reference_key.name != 'Basis':
            raise FormatError('Original relative shape keys are required')
        if topology_hash(obj.data) != obj['tt_face_topology_sha256']:
            raise FormatError('Topology or source vertex order changed')
        if basis_hash(keys.reference_key) != obj['tt_face_basis_sha256']:
            raise FormatError('Basis editing is not supported by this target-only writer')
        rotation = Matrix(json.loads(obj['tt_face_rotation']))
        inverse = rotation.inverted()
        part = result['parts'][part_id]
        expected_names = {'Basis'} | {f'TT_Target_{t["id"]:03d}' for t in part['targets']}
        if set(k.name for k in keys.key_blocks) != expected_names:
            raise FormatError('Native targets were added, removed or renamed')
        for target in part['targets']:
            key = keys.key_blocks[f'TT_Target_{target["id"]:03d}']
            if key.relative_key != keys.reference_key:
                raise FormatError('Native targets must stay relative to Basis')
            for i, (vertex, base, delta) in enumerate(zip(key.data, keys.reference_key.data, target['offsets'])):
                # Preserve original packed offsets for unchanged coordinates.
                # Subtracting rounded Blender coordinates for every vertex
                # would otherwise introduce noise even in a no-op export.
                expected = base.co + rotation @ Vector(delta)
                if tuple(vertex.co) != tuple(expected):
                    target['offsets'][i] = list(inverse @ (vertex.co - base.co))
    if not seen:
        raise FormatError('No meshes bound to a native facial source were selected')
    return result
