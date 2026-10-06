"""Bounded observed HGOL skeletons, with explicit candidate ownership checks."""
from pathlib import Path
import hashlib
import json
import math
from .cu3 import Reader, FormatError


SUPPORTED_VERSIONS = (10, 12, 15, 16, 17)
MAX_CANDIDATE_ATTEMPTS = 4096


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def skeleton_identity(rig):
    """Names, hierarchy, transforms and ownership all contribute to identity.

    These digests are tool metadata, not native archive or shader hashes. File
    offsets are deliberately excluded, so exact repeated tables can coalesce.
    """
    binding = _digest(rig['joints'])
    ownership = {key: rig.get(key) for key in ('version', 'byte_order', 'points_of_interest',
                 'pre_poi_bytes', 'post_poi_bytes', 'opaque_tail_hex', 'layer_metadata', 'layers')}
    ownership['binding_sha256'] = binding
    return {'schema': 'tt.skeleton-identity.v1', 'binding_sha256': binding,
            'ownership_sha256': _digest(ownership)}


def attachment_locator(rig, logical):
    """Validate a consumed locator; unused native sentinels remain unchanged."""
    remap, points = rig.get('post_poi_bytes', []), rig.get('points_of_interest', [])
    if not isinstance(logical,int) or not 0 <= logical < len(remap):
        raise FormatError('Attachment locator is outside the native remap table')
    index = remap[logical]
    if not isinstance(index,int) or not 0 <= index < len(points):
        raise FormatError('Attachment locator remap is outside the native point table')
    point = points[index]
    joint = point.get('joint')
    if not isinstance(joint,int) or not 0 <= joint < len(rig['joints']):
        raise FormatError('Attachment locator has no supported native joint binding: ' + str(joint))
    return point


def _validate(rig):
    joints = rig['joints']
    if not 0 < len(joints) <= 255:
        raise FormatError('Unsupported GHG joint count')
    for i, joint in enumerate(joints):
        if not isinstance(joint['name'],str):
            raise FormatError('Invalid skeleton bone name')
        if joint['index'] != i or (joint['parent'] is not None and not 0 <= joint['parent'] < i):
            raise FormatError('Skeleton indices/parents are incompatible')
        for field in ('local_bind_row_major', 'inverse_world_bind_row_major'):
            if len(joint[field]) != 16 or not all(math.isfinite(x) for x in joint[field]):
                raise FormatError('Invalid or non-finite skeleton bind matrix')
        for field, count in (('orient_row_major', 16), ('locator_offset', 3)):
            if field in joint and (len(joint[field]) != count or not all(math.isfinite(x) for x in joint[field])):
                raise FormatError('Invalid or non-finite skeleton orientation/locator')
    if len({joint['name'] for joint in joints}) != len(joints):
        raise FormatError('Duplicate skeleton bone names')
    for point in rig.get('points_of_interest', []):
        if len(point['matrix']) != 16 or not all(math.isfinite(x) for x in point['matrix']):
            raise FormatError('Invalid or non-finite native locator matrix')


def _display_owned(rig, display):
    """Check native layer references against the already decoded model display.

    This is structural evidence only. If several different skeletons still
    reference valid display tables, their ownership has not been resolved.
    """
    metadata = rig.get('layer_metadata', [])
    for index, layer in enumerate(rig.get('layers', [])):
        first = layer['metadata_index']
        last = first + layer['rigids'] + layer['skins']
        if first < 0 or last > len(metadata):
            raise FormatError('Skeleton layer exceeds its native ownership table')
        for item in metadata[first:last]:
            if item['layer'] != index or not 0 <= item['special'] < len(display['specials']):
                raise FormatError('Skeleton layer references an incompatible display instance')
            if item['kind'] == 0 and not 0 <= item['joint'] < len(rig['joints']):
                raise FormatError('Skeleton rigid ownership references an invalid joint')


def _offsets(candidates):
    return ', '.join(f"0x{candidate['hgol_offset']:x}" +
                     (f" (NTBL 0x{candidate['name_table_offset']:x})" if candidate.get('name_table_offset') is not None else '')
                     for candidate in candidates)


