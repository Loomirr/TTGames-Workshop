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
import math
import numbers

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
        self.morph = None           # raw morph block as read (facial shapes)
        self.morph_vertices = None  # vertex count the morph block was made for
        self.shapes = None          # decoded shapes: [(id, [(dx, dy, dz) per vertex] or None), ...]
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
        try:
            self._read(data)
            self._original_bones = tuple((b["name"], b["parent"], tuple(b["local"]))
                                         for b in self.bones)
        except HGPError:
            raise
        except (struct.error, IndexError, ValueError, KeyError, UnicodeError) as e:
            raise HGPError(f'Damaged or unsupported model: {e}') from e

    def _read(self, data):
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
            p.shapes = decode_morph(p.morph, count)
        elif u(g + 0x38):
            raise HGPError(f'Unknown morph marker {u(g + 0x38):#x} at {g:#x}')
        p.original = (base, start, n)
        return p

    def template_for(self, kind):
        """A 232-byte record for a new part of `kind`: an original of that kind, or (in the eight
        models that have none) another record turned into that kind. Rigid and skinned records differ
        only in the fields the writer sets, plus three that take their plain values here."""
        same = [p for p in self.parts if p.kind == kind and struct.unpack_from('<I', p.template, 0x44)[0] == 1]
        same = same or [p for p in self.parts if p.kind == kind] or self.parts
        rec = bytearray(same[0].template)
        if same[0].kind != kind:
            struct.pack_into('<I', rec, 0x2C, 0x8A80006C)
            struct.pack_into('<I', rec, 0x44, 1)
            rec[0x4C:0x68] = b'\xff' * 28
            struct.pack_into('<I', rec, 0x6C, 0)
            struct.pack_into('<I', rec, 0x68, kind)
        return bytes(rec)

    def buffer_for(self, kind):
        """The vertex buffer new parts of `kind` go into: the last one holding that kind, or a new one."""
        have = [b for b in self.buffer_order if self.buffer_kind.get(b) == kind]
        return have[-1] if have else max(self.buffer_order, default=-1) + 1

    def _validated_bones(self, bones):
        """Keep source joints intact; validate appended joints before allocating output.

        Work on copies and recompute derived world matrices. Callers may reuse a
        bone dictionary after changing its local matrix, so cached ``world`` data
        cannot establish the inverse bind written to the file.
        """
        old_count = len(self._original_bones)
        if len(bones) < old_count or len(bones) > 255:
            raise HGPError('Bones can be appended up to 255; original bones cannot be removed')
        checked = []
        names = {name for name, _, _ in self._original_bones}
        for i, bone in enumerate(bones):
            if not isinstance(bone, dict):
                raise HGPError(f'Bone {i} must be a bone record')
            name, parent, local = bone.get('name'), bone.get('parent'), bone.get('local')
            if i < old_count:
                try:
                    state = (name, parent, tuple(local))
                except TypeError as exc:
                    raise HGPError(f'Original bone {i} must retain its native bind matrix') from exc
                if state != self._original_bones[i]:
                    raise HGPError(f'Original bone {i} name, parent and bind matrix must remain unchanged')
                local = list(local)
            else:
                if not isinstance(name, str) or not name or '\0' in name:
                    raise HGPError(f'New bone {i} needs a nonempty name without NUL characters')
                try:
                    name.encode('ascii')
                except UnicodeEncodeError as exc:
                    raise HGPError(f'New bone {i} name must be ASCII; names are not remapped') from exc
                if name in names:
                    raise HGPError(f'New bone {i} name {name!r} collides with another bone')
                if isinstance(parent, bool) or not isinstance(parent, numbers.Integral) or not -1 <= parent < i:
                    raise HGPError(f'New bone {name} needs an integer parent index before itself, or -1')
                if old_count == 0:
                    raise HGPError('Adding bones needs an original joint record as a template')
                local = _finite_bone_matrix(local, f'New bone {name} local matrix')
                names.add(name)
            # Never use caller-provided cached worlds, including for original joints.
            world = list(local) if parent < 0 else _mul(local, checked[parent]['world'])
            if i >= old_count:
                _finite_bone_matrix(world, f'New bone {name} world matrix')
                _finite_bone_matrix(_inverse(world), f'New bone {name} inverse matrix')
            checked.append(dict(bone, name=name, parent=parent, local=local, world=world))
        return checked

    # -- writing -----------------------------------------------------------------------------------
    def write(self, parts=None, textures=None, bones=None, materials=None):
        """Bytes of a model file holding `parts`, `textures`, `bones` and `materials` (each defaulting
        to what was read).

        - A part read from this file is patched in place; a part with offset None is added, modelled on
          its `template` record. Parts of the original that are not passed are unlinked.
        - `bones`: the original bones, unchanged and in order, then any new ones (dicts with `name`,
          `parent` and `local`, a 16-float row-major matrix relative to the parent).
        - `materials`: the original materials (their `colour`, `alpha` and `texture` may be changed),
          then any new ones (dicts with `template`: the index of an original material to copy).
        - `textures`: the texture list; new entries are dicts with `width`, `height`, `levels`,
          `format` and `dds`.
        Objects (a rigid bone's list or a layer's skinned list) that do not exist yet are created, and
        the bounds of every object whose parts changed are recomputed.
        """
        parts = self.parts if parts is None else parts
        textures = self.textures if textures is None else textures
        bones = self._validated_bones(self.bones if bones is None else bones)
        materials = self.materials if materials is None else materials
        nb_old, nb = len(self._original_bones), len(bones)
        if len(materials) < len(self.materials):
            raise HGPError('Materials can be added, not removed')
        for m in materials:
            if m['texture'] is not None and not 0 <= m['texture'] < len(textures):
                raise HGPError(f"A material names texture {m['texture']}, of {len(textures)}")
        for p in parts:
            _validate(p, nb, len(materials), len(textures))
        out = bytearray(self.data[:self.texture_block])
        put = lambda o, fmt, *v: struct.pack_into(fmt, out, o, *v)
        H = self.header

        def alloc(blob):
            """New data goes in a block just before the texture block; only the blocks after it move."""
            out.extend(bytes(_align(len(out), 16) - len(out)))
            at = len(out)
            out.extend(blob)
            return at

        # 1. new geometry records (a morph block, if any, follows its record as in the originals)
        added = [p for p in parts if p.offset is None]
        new_offset = {}
        for p in added:
            if p.template is None or len(p.template) != GEOMETRY_SIZE:
                raise HGPError('A new part needs a 232-byte template record')
            new_offset[id(p)] = alloc(bytes(p.template) + encode_morph(p.shapes, len(p.positions)))
        # an original record whose morph block changes size cannot stay where it is: it moves here too
        for p in parts:
            if p.offset is None:
                continue
            block = encode_morph(p.shapes, len(p.positions))
            old = len(p.morph) if p.morph is not None else 0
            if len(block) != old:
                rec = bytearray(self.data[p.offset:p.offset + GEOMETRY_SIZE])
                new_offset[id(p)] = alloc(bytes(rec) + block)
            elif block and block != p.morph:
                out[p.offset + GEOMETRY_SIZE:p.offset + GEOMETRY_SIZE + len(block)] = block
        offset_of = lambda p: new_offset.get(id(p), p.offset)

        # 2. skeleton: new bones are appended; the tables, and every per-bone array, move to new copies
        layer_arrays = {}
        for layer in self.layers:
            rec = H[19] + 20 * layer['index']
            layer_arrays[layer['index']] = [self.u32(rec + 4), self.u32(rec + 12)]
        if nb > nb_old:
            names, joints, local, inverse = bytearray(), bytearray(), bytearray(), bytearray()
            for i, b in enumerate(bones):
                if i < nb_old:
                    joints += self.data[H[7] + 0x60 * i:H[7] + 0x60 * (i + 1)]
                    local += self.data[H[8] + 64 * i:H[8] + 64 * (i + 1)]
                    inverse += self.data[H[9] + 64 * i:H[9] + 64 * (i + 1)]
                    continue
                world = _bone_world(bones, i)
                parent_rec = H[7] + 0x60 * (b['parent'] if 0 <= b['parent'] < nb_old else 0)
                rec = bytearray(self.data[parent_rec:parent_rec + 0x60])
                orient = list(b['local'][:12]) + [0.0, 0.0, 0.0, 1.0]      # rotation, no translation
                struct.pack_into('<19f', rec, 0, *orient, 0.0, 0.0, 0.0)
                rec[0x50] = 255 if b['parent'] < 0 else b['parent']
                rec[0x51] = 8 if b['parent'] < 0 else 33
                joints += rec
                local += struct.pack('<16f', *b['local'])
                inverse += struct.pack('<16f', *_inverse(world))
                names += b['name'].encode('ascii') + bytes(1)
            name_at = alloc(bytes(names))
            o = name_at
            for i in range(nb_old, nb):
                struct.pack_into('<I', joints, 0x60 * i + 0x4C, o)
                o += len(bones[i]['name'].encode('ascii')) + 1
            h7, h8, h9 = alloc(bytes(joints)), alloc(bytes(local)), alloc(bytes(inverse))
            put(4 * 6, '<4I', nb, h7, h8, h9)
            for index, arrays in layer_arrays.items():
                for k, at in enumerate(arrays):
                    if at:
                        old = self.data[at:at + 4 * nb_old]
                        arrays[k] = alloc(old + bytes(4 * (nb - nb_old)))
                        put(H[19] + 20 * index + (4 if k == 0 else 12), '<I', arrays[k])

        # 3. objects: each lists its parts in the order given; missing ones are created
        by_object = {}
        for p in parts:
            by_object.setdefault((p.layer, p.slot, p.bone), []).append(p)
        objects = {(o['layer'], o['slot'], o['bone']): o['offset'] for o in self.objects}
        original_lists = {}
        for p in self.parts:
            original_lists.setdefault((p.layer, p.slot, p.bone), []).append(p)
        for o in self.objects:
            put(o['offset'] + 12, '<I', 0)
        for key, plist in by_object.items():
            layer, slot, bone = key
            if not 0 <= layer < len(self.layers):
                raise HGPError(f'Layer {layer} does not exist')
            if key not in objects:
                at = alloc(bytes(OBJECT_SIZE))
                objects[key] = at
                rec = H[19] + 20 * layer
                if slot == 'rigid':
                    if not layer_arrays[layer][0]:
                        layer_arrays[layer][0] = alloc(bytes(4 * nb))
                        put(rec + 4, '<I', layer_arrays[layer][0])
                    put(layer_arrays[layer][0] + 4 * bone, '<I', at)
                else:
                    put(rec + (8 if slot == 'skinned' else 16), '<I', at)
            put(objects[key] + 12, '<I', offset_of(plist[0]))
            for a, b in zip(plist, plist[1:]):
                put(offset_of(a), '<I', offset_of(b))
            put(offset_of(plist[-1]), '<I', 0)
            same = original_lists.get(key, [])
            if not (len(plist) == len(same) and all(a is b for a, b in zip(plist, same))):
                put(objects[key] + 0x14, '<13f', *_bounds([v for p in plist for v in p.positions]))

        # 4. materials: originals patched in place; new ones copied from a template
        mat_at = []
        for i, m in enumerate(materials):
            if i < len(self.materials):
                at = self.materials[i]['offset']
            else:
                t = self.materials[m['template']]['offset']
                rec = bytearray(self.data[t:t + 0xB4])
                struct.pack_into('<I', rec, 0x30, 0xFFFFFFFF)            # no linked pass
                at = alloc(bytes(rec) + bytes(12))
            mat_at.append(at)
            put(at + 0x54, '<3f', *m['colour'])
            put(at + 0x74, '<f', m['alpha'])
            put(at + 0x78, '<H', 0 if m['texture'] is None else m['texture'] + 1)
        if len(materials) > len(self.materials):
            table = alloc(struct.pack(f'<{len(mat_at)}I', *mat_at))
            put(4 * 4, '<2I', len(materials), table)

        # 5. vertex buffers: every buffer is the concatenation of its parts' vertices, in file order
        order = sorted(parts, key=lambda p: offset_of(p))
        # (a buffer no original part draws from is copied as it is: some originals carry one)
        buffers = {bid: bytearray() if bid in self.buffer_kind else bytearray(self.buffers[bid])
                   for bid in self.buffer_order}
        buffer_order = list(self.buffer_order)
        kinds = dict(self.buffer_kind)
        base_of = {}
        for p in order:
            if p.buffer not in buffers:
                if p.buffer != max(buffer_order, default=-1) + 1:
                    raise HGPError(f'A new vertex buffer must be numbered {max(buffer_order, default=-1) + 1}')
                buffers[p.buffer] = bytearray()
                buffer_order.append(p.buffer)
            if kinds.setdefault(p.buffer, p.kind) != p.kind:
                raise HGPError(f'Vertex buffer {p.buffer} holds kind {kinds[p.buffer]:#x}, not {p.kind:#x}')
            buf = buffers[p.buffer]
            base_of[id(p)] = len(buf) // STRIDE[p.kind]
            buf += _pack_vertices(p)
        # 6. index buffer: original parts keep their order, new ones follow
        index_order = sorted((p for p in parts if p.offset is not None), key=lambda p: p.original[1]) + added
        indices = []
        start_of = {}
        for p in index_order:
            start_of[id(p)] = len(indices)
            indices += p.strip

        # 7. patch every record
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
            put(g + 0x38, '<I', MORPH_FLAG if p.shapes else 0)

        # 8. texture block
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

        # 9. vertex block
        nbuf = len(buffer_order)
        hdr = _align(0x30 + 12 * nbuf, 16)
        offs, pos = [], 0
        for bid in buffer_order:
            offs.append(pos)
            pos = _align(pos + len(buffers[bid]), 16)
        index_off = pos
        raw = 2 * len(indices)
        old = self.vertex_header
        slack = (old[7] + self.index_bytes) - old[2]       # this word's meaning is unknown: keep its distance
        block = bytearray(hdr + 16)
        struct.pack_into('<9I', block, 0, nbuf, 1, hdr + 16 + index_off + raw - slack, 0x30, hdr + 16,
                         index_off, hdr, index_off + hdr + 16, _align(raw, 16))
        for i, bid in enumerate(buffer_order):
            struct.pack_into('<3I', block, 0x30 + 12 * i, len(buffers[bid]), bid, offs[i])
        struct.pack_into('<I', block, hdr, raw)
        out += block
        for bid, off in zip(buffer_order, offs):
            out += bytes(off - (len(out) - vb - hdr - 16))
            out += buffers[bid]
        out += bytes(index_off - (len(out) - vb - hdr - 16))
        if indices and max(indices) > 0xFFFF:
            raise HGPError('Index past 65535')
        out += struct.pack(f'<{len(indices)}H', *indices)
        out += bytes(_align(raw, 16) - raw)

        # 10. header
        struct.pack_into('<I', out, 0, len(out))
        struct.pack_into('<I', out, 8, n_tex)
        struct.pack_into('<I', out, 12, tb)
        struct.pack_into('<I', out, 0x94, tb)
        return bytes(out)


