"""LEGO Star Wars II: The Original Trilogy (2006, PC) model files (.hgp): reader and writer.

Plain Python with no other packages, so the Blender add-on and the command-line checks share it.
The layout is described in docs/LSW2_HGP.md. Every pointer in the file is an absolute file offset.

Reading gives bones, attachment points, materials, embedded DDS textures and, per detail layer,
the geometry: rigid parts (one bone each) and skinned parts (up to eight bones each).

Writing works on top of the original file. Everything before the texture block is kept byte for byte
(skeleton, materials, the structures not yet understood); geometry records are patched in place and
new ones are added in a block just before the textures. The textures, vertex buffers and index buffer
at the end of the file are rebuilt. An unchanged model writes back identical to the original.
"""
import struct

MAGIC = b'NU20'
RIGID, SKINNED = 0x59, 0x5D
STRIDE = {RIGID: 36, SKINNED: 56}
GEOMETRY_SIZE = 0xE8
OBJECT_SIZE = 0x70
MORPH_FLAG = 0xB4
MAX_BONES_PER_PART = 8      # the most any original skinned part uses (the record has room for 15)
TRIANGLE_STRIP = 5          # Direct3D 9 primitive type; the only one the originals use


class HGPError(ValueError):
    pass


def _align(x, n):
    return (x + n - 1) // n * n


class Part:
    """One geometry record: a single material, drawn as one triangle strip."""

    def __init__(self):
        self.offset = None          # file offset of the record (None for a new part)
        self.layer = 0
        self.slot = 'skinned'       # 'rigid' (on one bone), 'skinned' or 'skinned2' (the layer's two chains)
        self.bone = None            # bone index of a rigid part
        self.material = 0
        self.kind = SKINNED
        self.buffer = 0
        self.palette = []           # skinned: the bones this part's vertices may name
        self.positions = []
        self.normals = []
        self.colours = []           # u32 as stored (the originals use 0xff000000 almost throughout)
        self.uvs = []
        self.weights = []           # skinned: per vertex [(bone index, weight), ...]
        self.strip = []             # triangle-strip indices into this part's vertices
        self.morph = None           # raw morph block (facial shapes), kept only while the vertices are unchanged
        self.morph_vertices = None  # vertex count the morph block was made for
        self.raw_skin = []          # skinned: stored (w1, w2, j1, j2, j3); used while weights are unchanged
        self.template = None        # the 232-byte record this part was read from or modelled on

    def triangles(self):
        """Triangles in the file's winding (Direct3D strip rule: every second triangle is flipped)."""
        s, out = self.strip, []
        for i in range(len(s) - 2):
            a, b, c = s[i], s[i + 1], s[i + 2]
            if a == b or b == c or a == c:
                continue
            out.append((a, b, c) if i % 2 == 0 else (b, a, c))
        return out

    def set_triangles(self, triangles):
        self.strip = stripify(triangles)


