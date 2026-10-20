"""Original 2005 LSW1 PC HGP reader, derived from the supplied disc files.

No LSW2 or Complete Saga format reader is used. Offsets are relative to the
0x30-byte file header. Native hierarchy, local bind matrices, inverse world
bind matrices, LOD links, primitive palettes and vertex weights are retained.
"""
from pathlib import Path
import struct
import math
import re


class HGP:
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if len(self.data) < 0xb0:
            raise ValueError('This file is too short to be an LSW1 PC character HGP')
        self.body = self.data[0x30:]
        self.header = struct.unpack_from('<12I', self.data)
        # Observed original PC name-table offsets. 0x28 occurs in WheelBike,
        # Destroyer and several ships; 0x36 occurs in Wookie and Geonosian.
        # Their root/joint/material/vertex layouts match the older files.
        # This is not a gate for other games which also use the HGP extension.
        if self.header[0] != 0 or self.header[1] not in (0x14, 0x28, 0x30, 0x36):
            raise ValueError('Expected an original LSW1 PC HGP; other LEGO game formats are unsupported')
        self.root = self.header[6]
        self.require_range(self.root, 0x80, 'root')
        self.count = self.body[self.root + 0x7c]
        if not self.count:
            raise ValueError('This HGP has no supported character skeleton')
        self.joints_at = self.u32(self.root + 0x14)
        self.local_at = self.u32(self.root + 0x18)
        self.inverse_at = self.u32(self.root + 0x1c)
        self.lods_at = self.u32(self.root + 0x24)
        self.layer_count = self.body[self.root + 0x7e]
        if not 1 <= self.layer_count <= 32:
            raise ValueError('Unsupported HGP layer table')
        self.require_range(self.joints_at, self.count * 0x60, 'joint table')
        self.require_range(self.local_at, self.count * 64, 'local bind table')
        self.require_range(self.inverse_at, self.count * 64, 'inverse bind table')
        self.require_range(self.lods_at, self.layer_count * 20, 'layer table')
        self.layers = [self.string(self.u32(self.lods_at+i*20)) for i in range(self.layer_count)]
        # Serialized joint names retain exporter addresses. Header word 1 is
        # the first name's body-relative offset, after optional export metadata
        # (0x14, 0x28, 0x30 or 0x36 in the validated files), not a fixed 0x30.
        self.name_base = self.u32(self.joints_at + 0x4c) - self.header[1]
        self.bones = []
        for i in range(self.count):
            at = self.joints_at + i * 0x60
            name_at = self.u32(at + 0x4c) - self.name_base
            if not 0 <= name_at < self.header[3]:
                raise ValueError(f'Invalid HGP joint name offset for joint {i}')
            name = self.string(name_at)
            parent = self.u32(at + 0x50) & 255
            if parent != 255 and parent >= i:
                raise ValueError(f'Invalid HGP parent {parent} for joint {i}')
            local = self.floats(self.local_at + i * 64, 16)
            inverse = self.floats(self.inverse_at + i * 64, 16)
            if not all(math.isfinite(value) for value in (*local, *inverse)):
                raise ValueError(f'Non-finite HGP bind transform for joint {i}')
            self.bones.append(dict(index=i, name=name, parent=-1 if parent == 255 else parent,
                local=local, inverse=inverse))
        self.buffers = []
        vertex_at = self.header[5]
        self.require_range(vertex_at, 16, 'vertex table header')
        self.require_range(vertex_at + 16, self.u32(vertex_at) * 12, 'vertex table')
        for i in range(self.u32(vertex_at)):
            at = vertex_at + 16 + i * 12
            size = self.u32(at)
            offset = vertex_at + self.u32(at + 8)
            self.require_range(offset, size, 'vertex buffer')
            self.buffers.append(self.body[offset:offset+size])

    def require_range(self, at, size, label):
        if at < 0 or size < 0 or at + size > len(self.body):
            raise ValueError(f'Invalid HGP {label} range')

    def u32(self, at): return struct.unpack_from('<I', self.body, at)[0]
    def u16(self, at): return struct.unpack_from('<H', self.body, at)[0]
    def floats(self, at, count): return struct.unpack_from(f'<{count}f', self.body, at)
    def string(self, at): return self.body[at:self.body.index(0, at)].decode('ascii')

    def layer_meshes(self, layer):
        """Read exactly one native layer, without adding defaultLayer.

        Layers are visibility/component sets, not necessarily whole-model LODs.
        An empty exported layer is valid and returns an empty list.
        """
        layer = int(layer)
        if not 0 <= layer < self.layer_count:
            raise ValueError(f'Layer {layer} is unavailable; this character has {self.layer_count} layers')
        result = []
        at = self.lods_at + layer * 20
        rigid_array = self.u32(at+4)
        if rigid_array:
            self.require_range(rigid_array, self.count * 4, 'rigid object table')
            for bone in range(self.count):
                obj = self.u32(rigid_array+bone*4)
                if obj:
                    result.extend(self.object_meshes(obj, bone))
        for field in (8,16):
            obj=self.u32(at+field)
            if obj:result.extend(self.object_meshes(obj,None))
        for part in result:
            part['layer'] = layer
            part['layer_name'] = self.layers[layer]
        return result

    @staticmethod
    def _layer_key(name):
        name = re.sub(r'^tt\d+[_\s]*', '', name.lower())
        return re.sub(r'[^a-z0-9]', '', name)

    def selected_layers(self, lod='AUTO'):
        """Choose an inspection assembly from observed PC layer conventions.

        This does not reconstruct gameplay layer switches. Unknown alternates,
        broken pieces, goggles and cutscene-only hoses remain explicit choices.
        An integer retains the original defaultLayer-plus-selected-layer API.
        """
        if lod != 'AUTO':
            layer = int(lod)
            if not 0 <= layer < self.layer_count:
                raise ValueError(f'Layer {layer} is unavailable; this character has {self.layer_count} layers')
            return [0] if layer == 0 else [0, layer]
        parts = [self.layer_meshes(i) for i in range(self.layer_count)]
        present = [i for i, meshes in enumerate(parts) if meshes]
        if not present:
            raise ValueError('This HGP contains no geometry in its native layers')
        keys = [self._layer_key(name) for name in self.layers]
        high = {'highres', 'hires', 'hi'}
        lower = {'mediumres', 'medres', 'med', 'lowres', 'lores', 'lo',
                 'verylores', 'vlowres', 'vlores', 'vlo'}
        primary = next((i for i in present if keys[i] in high), None)
        if primary is None:
            primary = next((i for i in present if keys[i] in lower), None)
            if primary is not None and 0 in present:
                # Some droids/vehicles keep their complete high detail body in
                # defaultLayer. The lower-detail table covers the same joints
                # (or their parents), whereas Boss Nass/Tarpals defaultLayer
                # covers only the head. Do not overlay two complete bodies.
                default_parts = parts[0] + [p for i in present if keys[i] == 'light' for p in parts[i]]
                default_bones = {b for p in default_parts for weights in p['weights'] for b in weights}
                covered = set(default_bones)
                for bone in default_bones:
                    parent = self.bones[bone]['parent']
                    while parent >= 0:
                        covered.add(parent)
                        parent = self.bones[parent]['parent']
                lower_bones = {b for p in parts[primary] for weights in p['weights'] for b in weights}
                default_faces = sum(len(p['faces']) for p in default_parts)
                lower_faces = sum(len(p['faces']) for p in parts[primary])
                if lower_bones and lower_bones <= covered and default_faces >= lower_faces:
                    primary = 0
        if primary is None:
            # Non-detail component names do not imply a replacement for the
            # default body. Keep defaultLayer and only known complementary sets.
            primary = next((i for i in present if self.layers[i].lower().startswith('tt1_')
                            and not any(token in keys[i] for token in ('broken', 'notused', 'old', 'cutscene'))), None)
            if primary is None:
                primary = 0 if 0 in present else present[0]
        selected = [0] if primary == 0 else [0, primary]
        for i in present:
            key = keys[i]
            # These are literal observed component names, not a rule to merge
            # every TT layer. OldNips, BrokenBits and costume alternatives stay
            # available through layer_meshes / explicit numeric selection.
            complementary = key in {
                'head', 'heads', 'everythingelse', 'hose', 'hoses',
                'commonhose', 'alwaysdrawn', 'energybinder', 'energybinders',
                'light', 'clonetrooper',
            } or bool(re.fullmatch(r'bits\d*', key))
            if key == 'himedcommon':
                complementary = keys[primary] in high | {'mediumres', 'medres', 'med'}
            if complementary and i not in selected:
                selected.append(i)
        # Young Anakin stores hair in an independent detail family. Do not also
        # add goggles or choose between Padme's mutually exclusive hair/helmet.
        hair = next((i for i in present if keys[i] in {'hairhi', 'hairhighres', 'hairhires'}), None)
        if hair is not None and hair not in selected:
            selected.append(hair)
        return [i for i in selected if parts[i]]

    def meshes(self, lod='AUTO'):
        result = []
        seen = set()
        for layer in self.selected_layers(lod):
            for part in self.layer_meshes(layer):
                identity = (part['geometry'], part['primitive'], part['rigid_bone'])
                if identity not in seen:
                    result.append(part)
                    seen.add(identity)
        if not result:
            raise ValueError(f'{self.path.name}: selected layers contain no geometry')
        return result

    def textures(self):
        """Embedded PC DDS files. No external texture directory is required."""
        at=self.header[2];data_offset=self.u32(at);size=self.u32(at+4);count=self.u32(at+8)
        if count > 4096:raise ValueError('Invalid texture count')
        offsets=[self.u32(at+12+i*20+16) for i in range(count)]+[size]
        for i in range(count):
            start=at+12+data_offset+offsets[i];end=at+12+data_offset+offsets[i+1]
            if not 0 <= start < end <= len(self.body):raise ValueError('Invalid embedded texture range')
            raw=self.body[start:end]
            if raw[:4] != b'DDS ':raise ValueError('Only original LSW1 PC DDS textures are supported')
            yield raw

    def materials(self):
        """Observed original LSW1 PC material fields, without external readers."""
        at=self.header[3];count=self.u32(at)
        if count > 4096:raise ValueError('Invalid material count')
        result=[]
        for i in range(count):
            ptr=self.u32(at+4+i*4)
            texture=struct.unpack_from('<h',self.body,ptr+0x78)[0]
            result.append(dict(texture=None if texture==-1 else texture & 0x7fff,
                diffuse=self.floats(ptr+0x54,3),attributes=self.u32(ptr+0x40),
                effect=self.body[ptr+0x9d],linked_material=self.u32(ptr+0x30),
                texture_aux=self.u16(ptr+0x7a)))
        # Original LSW1 stores a one-based link to an auxiliary material.
        # 0x7fef / 0x3f52xxxx is the observed normal-map pass. Other linked
        # records (including 0x7ffe reflection passes) must not become normals.
        for material in result:
            link=material['linked_material']
            material['normal_texture']=None
            if link:
                if link > len(result):raise ValueError('Invalid linked material reference')
                auxiliary=result[link-1]
                if auxiliary['texture_aux']==0x7fef and auxiliary['attributes']>>16==0x3f52:
                    material['normal_texture']=auxiliary['texture']
        return result

    def object_meshes(self, obj, rigid_bone):
        geometry = self.u32(obj+12)
        seen = set()
        while geometry:
            assert geometry not in seen
            seen.add(geometry)
            material = self.u32(geometry+8)
            vtype = self.u32(geometry+12)
            assert vtype in (0x59, 0x5d), (self.path.name, hex(geometry), hex(vtype))
            buffer_id = self.u32(geometry+28)
            raw = self.buffers[buffer_id-1]
            stride = 36 if vtype == 0x59 else 56
            assert len(raw) % stride == 0
            primitive = self.u32(geometry+48)
            prim_seen = set()
            while primitive:
                assert primitive not in prim_seen
                prim_seen.add(primitive)
                mode = self.u32(primitive+4)
                assert mode in (5, 6), (self.path.name, hex(primitive), mode)
                n = self.u16(primitive+8)
                indices_at = self.u32(primitive+12)
                indices = struct.unpack_from(f'<{n}H', self.body, indices_at)
                assert max(indices) < len(raw)//stride
                palette = []
                if vtype == 0x5d:
                    palette_count = self.u16(primitive+20)
                    palette = list(struct.unpack_from(f'<{palette_count}H', self.body, primitive+22))
                    assert palette_count <= 15 and all(x < self.count for x in palette)
                used = sorted(set(indices))
                remap = {old:new for new,old in enumerate(used)}
                vertices, normals, uvs, weights, colors = [], [], [], [], []
                for i in used:
                    offset = i*stride
                    vertices.append(struct.unpack_from('<3f',raw,offset))
                    normals.append(struct.unpack_from('<3f',raw,offset+(12 if vtype==0x59 else 32)))
                    uvs.append(struct.unpack_from('<2f',raw,offset+(28 if vtype==0x59 else 48)))
                    # Keep the packed native color bytes verbatim. The alpha
                    # lane drives observed translucent surfaces; RGB semantics
                    # are not assumed to be a replacement plastic palette.
                    colors.append(struct.unpack_from('<4B',raw,offset+(24 if vtype==0x59 else 44)))
                    if vtype == 0x59:
                        assert rigid_bone is not None
                        weights.append({rigid_bone:1.0})
                    else:
                        w1,w2,j1,j2,j3 = struct.unpack_from('<5f',raw,offset+12)
                        influences={}
                        for w,j in [(w1,j1),(w2,j2),(1-w1-w2,j3)]:
                            if w > 1e-6:
                                assert abs(j-round(j)) < 1e-5 and 0 <= round(j) < len(palette)
                                bone=palette[round(j)]
                                influences[bone]=influences.get(bone,0)+w
                        assert abs(sum(influences.values())-1) < 1e-5
                        weights.append(influences)
                faces=[]
                step = 1 if mode == 6 else 3
                for i in range(0,len(indices)-2,step):
                    a,b,c=indices[i:i+3]
                    if len({a,b,c}) < 3: continue
                    # Coordinate conversion swaps Y/Z and reverses winding.
                    face=(a,c,b) if mode == 5 or i%2==0 else (a,b,c)
                    faces.append(tuple(remap[x] for x in face))
                yield dict(geometry=geometry, primitive=primitive, material=material,
                    buffer=buffer_id, vertex_type=vtype, rigid_bone=rigid_bone,
                    vertices=vertices,normals=normals,uvs=uvs,weights=weights,colors=colors,faces=faces)
                primitive=self.u32(primitive)
            geometry=self.u32(geometry)


if __name__ == '__main__':
    import json,sys
    for path in sys.argv[1:]:
        h=HGP(path);meshes=h.meshes()
        print(json.dumps(dict(file=h.path.name,bones=h.count,meshes=len(meshes),
            faces=sum(len(m['faces']) for m in meshes),
            rigid=sum(m['rigid_bone'] is not None for m in meshes),
            skinned=sum(m['rigid_bone'] is None for m in meshes))))