def _finite_bone_matrix(matrix, label):
    try:
        values = list(matrix)
    except TypeError as exc:
        raise HGPError(f'{label} must contain 16 numbers') from exc
    if len(values) != 16 or any(isinstance(v, bool) or not isinstance(v, numbers.Real) for v in values):
        raise HGPError(f'{label} must contain 16 numbers')
    if not all(math.isfinite(v) for v in values):
        raise HGPError(f'{label} must be finite')
    try:
        values = list(struct.unpack('<16f', struct.pack('<16f', *values)))
    except (OverflowError, struct.error) as exc:
        raise HGPError(f'{label} exceeds float32 range') from exc
    if not all(math.isfinite(v) for v in values):
        raise HGPError(f'{label} exceeds finite float32 range')
    if any(abs(values[j]) > 1e-6 for j in (3, 7, 11)) or abs(values[15] - 1.0) > 1e-6:
        raise HGPError(f'{label} must be an affine row-vector transform')
    _inverse(values)  # Refuse singular matrices, including values lost in float32 rounding.
    return values


def _bone_world(bones, i):
    b = bones[i]
    if 'world' not in b:
        b['world'] = list(b['local']) if b['parent'] < 0 else _mul(b['local'], _bone_world(bones, b['parent']))
    return b['world']