class Model:
    def __init__(self, data):
        self.data = bytes(data)
        d = self.data
        if len(d) < 0x98 or d[4:8] != MAGIC:
            raise HGPError('Not a LEGO Star Wars II model (no NU20 block at offset 4)')
        self.header = list(struct.unpack_from('<38I', d))
        H = self.header
        if H[0] != len(d):
            raise HGPError(f'File size field {H[0]} does not match the file ({len(d)} bytes)')
        self._check(H[3] + 0x20 <= len(d) and H[3] == H[37], 'texture block')
        self.texture_block = H[3]
        self._read_textures()
        self._read_materials()
        self._read_skeleton()
        self._read_layers()
        self._read_vertex_block()
        self._read_parts()

    # -- helpers ---------------------------------------------------------------------------------
    def _check(self, ok, what):
        if not ok:
            raise HGPError(f'Damaged or unsupported model: {what} out of range')

    def u32(self, o):
        return struct.unpack_from('<I', self.data, o)[0]

    def u16(self, o):
        return struct.unpack_from('<H', self.data, o)[0]

    def floats(self, o, n):
        return struct.unpack_from(f'<{n}f', self.data, o)

    def string(self, o):
        end = self.data.index(b'\0', o)
        return self.data[o:end].decode('ascii', 'replace')

    # -- sections ----------------------------------------------------------------------------------
    def _read_textures(self):
        d, tb = self.data, self.texture_block
        w = struct.unpack_from('<8I', d, tb)
        base, self.vertex_block, count = w[0], w[1], w[2]
        self._check(base == tb + 8 and count == self.header[2] and w[4] == 0x18, 'texture header')
        entries, start = base + w[4], base + w[5]
        self._check(start + w[6] == self.vertex_block <= len(d), 'texture data')
        self.textures = []
        offsets = [self.u32(entries + 20 * i + 16) for i in range(count)] + [w[6]]
        for i in range(count):
            width, height, levels, fmt, off = struct.unpack_from('<5I', d, entries + 20 * i)
            a, b = start + offsets[i], start + offsets[i + 1]
            self._check(a < b and d[a:a + 4] == b'DDS ', f'texture {i}')
            self.textures.append(dict(width=width, height=height, levels=levels, format=fmt, dds=d[a:b]))

    def _read_materials(self):
        H = self.header
        self.materials = []
        for i in range(H[4]):
            p = self.u32(H[5] + 4 * i)
            self._check(p + 0xB4 <= self.texture_block, f'material {i}')
            tex = self.u16(p + 0x78)
            link = self.u32(p + 0x30)
            self.materials.append(dict(
                offset=p,
                texture=None if tex == 0 else tex - 1,      # stored counting from 1; 0 = no texture
                texture_flags=self.u16(p + 0x7A),
                colour=self.floats(p + 0x54, 3),
                alpha=self.floats(p + 0x74, 1)[0],
                attributes=self.u32(p + 0x40),
                linked=None if link == 0xFFFFFFFF else link - 1))
            m = self.materials[-1]
            if m['texture'] is not None and m['texture'] >= len(self.textures):
                raise HGPError(f'Material {i} names texture {m["texture"] + 1} of {len(self.textures)}')

    def _read_skeleton(self):
        H = self.header
        n = H[6]
        self._check(H[7] + 0x60 * n <= self.texture_block and H[9] + 64 * n <= self.texture_block, 'bone tables')
        self.bones = []
        for i in range(n):
            r = H[7] + 0x60 * i
            parent = self.data[r + 0x50]
            parent = -1 if parent == 255 else parent
            if parent >= i:
                raise HGPError(f'Bone {i} has parent {parent}, which does not come before it')
            local = self.floats(H[8] + 64 * i, 16)
            world = list(local) if parent < 0 else _mul(local, self.bones[parent]['world'])
            self.bones.append(dict(name=self.string(self.u32(r + 0x4C)), parent=parent, local=local,
                                   world=world, inverse=self.floats(H[9] + 64 * i, 16)))
        self.points = []
        for i in range(H[16]):
            r = H[17] + 0x50 * i
            self.points.append(dict(name=self.string(self.u32(r + 0x40)), bone=self.u32(r + 0x44),
                                    matrix=self.floats(r, 16)))

    def _read_layers(self):
        H = self.header
        self.layers = []
        names = self._layer_names()
        for i in range(H[18]):
            a, rigid, skinned, _, skinned2 = struct.unpack_from('<5I', self.data, H[19] + 20 * i)
            self.layers.append(dict(index=i, name=names[i] if i < len(names) else f'layer{i}',
                                    rigid_array=rigid, skinned=skinned, skinned2=skinned2))

    def _layer_names(self):
        """Layer names sit in the name table straight after the bone names (no pointer refers to them)."""
        H = self.header
        if not self.bones:
            return []
        last = max(self.u32(H[7] + 0x60 * i + 0x4C) for i in range(len(self.bones)))
        end = H[12] + H[13]
        o = self.data.index(b'\0', last) + 1
        out = []
        while o < end and len(out) < H[18]:
            s = self.string(o)               # an empty layer may have an empty name
            out.append(s)
            o += len(s) + 1
        return out

    def _read_vertex_block(self):
        d, vb = self.data, self.vertex_block
        w = struct.unpack_from('<9I', d, vb)
        self._check(w[1] == 1 and w[3] == 0x30 and w[4] == w[6] + 16 and w[7] == w[5] + w[4], 'vertex header')
        self.vertex_header = w
        data = vb + w[4]
        self.buffers = {}
        self.buffer_order = []
        for i in range(w[0]):
            size, bid, off = struct.unpack_from('<3I', d, vb + 0x30 + 12 * i)
            self._check(data + off + size <= data + w[5], f'vertex buffer {bid}')
            self.buffers[bid] = d[data + off:data + off + size]
            self.buffer_order.append(bid)
        self.index_bytes = self.u32(vb + w[6])
        self._check(data + w[5] + self.index_bytes <= len(d) and data + w[5] + w[8] == len(d), 'index buffer')
        self.indices = struct.unpack_from(f'<{self.index_bytes // 2}H', d, data + w[5])

    def _chain(self, obj):
        g, seen = self.u32(obj + 12), set()
        while g:
            if g in seen or g + GEOMETRY_SIZE > self.texture_block:
                raise HGPError('Damaged geometry chain')
            seen.add(g)
            yield g
            g = self.u32(g)

    def _read_parts(self):
        self.parts, self.objects = [], []
        nb = len(self.bones)
        for layer in self.layers:
            if layer['rigid_array']:
                for bone in range(nb):
                    obj = self.u32(layer['rigid_array'] + 4 * bone)
                    if obj:
                        self.objects.append(dict(offset=obj, layer=layer['index'], slot='rigid', bone=bone))
            for slot in ('skinned', 'skinned2'):
                if layer[slot]:
                    self.objects.append(dict(offset=layer[slot], layer=layer['index'], slot=slot, bone=None))
        for obj in self.objects:
            for g in self._chain(obj['offset']):
                self.parts.append(self._read_part(g, obj))
        self.buffer_kind = {}
        for p in self.parts:
            if self.buffer_kind.setdefault(p.buffer, p.kind) != p.kind:
                raise HGPError(f'Vertex buffer {p.buffer} mixes vertex kinds')

    def _read_part(self, g, obj):
        d, u = self.data, self.u32
        p = Part()
        p.offset, p.layer, p.slot, p.bone = g, obj['layer'], obj['slot'], obj['bone']
        p.template = d[g:g + GEOMETRY_SIZE]
        p.material, p.buffer, p.kind = u(g + 8), u(g + 0x48), u(g + 0x68)
        if p.kind not in STRIDE:
            raise HGPError(f'Unknown vertex kind {p.kind:#x} at {g:#x}')
        if (p.kind == RIGID) != (obj['slot'] == 'rigid'):
            raise HGPError(f'Vertex kind {p.kind:#x} in a {obj["slot"]} list at {g:#x}')
        if p.material >= len(self.materials):
            raise HGPError(f'Part at {g:#x} names material {p.material} of {len(self.materials)}')
        ptype, base, low, count, start, prims = struct.unpack_from('<6I', d, g + 0xD0)
        n = self.u16(g + 0xA0)
        if ptype != TRIANGLE_STRIP or low != 0 or n != prims + 2 or base != u(g + 0x18) or count != u(g + 0x10):
            raise HGPError(f'Unexpected draw record at {g:#x}')
        pc = self.u16(g + 0xAC)
        if pc > 15:
            raise HGPError(f'Bone list of {pc} at {g:#x}')
        p.palette = list(struct.unpack_from(f'<{pc}H', d, g + 0xAE))
        if any(b >= len(self.bones) for b in p.palette):
            raise HGPError(f'Bone list names a missing bone at {g:#x}')
        stride = STRIDE[p.kind]
        buf = self.buffers.get(p.buffer)
        if buf is None or (base + count) * stride > len(buf):
            raise HGPError(f'Part at {g:#x} reaches past vertex buffer {p.buffer}')
        if start + n > len(self.indices):
            raise HGPError(f'Part at {g:#x} reaches past the index buffer')
        p.strip = list(self.indices[start:start + n])
        if p.strip and max(p.strip) >= count:
            raise HGPError(f'Part at {g:#x} indexes past its {count} vertices')
        for i in range(count):
            o = (base + i) * stride
            p.positions.append(struct.unpack_from('<3f', buf, o))
            if p.kind == RIGID:
                p.normals.append(struct.unpack_from('<3f', buf, o + 12))
                p.colours.append(struct.unpack_from('<I', buf, o + 24)[0])
                p.uvs.append(struct.unpack_from('<2f', buf, o + 28))
            else:
                w1, w2, j1, j2, j3 = struct.unpack_from('<5f', buf, o + 12)
                p.normals.append(struct.unpack_from('<3f', buf, o + 32))
                p.colours.append(struct.unpack_from('<I', buf, o + 44)[0])
                p.uvs.append(struct.unpack_from('<2f', buf, o + 48))
                slots = []
                for w, j in ((w1, j1), (w2, j2), (1.0 - w1 - w2, j3)):
                    if w > 1e-6:
                        k = int(round(j))
                        if abs(j - k) > 1e-4 or not 0 <= k < len(p.palette):
                            raise HGPError(f'Vertex {i} of part {g:#x} names bone slot {j}')
                        slots.append((p.palette[k], w))
                p.weights.append(slots)       # in stored slot order; one bone may appear twice
                p.raw_skin.append((w1, w2, j1, j2, j3))
        if u(g + 0x38) == MORPH_FLAG:
            m = g + GEOMETRY_SIZE
            size = u(m)
            if not 0x18 <= size <= self.texture_block - m:
                raise HGPError(f'Morph block at {m:#x} out of range')
            p.morph, p.morph_vertices = d[m:m + size], count
        elif u(g + 0x38):
            raise HGPError(f'Unknown morph marker {u(g + 0x38):#x} at {g:#x}')
        p.original = (base, start, n)
        return p

    # -- writing -----------------------------------------------------------------------------------
    def write(self, parts=None, textures=None):
        """Bytes of a model file holding `parts` (default: the parts as read) and `textures`.

        A part read from this file is patched in place; a part with offset None is added (its
        template record and its object, a rigid bone's or a layer chain's, must already exist).
        Parts of the original that are not passed are unlinked from their chains.
        """
        parts = self.parts if parts is None else parts
        textures = self.textures if textures is None else textures
        for p in parts:
            _validate(p, len(self.bones), len(self.materials), len(textures))
        out = bytearray(self.data[:self.texture_block])
        put = lambda o, fmt, *v: struct.pack_into(fmt, out, o, *v)

        # 1. new records go in a block just before the texture block; only the blocks after it move
        added = [p for p in parts if p.offset is None]
        new_offset = {}
        for p in added:
            if p.template is None or len(p.template) != GEOMETRY_SIZE:
                raise HGPError('A new part needs a 232-byte template record')
            new_offset[id(p)] = len(out)
            out += p.template
            if p.morph is not None:
                raise HGPError('A new part cannot carry a morph block')
        pad = _align(len(out), 16) - len(out)
        out += bytes(pad)
        offset_of = lambda p: p.offset if p.offset is not None else new_offset[id(p)]

        # 2. chains: each object lists its parts in the order given
        by_object = {}
        for p in parts:
            key = (p.layer, p.slot, p.bone)
            by_object.setdefault(key, []).append(p)
        objects = {(o['layer'], o['slot'], o['bone']): o['offset'] for o in self.objects}
        for o in self.objects:
            put(o['offset'] + 12, '<I', 0)
        for key, plist in by_object.items():
            if key not in objects:
                raise HGPError(f'No object for layer {key[0]} {key[1]} bone {key[2]} in the original model')
            put(objects[key] + 12, '<I', offset_of(plist[0]))
            for a, b in zip(plist, plist[1:]):
                put(offset_of(a), '<I', offset_of(b))
            put(offset_of(plist[-1]), '<I', 0)

        # 3. vertex buffers: every buffer is the concatenation of its parts' vertices, in file order
        order = sorted(parts, key=lambda p: offset_of(p))
        # (a buffer no original part draws from is copied as it is: some originals carry one)
        buffers = {bid: bytearray() if bid in self.buffer_kind else bytearray(self.buffers[bid])
                   for bid in self.buffer_order}
        base_of = {}
        for p in order:
            if p.buffer not in buffers:
                raise HGPError(f'Vertex buffer {p.buffer} does not exist in the original model')
            if self.buffer_kind.get(p.buffer, p.kind) != p.kind:
                raise HGPError(f'Vertex buffer {p.buffer} holds kind {self.buffer_kind[p.buffer]:#x}, not {p.kind:#x}')
            buf = buffers[p.buffer]
            base_of[id(p)] = len(buf) // STRIDE[p.kind]
            buf += _pack_vertices(p)
        # 4. index buffer: original parts keep their order, new ones follow
        index_order = sorted((p for p in parts if p.offset is not None), key=lambda p: p.original[1]) + added
        indices = []
        start_of = {}
        for p in index_order:
            start_of[id(p)] = len(indices)
            indices += p.strip

        # 5. patch every record
        for p in parts:
            g = offset_of(p)
            n, count = len(p.strip), len(p.positions)
            put(g + 8, '<I', p.material)
            put(g + 0x10, '<2I', count, count)
            put(g + 0x18, '<I', base_of[id(p)])
            put(g + 0x48, '<I', p.buffer)
            put(g + 0x68, '<I', p.kind)
            put(g + 0xA0, '<2H', n, n)
            palette = list(p.palette) + [0] * (15 - len(p.palette))
            put(g + 0xAC, '<16H', len(p.palette), *palette)
            put(g + 0xD0, '<6I', TRIANGLE_STRIP, base_of[id(p)], 0, count, start_of[id(p)], n - 2)
            keep_morph = p.morph is not None and p.morph_vertices == count
            put(g + 0x38, '<I', MORPH_FLAG if keep_morph else 0)

        # 6. texture block
        tb = len(out)
        base = tb + 8
        n_tex = len(textures)
        entries = base + 0x18
        start = _align(entries + 20 * n_tex, 128)
        blobs, offs, pos = [], [], 0
        for t in textures:
            blob = bytes(t['dds']) + bytes(_align(len(t['dds']), 128) - len(t['dds']))
            offs.append(pos)
            blobs.append(blob)
            pos += len(blob)
        vb = start + pos
        out += struct.pack('<8I', base, vb, n_tex, vb - base - 0x14, 0x18, start - base, pos, 0)
        for t, off in zip(textures, offs):
            out += struct.pack('<5I', t['width'], t['height'], t['levels'], t['format'], off)
        out += bytes(start - len(out))
        for blob in blobs:
            out += blob

        # 7. vertex block
        nbuf = len(self.buffer_order)
        hdr = _align(0x30 + 12 * nbuf, 16)
        offs, pos = [], 0
        for bid in self.buffer_order:
            offs.append(pos)
            pos = _align(pos + len(buffers[bid]), 16)
        index_off = pos
        raw = 2 * len(indices)
        old = self.vertex_header
        slack = (old[7] + self.index_bytes) - old[2]       # this word's meaning is unknown: keep its distance
        block = bytearray(hdr + 16)
        struct.pack_into('<9I', block, 0, nbuf, 1, hdr + 16 + index_off + raw - slack, 0x30, hdr + 16,
                         index_off, hdr, index_off + hdr + 16, _align(raw, 16))
        for i, bid in enumerate(self.buffer_order):
            struct.pack_into('<3I', block, 0x30 + 12 * i, len(buffers[bid]), bid, offs[i])
        struct.pack_into('<I', block, hdr, raw)
        out += block
        for bid, off in zip(self.buffer_order, offs):
            out += bytes(off - (len(out) - vb - hdr - 16))
            out += buffers[bid]
        out += bytes(index_off - (len(out) - vb - hdr - 16))
        if indices and max(indices) > 0xFFFF:
            raise HGPError('Index past 65535')
        out += struct.pack(f'<{len(indices)}H', *indices)
        out += bytes(_align(raw, 16) - raw)

        # 8. header
        struct.pack_into('<I', out, 0, len(out))
        struct.pack_into('<I', out, 8, n_tex)
        struct.pack_into('<I', out, 12, tb)
        struct.pack_into('<I', out, 0x94, tb)
        return bytes(out)