def select_skeleton(candidates, expected_nodes=None, *, display=None, identity=None):
    """Fail closed on distinct bind tables or unresolved resource ownership."""
    if identity is not None and not isinstance(identity,dict):
        raise FormatError('Retained native skeleton identity must be a structured record')
    compatible, rejected = [], []
    for candidate in candidates:
        try:
            _validate(candidate)
            if display is not None:
                _display_owned(candidate, display)
            candidate['identity'] = skeleton_identity(candidate)
            if identity is not None:
                if (identity.get('schema') != 'tt.skeleton-identity.v1' or
                        any(identity.get(key) != candidate['identity'][key] for key in ('binding_sha256', 'ownership_sha256'))):
                    raise FormatError('Candidate differs from the retained native skeleton identity')
            compatible.append(candidate)
        except (ValueError, KeyError, TypeError) as error:
            rejected.append({'offset': candidate.get('hgol_offset'), 'issue': str(error)})
    if not compatible:
        details = '; '.join(f"0x{item['offset']:x}: {item['issue']}" for item in rejected if isinstance(item['offset'], int))
        raise FormatError('No supported matching GHG skeleton (HGOL 10/12 or ROTV layouts 15/16/17)' + (': ' + details if details else ''))
    identities = {candidate['identity']['ownership_sha256'] for candidate in compatible}
    if len(identities) != 1:
        same_bind = len({candidate['identity']['binding_sha256'] for candidate in compatible}) == 1
        conflict = 'identical bind tables have conflicting resource/layer ownership' if same_bind else 'conflicting native bind tables'
        raise FormatError('Ambiguous GHG skeleton: ' + conflict + '; candidates at ' + _offsets(compatible))
    rig = compatible[0]
    if expected_nodes is not None and len(rig['joints']) != expected_nodes:
        raise FormatError(f"Skeleton has {len(rig['joints'])} joints; animation has {expected_nodes}; candidate at " + _offsets([rig]))
    rig['candidate_offsets'] = sorted({candidate['hgol_offset'] for candidate in compatible})
    rig['candidate_name_table_offsets'] = sorted({candidate['name_table_offset'] for candidate in compatible
                                                 if candidate.get('name_table_offset') is not None})
    rig['selection'] = {'reason': 'identical_duplicate_tables' if len(compatible) > 1 else 'unique_compatible_table',
                        'candidate_offsets': rig['candidate_offsets'],
                        'display_ownership_checked': display is not None,
                        'retained_identity_checked': identity is not None, 'rejected_candidates': rejected}
    return rig


