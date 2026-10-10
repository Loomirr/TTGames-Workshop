"""Experimental, read-only LEGO Marvel PC AN4 decoder.

Supports the observed ANI-D Euler clips with embedded constants and type-6/7
packed curves. Unknown variants are rejected, never silently approximated.
Output retains original scalar channels; transform composition is unverified.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct


class Blob:
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()

    def get(self, fmt, offset):
        size = struct.calcsize('>' + fmt)
        if offset < 0 or offset + size > len(self.data):
            raise ValueError(f'Out of bounds at {offset:#x}')
        values = struct.unpack_from('>' + fmt, self.data, offset)
        return values[0] if len(values) == 1 else values

    def string(self, offset):
        return self.data[offset:self.data.index(b'\0', offset)].decode('ascii')


def skeleton(path):
    b = Blob(path)
    names = b.data.index(b'LBTN')
    version, size = b.get('2I', names + 4)
    names_start = names + 12
    candidates = []
    start = 0
    while True:
        pos = b.data.find(b'LOGH', start)
        if pos < 0:
            break
        ver, count = b.get('2I', pos + 4)
        if ver == 10 and count == 63:
            candidates.append(pos)
        start = pos + 4
    if not candidates:
        raise ValueError('Expected 63-joint HGOL version 10')
    pos = candidates[0]
    joints = []
    for i in range(63):
        at = pos + 12 + i * 82
        name_index = b.get('I', at)
        if name_index >= size:
            raise ValueError('Invalid joint name offset')
        parent, flags = b.get('2B', at + 80)
        if parent != 255 and parent >= i:
            raise ValueError('Parent must precede child')
        joints.append(dict(index=i, name=b.string(names_start + name_index),
                           parent=None if parent == 255 else parent, flags=flags,
                           orient_row_major=list(b.get('16f', at + 4)),
                           locator_offset=list(b.get('3f', at + 68))))
    at = pos + 12 + 63 * 82
    for field in ('local_bind_row_major', 'inverse_world_bind_row_major'):
        count = b.get('I', at)
        if count != 63:
            raise ValueError('Matrix count disagrees with joints')
        at += 4
        for joint in joints:
            joint[field] = list(b.get('16f', at))
            at += 64
    return dict(source=str(b.path.resolve()), sha256=hashlib.sha256(b.data).hexdigest(),
                hgol_offset=pos, joints=joints)


def animation(path, debug=False, clip_index=0, actor_name=None):
    if not actor_name:
        raise ValueError('An explicit actor_name is required; other rigs are not remapped')
    b = Blob(path)
    version, size = b.get('2I', 0)
    if version not in (13,14) or size != len(b.data):
        raise ValueError('Expected AN4 header version 13/14 with exact file size')
    strings, children = b.get('2I', 16)
    root_name = b.string(strings + b.get('I', 28))
    child_count = b.get('H', 8)
    actors = []
    def visit(at):
        count = b.get('H', at + 8)
        child_ptr, data_ptr, name_ptr = b.get('3I', at + 20)
        # Actor name references are one-based; root name uses offset zero.
        name = b.string(strings + max(0, name_ptr - 1))
        if data_ptr:
            block = b.get('I', data_ptr + 68)
            if b.data[block:block + 4] == b'ANID':
                actors.append(dict(name=name, offset=block, data_ptr=data_ptr,
                                   clip_count=b.get('B',at+12),
                                   matrix=list(b.get('16f', data_ptr))))
        for n in range(count):
            visit(child_ptr + 72 * n)
    for n in range(child_count):
        visit(children + 72 * n)
    # Main actor is explicitly selected; attachments have independent skeletons.
    if actor_name=='auto63':
        main=next((a for a in actors if b.get('H',a['offset']+4)==63),None)
    else:
        main = next((a for a in actors if a['name'].lower() == actor_name.lower()), None)
    if main is None:
        raise ValueError(f'No compatible {actor_name} actor; other actors are not remapped')
    if not 0 <= clip_index < main['clip_count']:
        raise ValueError('Animation record index out of range')
    record=main['data_ptr']+80*clip_index
    at = b.get('I',record+68)
    clip_name=b.string(strings+b.get('I',record+64)-1)
    range_start,range_end=b.get('2H',record+72)
    nodes, keys, stride, old_frames, curves, first_old = b.get('6H', at + 4)
    flags = b.get('B', at + 19)
    frames = b.get('H', at + 22)
    minimum, scale = b.get('2f', at + 28)
    offsets = b.get('9I', at + 36)
    ratio, first = b.get('2f', at + 72)
    if nodes != 63 or curves != 6 or flags & 1 or not flags & 0x20 or not flags & 0x40 or not flags & 0x80:
        raise ValueError(f'Unsupported ANI-D layout: nodes={nodes}, curves={curves}, flags={flags:#x}')
    if not frames or not keys or frames > 10000:
        raise ValueError('Invalid frame or key count')
    types = list(b.get(f'{nodes * curves}H', at + offsets[2]))
    node_flags = list(b.get(f'{nodes}B', at + offsets[4]))
    descriptors = []
    key_cursor = 0
    scale_cursor = at + offsets[0]
    histogram = Counter()
    for node in range(nodes):
        for channel in range(curves):
            raw_type = types[node * curves + channel]
            kind = raw_type & 0x7fff
            active = bool(node_flags[node] & (2 if channel < 3 else 1))
            desc = dict(type=kind, step=bool(raw_type & 0x8000), active=active)
            if active:
                histogram[kind if kind < 16 else 'embedded_constant'] += 1
                if kind in (6, 7):
                    desc['key_offset'] = key_cursor
                    desc['scale'], desc['minimum'] = b.get('2f', scale_cursor)
                    key_cursor += 4 if kind == 6 else 8
                    scale_cursor += 8
                elif kind not in (14, 15) and kind < 16:
                    raise ValueError(f'Unsupported active curve type {kind}')
            descriptors.append(desc)
    if key_cursor != stride:
        raise ValueError(f'Curve bytes {key_cursor} disagree with key stride {stride}')
    if scale_cursor > at + offsets[3]:
        raise ValueError('Scale table overlaps keys')
    groups = (keys + 7) // 4
    if at + offsets[3] + groups * stride > at + offsets[4]:
        raise ValueError('Key groups overlap node flags')

    def sample(frame, key_position=None):
        if key_position is not None:
            pos = key_position
        elif keys == 1:
            pos = 0.0
        elif flags & 0x80:
            pos = (frame - first) * ratio
        else:
            pos = (frame - first_old) * (keys - 1) / (old_frames - 1)
        pos = max(0, min(keys - 1, pos))
        whole = int(pos)
        quarter, group, fraction = whole % 4, whole // 4, pos - whole
        result = []
        for desc in descriptors:
            kind = desc['type']
            if not desc['active'] or kind == 14:
                value = 0.0
            elif kind == 15:
                value = 1.0
            elif kind >= 16:
                value = kind * scale + minimum
            else:
                cursor = at + offsets[3] + group * stride + desc['key_offset']
                if kind == 6:
                    word = b.get('I', cursor)
                    next_word = b.get('I', cursor + stride)
                    v0, v1 = word & 255, next_word & 255
                    tangents = [((word >> (8 + q * 6)) & 63) / 63 for q in range(4)]
                    next_t0 = ((next_word >> 8) & 63) / 63
                else:
                    word = b.get('4H', cursor)
                    next_word = b.get('4H', cursor + stride)
                    v0, v1 = word[0], next_word[0]
                    tangents = [(word[q] & 0xfff) / 4095 for q in (1, 2, 3)]
                    tangents.append(((word[1] >> 12) | ((word[2] & 0xf000) >> 8) |
                                     ((word[3] & 0xf000) >> 4)) / 4095)
                    next_t0 = (next_word[1] & 0xfff) / 4095
                t0 = tangents[quarter]
                frac = 0.0 if desc['step'] else fraction
                if quarter < 3:
                    t1 = tangents[quarter + 1]
                    packed = v0 + (v1 - v0) * (t0 + (t1 - t0) * frac)
                else:
                    va = v0 + (v1 - v0) * t0
                    # Runtime avoids accessing the after-next group when fraction is zero.
                    vb = va
                    if frac:
                        v2 = (b.get('I', cursor + 2 * stride) & 255) if kind == 6 else b.get('H', cursor + 2 * stride)
                        vb = v1 + (v2 - v1) * next_t0
                    packed = va + (vb - va) * frac
                value = packed * desc['scale'] + desc['minimum']
            if not math.isfinite(value):
                raise ValueError('Non-finite sample')
            result.append(value)
        return [result[i:i + curves] for i in range(0, len(result), curves)]
    clip = dict(source=str(b.path.resolve()), sha256=hashlib.sha256(b.data).hexdigest(),
                name=clip_name, actor=main['name'], actor_matrix_row_major=list(b.get('16f',record)),
                clip_index=clip_index,clip_count=main['clip_count'],
                source_range_start=range_start,source_range_end=range_end,
                anid_offset=at, node_count=nodes, frame_count=frames, key_count=keys,
                key_stride=stride, compression_ratio=ratio, first_frame=first, format_flags=flags,
                curve_type_counts=dict(histogram), node_flags=node_flags,
                channel_order=['tx', 'ty', 'tz', 'rx_radians', 'ry_radians', 'rz_radians'],
                samples=[sample(frame) for frame in range(frames)])
    return (clip, b, descriptors, offsets, sample) if debug else clip


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='AN4 file or directory tree')
    parser.add_argument('skeleton', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--actor', required=True, help='Exact source actor name')
    parser.add_argument('--clip-index', type=int, default=0)
    args = parser.parse_args()
    try:
        rig = skeleton(args.skeleton)
    except (ValueError, OSError, IndexError, struct.error) as error:
        parser.error('Skeleton refused: ' + str(error))
    if not args.source.exists():
        parser.error('Animation source does not exist')
    if args.destination.exists():
        parser.error('Choose a new decode output folder')
    args.destination.mkdir(parents=True)
    (args.destination / 'skeleton.json').write_text(json.dumps(rig, indent=2))
    sources = [args.source] if args.source.is_file() else sorted(args.source.rglob('*.an4'))
    results = []
    for source in sources:
        try:
            clip = animation(source, actor_name=args.actor, clip_index=args.clip_index)
            relative = Path(source.name) if args.source.is_file() else source.relative_to(args.source)
            target = (args.destination / relative).with_suffix('.json')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(clip, separators=(',', ':'), allow_nan=False))
            results.append(dict(source=str(source.resolve()), output=str(target.resolve()),
                                name=clip['name'], frames=clip['frame_count'],
                                curve_types=clip['curve_type_counts'], status='decoded_scalars'))
            print(f"Decoded {clip['name']}: {clip['frame_count']} frames, 63 nodes")
        except (ValueError, IndexError, struct.error, StopIteration) as error:
            results.append(dict(source=str(source.resolve()), status='unsupported', reason=str(error)))
            print(f'Unsupported {source.name}: {error}')
    (args.destination / 'decode-manifest.json').write_text(json.dumps(results, indent=2))
    print(f"Decoded {sum(r['status'] == 'decoded_scalars' for r in results)}/{len(results)} files")


if __name__ == '__main__':
    main()
