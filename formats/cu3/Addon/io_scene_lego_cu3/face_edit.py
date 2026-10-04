"""Constrained native facial-target editing. No topology or stream relocation.

The companion comes from morph.extract_morphs and must carry the exact source
SHA-256. Repeated offsets remain repeated: unsupported run splitting is rejected.
This verifies binary layout and decoded positions, not the game's renderer.
"""
import hashlib
import math
import struct
from .cu3 import FormatError
from .morph import read_targets


def digest(data):
    return hashlib.sha256(data).hexdigest()


def packed_vector(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise FormatError('Each target vertex needs exactly three coordinates')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise FormatError('Target coordinates must be finite numbers')
    try:
        packed = struct.pack('>3f', *value)
    except (OverflowError, struct.error) as exc:
        raise FormatError('Target coordinates do not fit float32') from exc
    if not all(math.isfinite(v) for v in struct.unpack('>3f', packed)):
        raise FormatError('Target coordinates do not fit finite float32')
    return packed


def original_parts(data, companion):
    if companion.get('schema') != 'tt.relative-position-targets.v1':
        raise FormatError('Unsupported facial companion schema')
    if companion.get('sha256') != digest(data):
        raise FormatError('Source hash differs; decode a companion from this exact GHG')
    version = companion.get('mesh_version')
    mesh_at = data.find(b'HSEM')
    if version not in (0xa9, 0xaf) or mesh_at < 0 or struct.unpack_from('>I', data, mesh_at + 4)[0] != version:
        raise FormatError('Unsupported or mismatched MESH version')
    parts = companion.get('parts')
    if not isinstance(parts, dict) or not parts:
        raise FormatError('No editable facial parts')
    result, regions = {}, []
    for key, part in parts.items():
        targets = part['targets']
        original = read_targets(data, part['table_offset'] + len(targets) * 8,
                                len(targets), part['vertex_count'], version == 0xaf)
        # The sidecar may edit offset values only. Addresses, IDs, unknown data
        # and ordering must still describe the exact native source records.
        for field in ('table_offset', 'end_offset', 'vertex_count'):
            if part[field] != original[field]:
                raise FormatError(f'Part {key}: altered target structure')
        for target, before in zip(targets, original['targets']):
            for field in ('id', 'record_offset', 'encoding', 'companion_hex'):
                if target[field] != before[field]:
                    raise FormatError(f'Part {key}: altered {field}')
        regions.append((original['table_offset'], original['end_offset']))
        result[key] = original
    regions.sort()
    if any(right[0] < left[1] for left, right in zip(regions, regions[1:])):
        raise FormatError('Overlapping facial part regions')
    return result


def patch_targets(data, companion):
    """Return a separate byte string and manifest; never mutate the source."""
    originals = original_parts(data, companion)
    output, changes, writable = bytearray(data), [], set()
    dx = companion['mesh_version'] == 0xaf
    for part_id, part in companion['parts'].items():
        original = originals[part_id]
        vertices = original['vertex_count']
        for edited, before in zip(part['targets'], original['targets']):
            values = edited['offsets']
            if len(values) != vertices:
                raise FormatError(f'Part {part_id}, target {before["id"]}: vertex count changed')
            packed = [packed_vector(v) for v in values]
            record = before['record_offset']
            writes = []
            if before['encoding'] == 'dense_be_vec3':
                writes = [(record + 4 + i * 12, p) for i, p in enumerate(packed)]
            else:
                size_at = record + (8 if dx else 17)
                size = struct.unpack_from('>I', data, size_at)[0]
                first, index = size_at + 4, 0
                for at in range(first, first + size, 16):
                    count = struct.unpack_from('>I', data, at)[0]
                    if count:
                        value = packed[index]
                        if any(p != value for p in packed[index:index + count]):
                            raise FormatError(f'Part {part_id}, target {before["id"]}: vertices '
                                              f'{index}..{index + count - 1} share one native run; '
                                              'this edit requires stream repacking')
                        writes.append((at + 4, value))
                    index += count
            target_bytes = 0
            for at, value in writes:
                if bytes(output[at:at + 12]) != value:
                    target_bytes += sum(a != b for a, b in zip(data[at:at + 12], value))
                    output[at:at + 12] = value
                    writable.update(range(at, at + 12))
            if target_bytes:
                changes.append(dict(part=part_id, target_id=before['id'],
                                    encoding=before['encoding'], changed_bytes=target_bytes))
        after = read_targets(output, original['table_offset'] + len(original['targets']) * 8,
                             len(original['targets']), vertices, dx)
        for expected, actual in zip(part['targets'], after['targets']):
            if any(packed_vector(a) != packed_vector(b) for a, b in zip(expected['offsets'], actual['offsets'])):
                raise FormatError('Native output failed target round-trip validation')
    # Whole-file invariant, including all unknown companions and material blocks.
    changed = [i for i, (a, b) in enumerate(zip(data, output)) if a != b]
    if len(output) != len(data) or any(i not in writable for i in changed):
        raise FormatError('Writer touched bytes outside declared offset payloads')
    manifest = dict(schema='tt.face-target-patch.v1', source_sha256=digest(data),
                    output_sha256=digest(output), file_size=len(data),
                    changed_bytes=len(changed), targets=changes,
                    validation='Reparsed targets; unchanged file size and all non-offset bytes.',
                    game_tested=False,
                    limitations=['Same vertex count, target IDs and run structure only.',
                                 'Unknown companions, normals, materials and timing are preserved, not regenerated.'])
    return bytes(output), manifest