def _mul(a, b):
    """4x4 row-major product a*b (row vectors: v' = v * a * b)."""
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4)]


def _validate(p, n_bones, n_materials, n_textures):
    n = len(p.positions)
    if not (len(p.normals) == len(p.colours) == len(p.uvs) == n):
        raise HGPError('Part arrays differ in length')
    if n > 0xFFFF:
        raise HGPError(f'A part holds {n} vertices; the most is 65,535 (split the mesh)')
    if len(p.strip) > 0xFFFF:
        raise HGPError(f'A part draws {len(p.strip)} indices; the most is 65,535 (split the mesh)')
    if len(p.strip) < 3:
        raise HGPError('A part with no triangles')
    if max(p.strip) >= n:
        raise HGPError('Strip index past the part\'s vertices')
    if not 0 <= p.material < n_materials:
        raise HGPError(f'Material {p.material} does not exist')
    if p.kind == SKINNED:
        if not 1 <= len(p.palette) <= MAX_BONES_PER_PART:
            raise HGPError(f'A skinned part uses {len(p.palette)} bones; the most is {MAX_BONES_PER_PART}')
        if len(p.weights) != n:
            raise HGPError('Skinned part without a weight per vertex')
        if any(b >= n_bones for b in p.palette):
            raise HGPError('Bone list names a missing bone')
        for w in p.weights:
            if not 1 <= len(w) <= 3 or any(b not in p.palette for b, _ in w):
                raise HGPError('Vertex weights must name one to three bones of the part\'s bone list')
    elif p.kind == RIGID:
        if p.bone is None or not 0 <= p.bone < n_bones:
            raise HGPError('Rigid part without a bone')
    else:
        raise HGPError(f'Unknown vertex kind {p.kind:#x}')


