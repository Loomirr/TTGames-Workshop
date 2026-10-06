"""Bounded native MESH reader for observed PC NXG 169 and DX11 175.

No OBJ, extraction log or Blender dependency. References are resolved from
typed backward-reference constraints, without assuming a file-global ID base.
Unknown layouts and ambiguous references fail before returning geometry.
"""
from pathlib import Path
import math
import struct
from .cu3 import Reader, FormatError
from .morph import read_targets


SIZES = {2: 8, 3: 12, 4: 16, 5: 4, 6: 8, 7: 4, 8: 4, 9: 4}
FIELDS = {0: 'position', 1: 'normal', 2: 'color', 3: 'tangent',
          4: 'bitangent', 5: 'uv', 6: 'uv2', 7: 'uv3',
          9: 'indices', 10: 'packed_weights'}


def decode_skin_weights(indices, packed_weights, palette):
    """Retain authored UNORM8 totals before preparing normalized view weights.

    Unused 255 indices can carry nonzero bytes. Report those discarded bytes;
    do not hide them by reporting only the normalized weights. Multiple native
    slots may address the same joint; combine them before Blender's REPLACE
    assignment would otherwise discard an earlier influence.
    """
    if len(indices) != 4 or len(packed_weights) != 4 or any(
            not isinstance(value, int) or not 0 <= value <= 255
            for value in (*indices, *packed_weights)):
        raise FormatError('Unsupported native byte skin index/weight encoding')
    retained = {}
    sentinel_slots = []
    skipped_weight = retained_slots = 0
    for slot, (index, weight) in enumerate(zip(indices, packed_weights)):
        if index == 255:
            sentinel_slots.append(slot)
            skipped_weight += weight
            continue
        if not weight:
            continue
        if index >= len(palette):
            raise FormatError('Skin index exceeds native palette')
        joint = palette[index]
        if not isinstance(joint, int) or joint < 0:
            raise FormatError('Invalid native skin palette joint')
        retained[joint] = retained.get(joint, 0) + weight
        retained_slots += 1
    raw_total = sum(packed_weights)
    retained_total = sum(retained.values())
    diagnostics = dict(encoding='unorm8', raw_integer_total=raw_total,
                       retained_integer_total=retained_total,
                       raw_total=raw_total/255, retained_total=retained_total/255,
                       skipped_sentinel_slots=sentinel_slots,
                       skipped_sentinel_integer_weight=skipped_weight,
                       skipped_sentinel_weight=skipped_weight/255,
                       merged_duplicate_influences=retained_slots-len(retained),
                       normalized=bool(retained_total))
    weights = [(joint, weight/retained_total) for joint, weight in retained.items()] if retained_total else []
    return weights, diagnostics


class Cursor:
    def __init__(self, data, at=0):
        self.reader = Reader(data)
        self.data, self.at = data, at

    def take(self, size):
        if size < 0 or self.at + size > len(self.data):
            raise FormatError(f'Native mesh range outside file at {self.at:#x}')
        start = self.at
        self.at += size
        return start

    def get(self, fmt, endian='>'):
        return self.reader.get(fmt, self.take(struct.calcsize(endian + fmt)), endian)

    def expect(self, value, fmt='I'):
        at = self.at
        if self.get(fmt) != value:
            raise FormatError(f'Unsupported native mesh field at {at:#x}; expected {value!r}')

    def count(self, maximum):
        value = self.get('I')
        if value > maximum:
            raise FormatError(f'Unreasonable native mesh count: {value}')
        return value


