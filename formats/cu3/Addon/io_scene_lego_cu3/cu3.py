"""Bounds-checked reader for observed PC CU3 v16--19 and partial v22--27/v30.

CU3's envelope is big-endian; its embedded AN4/ANI-D data is little-endian.
TFA v22--27 and DCSV v30 support includes structural inventory. ANI-E sampling
is disabled, and their camera/object footers require separate verification.
This module does not execute game code, extract archives or modify its inputs.
"""
from pathlib import Path
import hashlib
import math
import struct


class FormatError(ValueError):
    pass


class Reader:
    def __init__(self, data):
        self.data = data

    def get(self, fmt, at, endian='>'):
        size = struct.calcsize(endian + fmt)
        if at < 0 or at + size > len(self.data):
            raise FormatError(f'Read outside file at 0x{at:x} ({size} bytes)')
        vals = struct.unpack_from(endian + fmt, self.data, at)
        return vals[0] if len(vals) == 1 else vals

    def string(self, at, end=None):
        end = len(self.data) if end is None else end
        if not 0 <= at < end <= len(self.data):
            raise FormatError('String address outside its table')
        null = self.data.find(b'\0', at, end)
        if null < 0:
            raise FormatError('Unterminated string')
        return self.data[at:null].decode('ascii')


class Animation:
    """Scalar sampler for the verified embedded-constant Euler layout.

    Other layouts retain their header and raw data; they are explicitly rejected
    for pose application, rather than receiving guessed curves.
    """
    def __init__(self, reader, at, limit):
        self.reader, self.at, self.limit = reader, at, limit
        raw_magic = reader.data[at:at + 4]
        self.endian = '>' if raw_magic in (b'ANID', b'ANIE') else '<'
        self.magic = raw_magic[::-1] if self.endian == '>' else raw_magic
        if self.magic not in (b'DINA', b'EINA'):
            raise FormatError(f'Expected ANI-D/E at 0x{at:x}')
        self.nodes, self.keys, self.stride, self.old_frames, self.curves, self.old_first = reader.get('6H', at + 4, self.endian)
        self.flags = reader.get('B', at + 19)
        self.integer_constant_count = reader.get('B', at + 17)
        self.frames = reader.get('H', at + 22, self.endian)
        self.minimum, self.scale = reader.get('2f', at + 28, self.endian)
        self.offsets = reader.get('9I', at + 36, self.endian)
        self.ratio, self.first = reader.get('2f', at + 72, self.endian)
        if not 0 < self.nodes <= 2048 or not 0 < self.curves <= 64 or not self.keys or not self.frames:
            raise FormatError('Invalid ANI-D counts')
        self.types = reader.get(f'{self.nodes * self.curves}H', at + self.offsets[2], self.endian)
        if isinstance(self.types, int):
            self.types = (self.types,)
        self.node_flags = reader.get(f'{self.nodes}B', at + self.offsets[4])
        if isinstance(self.node_flags, int):
            self.node_flags = (self.node_flags,)
        self.descriptors = None

    def header(self):
        return dict(offset=self.at, nodes=self.nodes, keys=self.keys, curves=self.curves,
                    format=self.magic[::-1].decode('ascii'),
                    frames=self.frames, flags=self.flags, first_frame=self.first,
                    compression_ratio=self.ratio)

    def prepare(self, scene_channels=False, morph_channels=False):
        if self.magic == b'EINA':
            raise FormatError('ANI-E sampling is not yet verified; structural inventory only')
        if self.descriptors is not None:
            return
        if morph_channels and (self.nodes != 1 or self.curves != 53 or self.flags not in (0xa4, 0xac)
                               or tuple(self.node_flags) != (0,) or self.magic != b'DINA'):
            raise FormatError('Facial scalar layout not verified for this animation')
        if (not scene_channels and not morph_channels and (self.curves != 6 or self.flags & 0xe0 != 0xe0)) or self.flags & 1:
            raise FormatError(f'Pose sampling not yet supported: curves={self.curves}, flags=0x{self.flags:02x}')
        if scene_channels and (self.curves not in (1, 2, 3, 6, 7, 8, 9, 10) or not self.flags & 0x80):
            raise FormatError('Unsupported scene scalar layout')
        if not math.isfinite(self.ratio) or self.ratio <= 0 or not math.isfinite(self.first):
            raise FormatError('Invalid compressed animation timing')
        descriptors, key_cursor, scale_cursor = [], 0, self.at + self.offsets[0]
        r = self.reader
        # Observed LB3 actor-control tracks: six absent transform channels,
        # visibility followed by discrete resource-control fields. These are
        # not a scale triplet. Retain the extra integers without interpreting
        # their resource/variant semantics. Unknown layouts still fail.
        discrete_scene = (scene_channels and self.flags == 0xac and self.nodes == 1 and
                          tuple(self.node_flags) == (0,) and
                          tuple(self.types) in ((14,)*6+(10,10), (14,)*6+(8,8), (14,)*6+(8,10,10), (14,)*6+(8,8,10,10)))
        # LMSH1 Stark Tower also supplies translated placement before the
        # same visibility/resource controls. Its three type-7 translations
        # consume 24 bytes per group, followed by 12 bytes of integer indices.
        # Keep this observed layout narrow; channels 6..8 are not bone scale.
        translated_controls = (scene_channels and self.flags == 0xac and self.nodes == 1 and
                               tuple(self.node_flags) == (2,) and
                               tuple(self.types) == (7,7,7,14,14,14,8,10,10))
        discrete_scene = discrete_scene or translated_controls
        if scene_channels and self.curves == 8 and not discrete_scene:
            raise FormatError('Unverified eight-channel scene control layout')
        attachment_controls = (scene_channels and self.flags in (0xa4, 0xac) and
                               self.nodes == 1 and tuple(self.node_flags) == (0,) and
                               tuple(self.types) in ((8,), (8,8)))
        if scene_channels and self.curves == 2 and not attachment_controls:
            raise FormatError('Unverified two-channel attachment control layout')
        # The two type-10 resource controls can exist without visibility.
        # Their -1 sentinels must not hide the actor or become bone scale.
        self.control_visibility_channel = 0 if attachment_controls else 6 if discrete_scene and self.types[6] == 8 else None
        self.discrete_scene_controls = discrete_scene
        for node in range(self.nodes):
            for channel in range(self.curves):
                kind = self.types[node * self.curves + channel] & 0x7fff
                active = (True if morph_channels or attachment_controls or discrete_scene and channel>=6 else bool(self.node_flags[node] & 8) if self.curves in (9,10) and 6<=channel<9 else
                          True if self.curves == 1 or channel >= 6 else bool(self.node_flags[node] & (2 if channel < 3 else 1)))
                desc = dict(kind=kind, active=active, step=bool(self.types[node * self.curves + channel] & 0x8000))
                if active and kind in (6, 7):
                    desc['key_offset'] = key_cursor
                    desc['scale'], desc['minimum'] = r.get('2f', scale_cursor, self.endian)
                    key_cursor += 4 if kind == 6 else 8
                    scale_cursor += 8
                elif active and scene_channels and (kind == 8 or kind == 10 and discrete_scene):
                    desc['key_offset'] = key_cursor
                    key_cursor += 4
                    desc['step'] = True
                elif active and kind >= 16 and not self.flags & 0x20:
                    # Indexed integer constants precede the aligned float pool.
                    # A visibility table with two integers adds four bytes;
                    # a skeletal table with none starts directly with floats.
                    float_start = (self.integer_constant_count * 2 + 3) & ~3
                    constant_at = self.at + self.offsets[1] + float_start + (kind - 16) * 4
                    if constant_at + 4 > self.at + self.offsets[2]:
                        raise FormatError('Float constant index outside its table')
                    desc['constant'] = r.get('f', constant_at, self.endian)
                elif active and kind < 16 and kind not in (14, 15):
                    raise FormatError(f'Unsupported skeletal curve type {kind}')
                descriptors.append(desc)
        if key_cursor != self.stride:
            raise FormatError(f'ANI-D key stride mismatch: {key_cursor} != {self.stride}')
        if scale_cursor > self.at + self.offsets[3]:
            raise FormatError('ANI-D scale table overlaps keys')
        groups = (self.keys + 7) // 4
        if self.at + self.offsets[3] + groups * self.stride > self.at + self.offsets[4]:
            raise FormatError('ANI-D key groups overlap node flags')
        if self.at + self.offsets[4] + self.nodes > self.limit:
            raise FormatError('ANI-D node flags outside data block')
        self.descriptors = descriptors

    def position(self, frame):
        return max(0.0, min(self.keys - 1.0, (frame - self.first) * self.ratio))

    def sample(self, frame, key_position=None):
        self.prepare()
        pos = self.position(frame) if key_position is None else max(0.0, min(self.keys - 1.0, key_position))
        whole = int(pos)
        quarter, group, fraction = whole % 4, whole // 4, pos - whole
        result, r = [], self.reader
        for desc in self.descriptors:
            kind = desc['kind']
            if not desc['active'] or kind == 14:
                value = 0.0
            elif kind == 15:
                value = 1.0
            elif kind >= 16:
                value = desc.get('constant', kind * self.scale + self.minimum)
            elif kind in (8, 10):
                cursor = self.at + self.offsets[3] + group * self.stride + desc['key_offset']
                index = r.get('B', cursor + quarter)
                if index >= self.integer_constant_count:
                    raise FormatError('Indexed integer curve outside its constant table')
                value = r.get('h', self.at + self.offsets[1] + index * 2, self.endian)
            else:
                cursor = self.at + self.offsets[3] + group * self.stride + desc['key_offset']
                if kind == 6:
                    word, following = r.get('I', cursor, self.endian), r.get('I', cursor + self.stride, self.endian)
                    v0, v1 = word & 255, following & 255
                    tangents = [((word >> (8 + q * 6)) & 63) / 63 for q in range(4)]
                    next_t0 = ((following >> 8) & 63) / 63
                else:
                    word, following = r.get('4H', cursor, self.endian), r.get('4H', cursor + self.stride, self.endian)
                    v0, v1 = word[0], following[0]
                    tangents = [(word[q] & 0xfff) / 4095 for q in (1, 2, 3)]
                    tangents.append(((word[1] >> 12) | ((word[2] & 0xf000) >> 8) | ((word[3] & 0xf000) >> 4)) / 4095)
                    next_t0 = (following[1] & 0xfff) / 4095
                frac = 0.0 if desc['step'] else fraction
                t0 = tangents[quarter]
                if quarter < 3:
                    packed = v0 + (v1 - v0) * (t0 + (tangents[quarter + 1] - t0) * frac)
                else:
                    va = v0 + (v1 - v0) * t0
                    vb = va
                    if frac:
                        v2 = (r.get('I', cursor + 2 * self.stride, self.endian) & 255) if kind == 6 else r.get('H', cursor + 2 * self.stride, self.endian)
                        vb = v1 + (v2 - v1) * next_t0
                    packed = va + (vb - va) * frac
                value = packed * desc['scale'] + desc['minimum']
            if not math.isfinite(value):
                raise FormatError('Non-finite animation sample')
            result.append(value)
        return [result[i:i + self.curves] for i in range(0, len(result), self.curves)]


