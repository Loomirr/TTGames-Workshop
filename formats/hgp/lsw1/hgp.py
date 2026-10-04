"""Original 2005 LSW1 PC HGP reader, derived from the supplied disc files.

No LSW2 or Complete Saga format reader is used. Offsets are relative to the
0x30-byte file header. Native hierarchy, local bind matrices, inverse world
bind matrices, LOD links, primitive palettes and vertex weights are retained.
"""
from pathlib import Path
import struct


class HGP:
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if len(self.data) < 0xb0:
            raise ValueError('This file is too short to be an LSW1 PC character HGP')
        self.body = self.data[0x30:]
        self.header = struct.unpack_from('<12I', self.data)
        if self.header[0] != 0 or self.header[1] not in (0x14, 0x30):
            raise ValueError('Expected an original LSW1 PC HGP; other LEGO game formats are unsupported')
        self.root = self.header[6]
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
        self.layers = [self.string(self.u32(self.lods_at+i*20)) for i in range(self.layer_count)]
        # Serialized joint names retain exporter addresses, while the names
        # themselves begin at body+0x30. Recover their relocation base.
        self.name_base = self.u32(self.joints_at + 0x4c) - 0x30
        self.bones = []
        for i in range(self.count):
            at = self.joints_at + i * 0x60
            name_at = self.u32(at + 0x4c) - self.name_base
            assert 0 <= name_at < self.header[3], (self.path.name, i, name_at)
            name = self.string(name_at)
            parent = self.u32(at + 0x50) & 255
            assert parent == 255 or parent < i, (name, parent, i)
            self.bones.append(dict(index=i, name=name, parent=-1 if parent == 255 else parent,
                local=self.floats(self.local_at + i * 64, 16),
                inverse=self.floats(self.inverse_at + i * 64, 16)))
        self.buffers = []
        vertex_at = self.header[5]
        for i in range(self.u32(vertex_at)):
            at = vertex_at + 16 + i * 12
            size = self.u32(at)
            offset = vertex_at + self.u32(at + 8)
            assert offset + size <= len(self.body)
            self.buffers.append(self.body[offset:offset+size])

    def u32(self, at): return struct.unpack_from('<I', self.body, at)[0]
    def u16(self, at): return struct.unpack_from('<H', self.body, at)[0]
    def floats(self, at, count): return struct.unpack_from(f'<{count}f', self.body, at)
    def string(self, at): return self.body[at:self.body.index(0, at)].decode('ascii')

    def meshes(self, lod='AUTO'):
        """TT1_HighRes is LOD 1; entry 0 is the exporter's defaultLayer."""
        if lod == 'AUTO':
            lod = next((i for i,name in enumerate(self.layers) if any(token in name.lower() for token in ('highres','hires'))), None)
            if lod is None:
                # TT1_Hi and TT1_MediumRes are also primary body layers in
                # original LSW1. defaultLayer can contain only eyes or a head.
                lod = next((i for i,name in enumerate(self.layers) if name.lower().startswith('tt1_')), None)
            if lod is None:
                lod = next((i for i in range(self.layer_count) if any(self.u32(self.lods_at+i*20+field) for field in (4,8,16))), 0)
        lod = int(lod)
        if not 0 <= lod < self.layer_count:
            raise ValueError(f'Layer {lod} is unavailable; this character has {self.layer_count} layers')
        result = []
        # defaultLayer carries shared rigid helmets/heads/accessories and
        # skinned facial overlays. It is combined with the desired detail
        # layer. Battle Droid's complete high-detail body is in layer 0.
        for layer in ([0] if lod == 0 else [0,lod]):
            at = self.lods_at + layer * 20
            rigid_array = self.u32(at+4)
            if rigid_array:
                for bone in range(self.count):
                    obj = self.u32(rigid_array+bone*4)
                    if obj:
                        result.extend(self.object_meshes(obj, bone))
            for field in (8,16):
                obj=self.u32(at+field)
                if obj:result.extend(self.object_meshes(obj,None))
        assert result, self.path.name
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
                vertices, normals, uvs, weights = [], [], [], []
                for i in used:
                    offset = i*stride
                    vertices.append(struct.unpack_from('<3f',raw,offset))
                    normals.append(struct.unpack_from('<3f',raw,offset+(12 if vtype==0x59 else 32)))
                    uvs.append(struct.unpack_from('<2f',raw,offset+(28 if vtype==0x59 else 48)))
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
                    vertices=vertices,normals=normals,uvs=uvs,weights=weights,faces=faces)
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