def _inverse(m):
    """Inverse of a 4x4 row-major matrix (Gauss-Jordan)."""
    a = [list(m[r * 4:r * 4 + 4]) + [1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]
    for c in range(4):
        piv = max(range(c, 4), key=lambda r: abs(a[r][c]))
        if abs(a[piv][c]) < 1e-12:
            raise HGPError('A bone matrix cannot be inverted')
        a[c], a[piv] = a[piv], a[c]
        f = a[c][c]
        a[c] = [x / f for x in a[c]]
        for r in range(4):
            if r != c and a[r][c]:
                g = a[r][c]
                a[r] = [x - g * y for x, y in zip(a[r], a[c])]
    return [a[r][4 + c] for r in range(4) for c in range(4)]


def _bounds(points):
    """Object bounds as the originals store them: R, R*R, min xyz, max xyz, centre xyz, R, R*R,
    where R is the largest half-size of the box (3,063 of 3,064 original objects match exactly)."""
    f32 = lambda x: struct.unpack('<f', struct.pack('<f', x))[0]
    lo = [min(v[i] for v in points) for i in range(3)]
    hi = [max(v[i] for v in points) for i in range(3)]
    centre = [f32((a + b) / 2) for a, b in zip(lo, hi)]
    r = f32(max((b - a) / 2 for a, b in zip(lo, hi)))
    return [r, f32(r * r)] + lo + hi + centre + [r, f32(r * r)]


def _mul(a, b):
    """4x4 row-major product a*b (row vectors: v' = v * a * b)."""
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4)]