class Cutscene:
    def __init__(self, path, data=None):
        self.path = Path(path)
        data = self.path.read_bytes() if data is None else bytes(data)
        self.reader = r = Reader(data)
        self.sha256 = hashlib.sha256(data).hexdigest()
        total, envelope, raw_version = r.get('3I', 0)
        self.header_shift = 4 if raw_version == 0x8000001e else 0
        self.version = 30 if self.header_shift else raw_version
        self.extended_header_word = r.get('I',12) if self.header_shift else None
        if self.header_shift and self.extended_header_word not in (0,1):
            raise FormatError('Unverified DCSV extended-header flag')
        self.frames, self.fps = r.get('If',12+self.header_shift)
        if envelope != 1 or self.version not in (16, 17, 18, 19, 22, 23, 24, 25, 26, 27, 30):
            raise FormatError(f'Unsupported CU3 envelope/version: {envelope}/{self.version}')
        if not self.frames or self.frames > 100000 or not 0 < self.fps <= 240:
            raise FormatError('Invalid CU3 timeline')
        if total != 0xffffffff and total not in (len(data), len(data) - 4):
            raise FormatError('CU3 declared size does not match file')
        table_bytes, actor_count = r.get('2I', 24+self.header_shift)
        if actor_count > 4096:
            raise FormatError('Unreasonable CU3 actor count')
        at, self.actor_metadata = 32+self.header_shift, []
        stride = 44 if self.version <= 17 else 48
        for i in range(actor_count):
            extra_count = r.get('I', at + (40 if self.version == 16 else 36))
            if extra_count > 4096:
                    raise FormatError(f'Unreasonable actor variant count at actor {i}, 0x{at:x}')
            meta = dict(index=i, table_offset=at,
                state_ref=r.get('I', at), kind=r.get('H', at + 4),
                tree_ref=r.get('I', at + 6), matrix_index=r.get('H', at + 10), actor_id=r.get('H', at + 12),
                rate=r.get('f', at + (18 if self.version == 16 else 14)), scale=r.get('f', at + (22 if self.version == 16 else 18)),
                variant_count=extra_count)
            next_at = at + stride + extra_count
            # v18+ can carry extra reference tables, each an array
            # of (string reference, integer reference) pairs. Their semantic
            # meaning is still under investigation. The final
            # four-byte field follows those arrays even when there are none.
            meta['switch_tables'] = []
            if self.version >= 18:
                tables = r.get('I', at + 40 + extra_count)
                if tables > 4096:
                    raise FormatError('Unreasonable actor switch table count')
                cursor = at + 44 + extra_count
                for table in range(tables):
                    count = r.get('I', cursor)
                    if count > 100000:
                        raise FormatError('Unreasonable actor switch key count')
                    cursor += 4
                    meta['switch_tables'].append([r.get('2I', cursor + k * 8) for k in range(count)])
                    cursor += count * 8
                next_at = cursor + 4
                if 22 <= self.version <= 27:
                    # TFA serializes a length-prefixed actor resource name
                    # here. Empty names use the same four-byte zero field as
                    # older files. Ignoring nonempty names misaligns every
                    # following actor. Its runtime override rules are unknown.
                    name_bytes = r.get('I', cursor)
                    if name_bytes > 4096 or next_at + name_bytes > len(data):
                        raise FormatError('TFA actor resource name exceeds bounds')
                    if name_bytes:
                        if data[next_at + name_bytes - 1] != 0:
                            raise FormatError('Unterminated TFA actor resource name')
                        meta['resource_name'] = r.string(next_at, next_at + name_bytes)
                        if len(meta['resource_name']) + 1 != name_bytes:
                            raise FormatError('TFA actor resource name has trailing bytes')
                    next_at += name_bytes
            self.actor_metadata.append(meta)
            at = next_at
        self.extra_references = []
        if self.version == 30 and self.extended_header_word == 1:
            extra_count = r.get('I', at)
            if extra_count > 100000:
                raise FormatError('Unreasonable DCSV pre-blob reference count')
            self.extra_references = [r.get('I',at+4+i*4) for i in range(extra_count)]
            at += 4+extra_count*4
        blob_size = r.get('I', at)
        self.blob_start, self.blob_end = at + 4, at + 4 + blob_size
        if self.blob_end > len(data):
            raise FormatError('CU3 data block exceeds file')
        standalone_count = r.get('I', self.blob_start, '<') if blob_size else 0
        if standalone_count * 4 + 4 > blob_size or (actor_count and standalone_count * 4 + 4 > table_bytes) or table_bytes > blob_size:
            raise FormatError('Invalid CU3 animation-offset table')
        self.standalone = []
        for i in range(standalone_count):
            off = r.get('I', self.blob_start + 4 + i * 4, '<')
            self.standalone.append(Animation(r, self.blob_start + off, self.blob_end))
        self.root = self.blob_start + table_bytes
        self.actors, self.tree_version = [], None
        if actor_count:
            self._tree()
            by_ref = {a['offset'] - self.blob_start: a for a in self.actors}
            for meta in self.actor_metadata:
                if meta['tree_ref'] not in by_ref:
                    raise FormatError(f'Actor reference does not point to an AN4 node: {meta["tree_ref"]:#x}')
                by_ref[meta['tree_ref']]['metadata'] = meta
        at = self.blob_end
        string_bytes = r.get('I', at)
        self.strings_start, self.strings_end = at + 4, at + 4 + string_bytes
        self.name = r.string(self.strings_start, self.strings_end)
        at = self.strings_end
        matrix_count = r.get('I', at)
        if matrix_count > 65536 or at + 4 + matrix_count * 64 > len(data):
            raise FormatError('Invalid CU3 matrix table')
        self.matrices = [list(r.get('16f', at + 4 + i * 64)) for i in range(matrix_count)]
        for actor in self.actors:
            if 'metadata' in actor:
                mi = actor['metadata']['matrix_index']
                if mi >= matrix_count:
                    raise FormatError('Actor matrix index outside table')
                actor['scene_matrix'] = self.matrices[mi]
        self.footer_start = at + 4 + matrix_count * 64
        # Remaining camera, rigid, locator and event records are preserved.
        self.footer_bytes = data[self.footer_start:]

    def _tree(self):
        r, root = self.reader, self.root
        ver, size = r.get('2I', root, '<')
        tree_versions = {22: (17,), 23: (18,), 24: (18,), 25: (18,),
                         26: (19,), 27: (20,), 30: (20,)}
        if ver not in tree_versions.get(self.version, (13, 14, 15, 16)) or size < 72 or root + size > self.blob_end:
            raise FormatError('Unsupported embedded AN4 tree header')
        self.tree_version = ver
        strings, children = r.get('2I', root + 16, '<')
        if strings >= size:
            raise FormatError('AN4 string table outside tree')
        string_start, tree_end = root + strings, root + size
        visited = set()
        def visit(at, parent):
            if at in visited or at < root + 72 or at + 72 > tree_end:
                raise FormatError('Invalid/cyclic AN4 node hierarchy')
            visited.add(at)
            count = r.get('H', at + 8, '<')
            child, data, name = r.get('3I', at + 20, '<')
            actor = dict(index=len(self.actors), offset=at, parent=parent,
                         name=r.string(string_start + max(0, name - 1), tree_end), records=[])
            visibility = r.get('I', at + 32, '<')
            actor['visibility_animation'] = Animation(r, root + visibility, tree_end) if visibility else None
            self.actors.append(actor)
            records = r.get('B', at + 12)
            if data:
                for i in range(records):
                    rec = root + data + 80 * i
                    if rec < root or rec + 80 > tree_end:
                        raise FormatError('AN4 animation record outside tree')
                    name_offset, ani_offset = r.get('2I', rec + 64, '<')
                    start, end = r.get('2H', rec + 72, '<')
                    if self.version in (22, 23, 24, 25, 26, 27, 30) and ani_offset == 0:
                        actor.setdefault('static_records',[]).append(dict(index=i,offset=rec,name=r.string(string_start+max(0,name_offset-1),tree_end),range_start=start,range_end=end,matrix=list(r.get('16f',rec,'<'))))
                        continue
                    anim = Animation(r, root + ani_offset, tree_end)
                    actor['records'].append(dict(index=i, offset=rec, name=r.string(string_start + max(0, name_offset - 1), tree_end),
                        range_start=start, range_end=end, matrix=list(r.get('16f', rec, '<')), animation=anim))
            if count > 4096:
                raise FormatError('Unreasonable AN4 child count')
            for i in range(count):
                visit(root + child + 72 * i, actor['index'])
        count = r.get('H', root + 8, '<')
        for i in range(count):
            visit(root + children + 72 * i, None)

    def report(self):
        actors = []
        for a in self.actors:
            records = []
            for rec in a['records']:
                anim = rec['animation']
                try:
                    anim.prepare()
                    status = 'supported_euler_pose'
                except FormatError as e:
                    status = str(e)
                records.append(dict(name=rec['name'], range_start=rec['range_start'], range_end=rec['range_end'],
                                    animation=anim.header(), sampling=status))
            actors.append(dict(name=a['name'], parent=a['parent'], metadata=a.get('metadata'), records=records))
        return dict(name=self.name, source=str(self.path.resolve()), sha256=self.sha256,
                    version=self.version, tree_version=self.tree_version, frames=self.frames, fps=self.fps,
                    actors=actors, standalone_animation_count=len(self.standalone),
                    standalone_animations=[a.header() for a in self.standalone],
                    matrix_count=len(self.matrices), unresolved_footer_bytes=len(self.footer_bytes))