class MeshReader:
    def __init__(self, data, at):
        self.c = Cursor(data, at + 4)
        self.version = self.c.get('I')
        if self.version not in (161, 169, 170, 175):
            raise FormatError(f'Native MESH version {self.version} is not supported')
        self.dx = self.version == 175
        self.buffers = {}
        self.serial = 0
        self.bases = None
        self.parts = []

    def buffer(self, kind):
        c = self.c
        at = c.at
        token = c.get('I')
        if token & 0xffff0000 == 0xc0000000:
            absolute = token & 0xffff
            candidates = {absolute - key for key, item in self.buffers.items()
                          if item['kind'] == kind and absolute >= key}
            self.bases = candidates if self.bases is None else self.bases & candidates
            if not self.bases:
                raise FormatError(f'Unresolved typed backward buffer reference at {at:#x}')
            c.expect(1)
            return {'absolute': absolute, 'kind': kind}
        if token != 1:
            raise FormatError(f'Unknown native buffer token {token:#x} at {at:#x}')
        flags, count = c.get('2I')
        if count > 20_000_000:
            raise FormatError('Unreasonable native buffer element count')
        item = {'kind': kind, 'record_offset': at, 'count': count, 'flags': flags}
        if kind == 'vertex':
            c.expect(b'DXTV', '4s')
            c.expect(161 if self.version == 161 else 169)
            descriptors = [c.get('3B') for _ in range(c.count(32))]
            if not descriptors or len({a[0] for a in descriptors}) != len(descriptors):
                raise FormatError('Empty or duplicate native vertex descriptors')
            if any(a[1] not in SIZES for a in descriptors):
                raise FormatError('Unsupported native vertex attribute encoding')
            stride = max(a[2] + SIZES[a[1]] for a in descriptors)
            occupied = [b for _, typ, offset in descriptors for b in range(offset, offset + SIZES[typ])]
            if len(set(occupied)) != len(occupied) or set(occupied) != set(range(stride)):
                raise FormatError('Overlapping or padded native vertex descriptor layout')
            c.take(6)  # Retained layout fields; not vertex payload.
            item.update(descriptors=descriptors, stride=stride, start=c.take(count * stride))
        else:
            size = c.get('I')
            if size not in (2, 4):
                raise FormatError('Unsupported native index element width')
            item.update(stride=size, start=c.take(count * size))
        key = self.serial
        self.buffers[key] = item
        self.serial += 1
        return {'relative': key, 'kind': kind}

    def stream(self):
        reference = self.buffer('vertex')
        return {'buffer': reference, 'byte_offset': self.c.get('I')}

    def read(self):
        c = self.c
        if not self.dx:
            c.expect(b'ROTV', '4s')
        count = c.count(100_000)
        for index in range(count):
            start = c.at
            if self.dx:
                c.expect(1)
            streams = [self.stream() for _ in range(c.count(16))]
            c.expect(0)
            indices = self.buffer('index')
            first_index, index_count, first_vertex = c.get('3I')
            c.expect(0, 'H')
            vertex_count = c.count(1_000_000)
            c.take(4)
            palette_size = c.count(256)
            palette_at = c.take(palette_size)
            palette = list(c.data[palette_at:palette_at + palette_size])
            self.serial += bool(palette_size)
            target_table = c.at
            ids = []
            while True:
                flag = c.get('I')
                if flag == 0:
                    break
                if flag != 1 or len(ids) >= 4096:
                    raise FormatError('Unsupported native morph target table')
                ids.append(c.get('I'))
            targets = None
            if ids:
                if self.version == 161:
                    raise FormatError('MESH 161 target streams are not verified')
                terminal = c.at - 4
                targets = read_targets(c.data, terminal, len(ids), vertex_count, self.dx)
                if targets['table_offset'] != target_table:
                    raise FormatError('Native target-table boundary mismatch')
                c.at = targets['end_offset']
                self.serial += 2 * len(ids)
                if not self.dx:
                    self.serial += sum(t['encoding'].startswith('rle') and
                                       int.from_bytes(bytes.fromhex(t['companion_hex'])[:4], 'big') > 0
                                       for t in targets['targets'])
            if not self.dx or not ids:
                c.take(4)
            c.take(36)
            self.serial += 2 if self.dx else 1
            if not self.dx:
                secondary = c.get('I')
                if secondary != 0:
                    raise FormatError('Secondary NXG mesh stream requires a separate verified decoder')
                c.take(28)
            self.parts.append(dict(index=index, record_offset=start, end_offset=c.at,
                                   streams=streams, index_buffer=indices, first_index=first_index,
                                   index_count=index_count, first_vertex=first_vertex,
                                   vertex_count=vertex_count, palette=palette, morphs=targets))
            if self.version == 161 and palette:
                raise FormatError('Only unskinned MESH 161 static accessories are verified')
        if self.bases is not None and len(self.bases) != 1:
            raise FormatError('Ambiguous native buffer reference base')
        base = next(iter(self.bases)) if self.bases else None
        def resolve(reference):
            key = reference.get('relative')
            if key is None:
                key = reference['absolute'] - base
            item = self.buffers[key]
            if item['kind'] != reference['kind']:
                raise FormatError('Native buffer reference type mismatch')
            return item
        for part in self.parts:
            self.decode_part(part, resolve)
            if self.version == 161 and any('indices' in v or 'packed_weights' in v for v in part['vertices']):
                raise FormatError('MESH 161 skin streams are not verified')
        return dict(schema='tt.native-mesh.v1', mesh_version=self.version,
                    end_offset=c.at, reference_base=base, parts=self.parts)

    def decode_part(self, part, resolve):
        r = self.c.reader
        attributes = {}
        for stream in part['streams']:
            buffer = resolve(stream['buffer'])
            start = buffer['start'] + stream['byte_offset'] + part['first_vertex'] * buffer['stride']
            end = start + part['vertex_count'] * buffer['stride']
            if start < buffer['start'] or end > buffer['start'] + buffer['count'] * buffer['stride']:
                raise FormatError('Draw vertex range exceeds its native stream')
            stream.update(stride=buffer['stride'], start=start)
            for variable, typ, offset in buffer['descriptors']:
                if variable in attributes:
                    raise FormatError('Duplicate vertex attribute across native streams')
                attributes[variable] = (start + offset, typ, buffer['stride'])
        if 0 not in attributes or attributes[0][1] not in (3, 4, 6):
            raise FormatError('Native mesh requires a verified 3D position stream')
        vertices = []
        for index in range(part['vertex_count']):
            vertex = {}
            for variable, (start, typ, stride) in attributes.items():
                fmt = f'{typ}f' if typ in (2, 3, 4) else '2e' if typ == 5 else '4e' if typ == 6 else '4B'
                values = list(r.get(fmt, start + index * stride, '<' if self.dx and typ <= 6 else '>'))
                if not all(math.isfinite(v) for v in values):
                    raise FormatError('Non-finite native vertex attribute')
                if self.dx and variable == 2 and typ == 9:
                    values = [values[2], values[1], values[0], values[3]]
                vertex[FIELDS.get(variable, f'attribute_{variable}')] = values
            if 'indices' in vertex or 'packed_weights' in vertex:
                if not {'indices', 'packed_weights'} <= vertex.keys():
                    raise FormatError('Incomplete native skin weights')
                if attributes[9][1] != 7 or attributes[10][1] != 8:
                    raise FormatError('Unsupported native skin attribute encoding')
                vertex['weights'], vertex['weight_diagnostics'] = decode_skin_weights(
                    vertex['indices'], vertex['packed_weights'], part['palette'])
            vertices.append(vertex)
        buffer = resolve(part['index_buffer'])
        if part['first_index'] + part['index_count'] > buffer['count'] or part['index_count'] % 3:
            raise FormatError('Native triangle range exceeds its index buffer')
        values = r.get(f'{part["index_count"]}{"H" if buffer["stride"] == 2 else "I"}',
                       buffer['start'] + part['first_index'] * buffer['stride'], '<' if self.dx else '>')
        if any(v >= part['vertex_count'] for v in values):
            raise FormatError('Native triangle index exceeds draw vertex count')
        part.update(vertices=vertices, attribute_types={FIELDS.get(v, f'attribute_{v}'):t for v,(_,t,_) in attributes.items()},
                    attribute_layout={FIELDS.get(v, f'attribute_{v}'):dict(offset=s, type=t, stride=stride,
                        endian='<' if self.dx and t<=6 else '>') for v,(s,t,stride) in attributes.items()},
                    triangles=[list(values[i:i+3]) for i in range(0, len(values), 3)])


def read_mesh_bytes(data):
    """Decode an uncompressed native model in memory, including patch validation."""
    candidates = []
    at = data.find(b'HSEM')
    while at >= 0:
        if at + 8 <= len(data) and int.from_bytes(data[at+4:at+8], 'big') in (161, 169, 170, 175):
            candidates.append(at)
        at = data.find(b'HSEM', at + 4)
    if len(candidates) != 1:
        raise FormatError('Expected one supported native MESH section in an uncompressed file')
    result = MeshReader(data, candidates[0]).read()
    return result


def read_mesh(path):
    import hashlib
    raw=Path(path).read_bytes()
    result = read_mesh_bytes(raw)
    result['source'] = str(Path(path).resolve())
    result['source_sha256'] = hashlib.sha256(raw).hexdigest()
    return result