def _pack_vertices(p):
    out = bytearray()
    for i in range(len(p.positions)):
        if p.kind == RIGID:
            out += struct.pack('<3f3fI2f', *p.positions[i], *p.normals[i], p.colours[i], *p.uvs[i])
        else:
            if len(p.raw_skin) == len(p.positions) and _same_skin(p.raw_skin[i], p.weights[i], p.palette):
                out += struct.pack('<3f5f3fI2f', *p.positions[i], *p.raw_skin[i],
                                   *p.normals[i], p.colours[i], *p.uvs[i])
                continue
            w = list(p.weights[i])
            slots = [(p.palette.index(b), x) for b, x in w]
            while len(slots) < 3:
                slots.append((-1, 0.0))
            (j1, w1), (j2, w2), (j3, _) = slots
            if len(w) < 3:
                j3 = -1.0
            out += struct.pack('<3f5f3fI2f', *p.positions[i], w1, w2, float(j1), float(j2), float(j3),
                               *p.normals[i], p.colours[i], *p.uvs[i])
    return out


def _same_skin(raw, weights, palette):
    """True while `weights` still says what the stored slots say (so they can be written unchanged)."""
    w1, w2, j1, j2, j3 = raw
    stored = [(palette[int(round(j))], w) for w, j in ((w1, j1), (w2, j2), (1.0 - w1 - w2, j3))
              if w > 1e-6 and 0 <= int(round(j)) < len(palette)]
    return len(stored) == len(weights) and all(a[0] == b[0] and abs(a[1] - b[1]) < 1e-7
                                               for a, b in zip(stored, weights))