def read_skeleton(path, expected_nodes=None, *, display=None, identity=None):
    path = Path(path)
    if path.suffix.lower() == '.json':
        rig = json.loads(path.read_text(encoding='utf-8'))
        _validate(rig)
        if expected_nodes is not None and len(rig['joints']) != expected_nodes:
            raise FormatError(f"Skeleton has {len(rig['joints'])} joints; animation has {expected_nodes}")
        if display is not None:
            _display_owned(rig, display)
        # JSON can describe an original file, but cannot establish its byte order.
        rig.setdefault('byte_order', None)
        rig['identity'] = skeleton_identity(rig)
        if identity is not None and identity != rig['identity']:
            raise FormatError('JSON skeleton differs from the retained native skeleton identity')
        return rig

    data = path.read_bytes()
    reader = Reader(data)
    source_sha256 = hashlib.sha256(data).hexdigest()
    candidates, errors, name_tables = [], [], []

    def markers(marker):
        cursor = 0
        while True:
            at = data.find(marker, cursor)
            if at < 0:
                return
            cursor = at + len(marker)
            yield at

    for at in markers(b'LBTN'):
        try:
            size = reader.get('I', at + 8)
        except FormatError:
            continue
        if size and at + 12 + size <= len(data):
            name_tables.append((at, at + 12, size))
            if len(name_tables) > MAX_CANDIDATE_ATTEMPTS:
                raise FormatError('HGOL name-table candidate limit exceeded')

    def parse(at, version, name_table):
        pos, joints = at + 8, []
        typed = version in (12, 15, 16, 17)
        table_offset, names, names_size = name_table if name_table is not None else (None, None, None)

        def take(size):
            nonlocal pos
            if size < 0 or size > len(data) - pos:
                raise FormatError('HGOL field exceeds file bounds')
            value = data[pos:pos + size]
            pos += size
            return value

        def array_count(maximum=65536):
            nonlocal pos
            if typed and take(4) != b'ROTV':
                raise FormatError('Missing HGOL array marker')
            count = reader.get('I', pos)
            pos += 4
            if count > maximum:
                raise FormatError('Unreasonable HGOL array count')
            return count

        def label(inline):
            nonlocal pos
            if inline:
                length = reader.get('H', pos)
                pos += 2
                value = reader.string(pos, pos + length)
                if len(value) + 1 != length:
                    raise FormatError('HGOL inline name has unverified trailing bytes')
                take(length)
            else:
                offset = reader.get('I', pos)
                pos += 4
                value = reader.string(names + offset, names + names_size)
            return value

        count = array_count(255)
        if not count:
            raise FormatError('Unsupported GHG joint count')
        for index in range(count):
            name = label(version >= 15)
            orient, locator = list(reader.get('16f', pos)), list(reader.get('3f', pos + 64))
            parent, flags = reader.get('2B', pos + 76)
            take(78)
            joints.append(dict(index=index, name=name, parent=None if parent == 255 else parent,
                               flags=flags, orient_row_major=orient, locator_offset=locator))
        for field in ('local_bind_row_major', 'inverse_world_bind_row_major'):
            if array_count(255) != count:
                raise FormatError('GHG bind matrix count differs from joints')
            for joint in joints:
                joint[field] = list(reader.get('16f', pos))
                take(64)
        bind_end = pos
        pre_poi_bytes = list(take(array_count()))
        pois = []
        for _ in range(array_count()):
            name = label(version >= 12)
            pois.append(dict(name=name, matrix=list(reader.get('16f', pos)), joint=reader.get('B', pos + 64)))
            take(65)
        post_poi_bytes = list(take(array_count()))
        length = reader.get('I', pos)
        take(4)
        opaque_tail = take(length)
        metadata = []
        for _ in range(array_count()):
            kind, joint, special, layer = reader.get('BBHB', pos)
            metadata.append(dict(kind=kind, joint=joint, special=special, layer=layer))
            take(5)
        layers = []
        for _ in range(array_count()):
            name = label(version >= 15)
            mi, rigids, skins = reader.get('3H', pos)
            take(6)
            layers.append(dict(name=name, metadata_index=mi, rigids=rigids, skins=skins))
        return dict(source=str(path.resolve()), source_sha256=source_sha256,
                    hgol_offset=at, version=version, byte_order='big', joints=joints,
                    name_table_offset=table_offset, bind_end_offset=bind_end, end_offset=pos,
                    points_of_interest=pois, pre_poi_bytes=pre_poi_bytes, post_poi_bytes=post_poi_bytes,
                    opaque_tail_hex=opaque_tail.hex(), layer_metadata=metadata, layers=layers)

    attempts = 0
    for marker_index,at in enumerate(markers(b'LOGH')):
        if marker_index >= MAX_CANDIDATE_ATTEMPTS:
            raise FormatError('HGOL skeleton candidate limit exceeded')
        try:
            version = reader.get('I', at + 4)
            if version not in SUPPORTED_VERSIONS:
                errors.append({'offset': at, 'issue': f'Unverified HGOL version {version}'})
                continue
            tables = name_tables if version in (10, 12) else [None]
            if not tables:
                raise FormatError('HGOL name table missing')
            for table in tables:
                attempts += 1
                if attempts > MAX_CANDIDATE_ATTEMPTS:
                    raise FormatError('HGOL skeleton/name-table ownership candidate limit exceeded')
                try:
                    candidates.append(parse(at, version, table))
                except (ValueError, UnicodeError) as error:
                    errors.append({'offset': at, 'name_table_offset': table[0] if table else None, 'issue': str(error)})
        except (ValueError, UnicodeError) as error:
            if attempts > MAX_CANDIDATE_ATTEMPTS:
                raise
            errors.append({'offset': at, 'issue': str(error)})
    if not candidates:
        details = '; '.join(f"0x{item['offset']:x}: {item['issue']}" for item in errors[:32])
        raise FormatError('No supported matching GHG skeleton (HGOL 10/12 or ROTV layouts 15/16/17)' + (': ' + details if details else ''))
    rig = select_skeleton(candidates, expected_nodes, display=display, identity=identity)
    rig['selection']['rejected_candidates'].extend(errors)
    return rig