def _finite_components(value, count, label):
    try:
        components = tuple(value)
    except TypeError as exc:
        raise HGPError(f'{label} must contain {count} numeric components') from exc
    if len(components) != count or any(isinstance(v, bool) or not isinstance(v, numbers.Real)
                                       for v in components):
        raise HGPError(f'{label} must contain {count} numeric components')
    if not all(math.isfinite(v) for v in components):
        raise HGPError(f'{label} must be finite')
    try:
        packed = struct.unpack(f'<{count}f', struct.pack(f'<{count}f', *components))
    except (OverflowError, struct.error) as exc:
        raise HGPError(f'{label} exceeds float32 range') from exc
    if not all(math.isfinite(v) for v in packed):
        raise HGPError(f'{label} exceeds finite float32 range')


def _validate(p, n_bones, n_materials, n_textures):
    n = len(p.positions)
    if p.shapes is not None:
        for sid, deltas in p.shapes:
            if deltas is not None and len(deltas) != n:
                raise HGPError(f'Shape {sid} has {len(deltas)} offsets for a part of {n} vertices')
            if deltas is not None:
                for i, delta in enumerate(deltas):
                    _finite_components(delta, 3, f'Shape {sid} vertex {i} delta')
    if not (len(p.normals) == len(p.colours) == len(p.uvs) == n):
        raise HGPError('Part arrays differ in length')
    for label, count, values in (('position', 3, p.positions), ('normal', 3, p.normals), ('UV', 2, p.uvs)):
        for i, value in enumerate(values):
            _finite_components(value, count, f'Vertex {i} {label}')
    if n > 0xFFFF:
        raise HGPError(f'A part holds {n} vertices; the most is 65,535 (split the mesh)')
    if len(p.strip) > 0xFFFF:
        raise HGPError(f'A part draws {len(p.strip)} indices; the most is 65,535 (split the mesh)')
    if len(p.strip) < 3:
        raise HGPError('A part with no triangles')
    if any(isinstance(i, bool) or not isinstance(i, numbers.Integral) or not 0 <= i < n for i in p.strip):
        raise HGPError('Strip index past the part\'s vertices')
    if not 0 <= p.material < n_materials:
        raise HGPError(f'Material {p.material} does not exist')
    if p.kind == SKINNED:
        if not 1 <= len(p.palette) <= MAX_BONES_PER_PART:
            raise HGPError(f'A skinned part uses {len(p.palette)} bones; the most is {MAX_BONES_PER_PART}')
        if len(p.weights) != n:
            raise HGPError('Skinned part without a weight per vertex')
        if any(isinstance(b, bool) or not isinstance(b, numbers.Integral) or not 0 <= b < n_bones for b in p.palette):
            raise HGPError('Bone list names a missing bone')
        for i, w in enumerate(p.weights):
            if not 1 <= len(w) <= 3 or any(not isinstance(slot, (list, tuple)) or len(slot) != 2 for slot in w):
                raise HGPError(f'Vertex {i} needs one to three bone/weight pairs')
            if any(isinstance(b, bool) or not isinstance(b, numbers.Integral) or b not in p.palette for b, _ in w):
                raise HGPError('Vertex weights must name one to three bones of the part\'s bone list')
            amounts = [amount for _, amount in w]
            _finite_components(amounts, len(amounts), f'Vertex {i} weights')
            if any(amount < 0 for amount in amounts) or abs(sum(amounts) - 1.0) > 1e-5:
                raise HGPError(f'Vertex {i} weights must be nonnegative and sum to one')
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