def stripify(triangles):
    """One Direct3D triangle strip for a triangle list (file winding), joined with degenerate triangles."""
    tris = [tuple(t) for t in triangles if len(set(t)) == 3]
    if not tris:
        return []
    edge = {}
    for i, (a, b, c) in enumerate(tris):
        for e in ((a, b), (b, c), (c, a)):
            edge.setdefault(e, []).append(i)
    used = [False] * len(tris)

    def take(x, y):
        """An unused triangle with directed edge x->y; returns its third vertex."""
        for i in edge.get((x, y), ()):
            if not used[i]:
                used[i] = True
                a, b, c = tris[i]
                return {(a, b): c, (b, c): a, (c, a): b}[(x, y)]
        return None

    strip = []
    for i, t in enumerate(tris):
        if used[i]:
            continue
        used[i] = True
        run = list(t)
        while True:
            # the next triangle in a strip at position k = len(run) - 2 shares the last two indices;
            # at an even position it reads (run[-2], run[-1], x), at an odd one (run[-1], run[-2], x)
            k = len(run) - 2
            x = take(run[-2], run[-1]) if k % 2 == 0 else take(run[-1], run[-2])
            if x is None:
                break
            run.append(x)
        if strip:
            strip += [strip[-1], run[0]]
            if len(strip) % 2:
                strip.append(run[0])
        strip += run
    return strip


def load(path):
    with open(path, 'rb') as f:
        return Model(f.read())