def decode_morph(block, vertices):
    """A morph block -> [(id, deltas or None)]. Layout: u32 size, u32 count, three pointers relative to
    their own position (offset table, id list, data) and -1; then per shape an offset relative to its
    own table slot (0 = no data), the ids, and the shapes' position offsets, 3 floats per vertex."""
    size, n, p1, p2, p3, end = struct.unpack_from('<6I', block)
    if size != len(block) or p1 != 0x10 or p2 != 0xC + 4 * n or p3 != 8 + 8 * n or end != 0xFFFFFFFF:
        raise HGPError('Unsupported morph block header')
    out, pos = [], 0x18 + 8 * n
    for k in range(n):
        off = struct.unpack_from('<I', block, 0x18 + 4 * k)[0]
        sid = struct.unpack_from('<I', block, 0x18 + 4 * n + 4 * k)[0]
        if off == 0:
            out.append((sid, None))
            continue
        start = 0x18 + 4 * k + off
        if start != pos or start + 12 * vertices > size:
            raise HGPError('Unsupported morph block layout')
        flat = struct.unpack_from(f'<{3 * vertices}f', block, start)
        out.append((sid, [flat[i:i + 3] for i in range(0, len(flat), 3)]))
        pos = start + 12 * vertices
    if pos != size:
        raise HGPError('Morph block has data after its shapes')
    return out


def encode_morph(shapes, vertices):
    """The inverse of decode_morph (b'' for no shapes)."""
    if not shapes:
        return b''
    n = len(shapes)
    head = 0x18 + 8 * n
    table, data = [], bytearray()
    for k, (sid, deltas) in enumerate(shapes):
        if deltas is None:
            table.append(0)
            continue
        table.append(head + len(data) - (0x18 + 4 * k))
        data += struct.pack(f'<{3 * vertices}f', *(c for d in deltas for c in d))
    size = head + len(data)
    return (struct.pack('<6I', size, n, 0x10, 0xC + 4 * n, 8 + 8 * n, 0xFFFFFFFF) +
            struct.pack(f'<{n}I', *table) + struct.pack(f'<{n}I', *(sid for sid, _ in shapes)) + bytes(data))


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
