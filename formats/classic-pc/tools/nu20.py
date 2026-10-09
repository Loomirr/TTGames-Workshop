"""Parser for TT Games "NU20" scene/model files (*_pc.gsc, *_pc.ghg) as shipped with LEGO Batman 1 PC.

Layout used by this game ("NU20 first"):
    'NU20', i32 -nu20_size, u32 version, i32 -1
    tagged chunks (tag[4], u32 size incl. the 8-byte header): HEAD NTBL TREF TST0 MS00 SST0 INID FDNS BNDS DISP VBIB SALI DYNO GSNH PNTR
    @nu20_size: u32 payload_size, then DDS textures back to back,
                u16 vb_count, vb_count * { u32 size, bytes }, u16 ib_count, ib_count * { u32 size, bytes }
Pointers inside the NU20 block are i32 offsets relative to the pointer's own position.
Field offsets follow the community documentation in BactaTank Classic (AlubJ); see EXTRACTION.md.

Usage:
    python tools/nu20.py info <file>
    python tools/nu20.py export <file> <out_dir>      # DDS textures, scene.obj/.mtl, scene.json
"""
import json
import os
import struct
import sys


def _cstr(d, off):
    end = d.index(b"\0", off)
    return d[off:end].decode("latin1")


def decode_vertex_format(vf):
    """Returns list of (attribute, kind, offset) and the stride implied by the format flags.

    Measured 2026-10-08 on LEGO Star Wars TCS, LEGO Indiana Jones 1 and LEGO Batman 1 (3,431 files): in every
    one of the 354,059 times a model draws a mesh with a material, the stride below equals the mesh record's
    stride. Normal slots agree with the normals of the mesh's own triangles (mean |dot| 0.96 to 0.99 a game).
    Order of the fields: position, normal slot, tangent slot, bitangent slot, colour 1, colour 2, UV sets,
    blend weights, blend indices, last vector.
      0x8 packed normal, 0x20 packed tangent, 0x80 packed bitangent (4 bytes each: x, y, z as (byte/255)*2-1,
          and a fourth byte); 0x4 / 0x10 / 0x40 would be the same three as floats (never met in the three games)
      0x800000, 0x1000000, 0x2000000 (and bit 31) give the same three slots even without 0x8 / 0x20 / 0x80.
          A slot present only through one of these does NOT hold a unit vector (checked against the triangles'
          own normals): usually three zero bytes and one value. Its meaning is unknown, so it is named
          unknown_800000 / unknown_1000000 / unknown_2000000 and never handed out as a normal or tangent.
          0x2000000 wins over 0x80: in TCS files that set both, the slot is not a unit vector.
      0x100 colour 1, 0x200 / 0x400 colour 2 (4 bytes each); bits 11..13 number of UV sets (two floats each;
          as two half floats when 0x8000000 is set, never met)
      0x8000 blend weights and 0x20000 blend indices: 4 bytes each (three used, one spare), the last 8 bytes of
          a skinned vertex; 0x4000 / 0x10000 would be float versions (never met)
      0x4000000 a last 8-byte field: a packed unit vector (often close to the normal) and four zero bytes.
          Called light_dir after the community documentation; what the game does with it is not known here.
      0x10000000 the vertex has NO position: the positions are whole vertex buffers of their own, one per
          animation frame, named in the mesh record (8 meshes: the swarm animals in stuff/extra of Batman and
          stuff/extras of Indiana Jones, e.g. batswarm, ratrun, fishswim, spider, snake).
    """
    signed = vf - (1 << 32) if vf & 0x80000000 else vf
    normal = 2 if (vf & 8) or (vf & 0x880000) else (vf >> 2) & 1
    tangent = 2 if (vf & 0x20) or (vf & 0x1000000) else (vf >> 4) & 1
    bitangent = 2 if signed < 0 or (vf & 0x2000080) else (vf >> 6) & 1
    colour1 = (vf >> 8) & 1
    colour2 = vf & 0x600
    if (vf >> 27) & 1:
        uv_float, uv_half = 0, (vf >> 11) & 7
    else:
        uv_float, uv_half = (vf >> 11) & 7, 0
    blend_a = 2 if vf & 0x8000 else (vf >> 14) & 1
    blend_b = 2 if vf & 0x20000 else (vf >> 16) & 1
    extra = (vf >> 26) & 1
    names = ("normal" if vf & 0xC else "unknown_800000",
             "tangent" if vf & 0x30 else "unknown_1000000",
             "bitangent" if vf & 0xC0 and not vf & 0x2000000 else "unknown_2000000")

    fmt, off = [("position", "float3", 0)], 12
    if vf & 0x10000000:
        fmt, off = [], 0
    for name, kind in zip(names, (normal, tangent, bitangent)):
        if kind == 1:
            fmt.append((name, "float3", off)); off += 12
        elif kind == 2:
            fmt.append((name, "byte4", off)); off += 4
    if colour1:
        fmt.append(("colour1", "byte4", off)); off += 4
    if colour2:
        fmt.append(("colour2", "byte4", off)); off += 4
    for i in range(uv_float):
        fmt.append((f"uv{i + 1}", "float2", off)); off += 8
    for i in range(uv_half):
        fmt.append((f"uv{i + 1}", "half2", off)); off += 4
    if blend_a == 1:
        fmt.append(("blend_weights", "float2", off)); off += 8
    elif blend_a == 2:
        fmt.append(("blend_weights", "byte4", off)); off += 4
    if blend_b == 1:
        fmt.append(("blend_indices", "float3", off)); off += 12
    elif blend_b == 2:
        fmt.append(("blend_indices", "byte4", off)); off += 4
    if extra:
        fmt.append(("light_dir", "byte4", off)); off += 8
    return fmt, off


def dds_format(header):
    """Pixel format of a DDS file from its first 128 bytes, as a short text.

    Met in the three games (every texture, 2026-10-08): DXT1, DXT3, DXT5, 'DXT1 cubemap', 'DXT5 cubemap',
    'A8R8G8B8' (uncompressed, TCS only) and 'A32B32G32R32F' (four floats a pixel, always 256 x 256)."""
    if header[:4] != b"DDS " or len(header) < 128:
        return "not a DDS file"
    pf_flags, fourcc, bits, r_mask, g_mask, b_mask, a_mask = struct.unpack_from("<I4sIIIII", header, 80)
    caps2 = struct.unpack_from("<I", header, 112)[0]
    if pf_flags & 4:
        code = struct.unpack("<I", fourcc)[0]
        name = {113: "A16B16G16R16F", 114: "R32F", 115: "G32R32F", 116: "A32B32G32R32F", 36: "A16B16G16R16",
                111: "R16F", 112: "G16R16F"}.get(code)
        if name is None:
            name = fourcc.decode("latin1") if all(32 < c < 127 for c in fourcc) else f"fourcc {code}"
    elif (bits, r_mask, g_mask, b_mask, a_mask) == (32, 0xFF0000, 0xFF00, 0xFF, 0xFF000000):
        name = "A8R8G8B8"
    else:
        name = f"uncompressed {bits} bit, masks {r_mask:x}/{g_mask:x}/{b_mask:x}/{a_mask:x}"
    if caps2 & 0xFE00:
        name += " cubemap"
    elif caps2 & 0x200000:
        name += " volume"
    return name


def float_dds_to_image(data, Image):
    """8-bit RGBA picture of an A32B32G32R32F DDS, or None with the reason when that would change the values.

    Only values inside 0..1 are turned into bytes (every such texture in the three games is); anything
    else would need a tone curve nobody defined, so it is left as DDS."""
    height, width = struct.unpack_from("<II", data, 12)
    if len(data) < 128 + width * height * 16:
        return None, "float texture shorter than its header says"
    values = struct.unpack_from(f"<{width * height * 4}f", data, 128)
    if any(not 0.0 <= v <= 1.0 for v in values):       # also false for NaN
        return None, "float texture with values outside 0..1: kept as DDS only"
    return Image.frombytes("RGBA", (width, height), bytes(int(v * 255 + 0.5) for v in values)), ""


class NU20:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.d = d = f.read()
        self.old_layout = 0
        self.payload_missing = False
        if d[:4] != b"NU20" and len(d) > 8:
            # LEGO Star Wars: The Complete Saga (container version 2) keeps the same chunks AFTER its textures and
            # buffers: the file starts with the offset of the NU20 block. Put the block first, so every offset in
            # this reader means the same thing, and remember where the textures now start (found 2026-10-05).
            (at,) = struct.unpack_from("<I", d, 0)
            if at + 8 <= len(d) and d[at + 4:at + 8] == b"NU20":
                self.old_layout = len(d) - at - 4
                self.d = d = d[at + 4:] + d[4:at + 4]
            elif d[4:8] == b"NU20" and at + 8 > len(d):
                # The offset points past the end of the file and the NU20 block follows it at once: a file of
                # that layout whose textures and buffers are not there. One such file is known: LEGO Indiana
                # Jones levels\outtakes\...\outtakes_losttemple_outrowin_pc.gsc (offset 36,452,288 in a file of
                # 204,996 bytes). The scene description is read; every mesh then reports its buffer as missing.
                self.payload_missing = True
                self.d = d = d[4:]
        magic, neg_size, self.version, _ = struct.unpack_from("<4siIi", d, 0)
        if magic != b"NU20" or neg_size >= 0:
            raise ValueError(f"{path}: not an NU20-first file ({magic!r}, {neg_size})")
        self.nu20_size = -neg_size
        if not self.old_layout and not self.payload_missing and self.nu20_size >= len(d):
            # One file is known: LEGO Batman chars\joker\joker.hgo_pc.gsc (container version 1). Its NU20 block
            # is the whole file: four DXT3 textures sit inside the TST0 chunk and the vertex and index data
            # inside VBIB, and its scene header is laid out differently. Its bone names (upperTorso, leftKnee,
            # weaponLeft ...) are not LEGO Batman's skeleton. This reader does not read that arrangement.
            raise ValueError(f"{path}: an older NU20 arrangement that this reader does not read: the NU20 block "
                             f"is the whole file ({self.nu20_size} bytes, version {self.version}), with the "
                             f"textures and buffers inside its chunks instead of after it")
        self.chunks = {}
        self.chunk_order = []
        pos = 16
        while pos < self.nu20_size:
            tag, size = struct.unpack_from("<4sI", d, pos)
            if size < 8:
                break
            name = tag.decode("latin1")
            self.chunks.setdefault(name, (pos, size))
            self.chunk_order.append((name, pos, size))
            pos += size
        self._names()
        self._gsnh()
        self._payload()

    # -- helpers -------------------------------------------------------
    def i32(self, off):
        return struct.unpack_from("<i", self.d, off)[0]

    def u32(self, off):
        return struct.unpack_from("<I", self.d, off)[0]

    def ptr(self, off):
        """Follow a self-relative pointer stored at off. 0 means null."""
        rel = self.i32(off)
        return off + rel if rel else 0

    # -- sections ------------------------------------------------------
    def _names(self):
        self.names = []
        if "NTBL" in self.chunks:
            pos, size = self.chunks["NTBL"]
            self.ntbl_data = pos + 12
            blob = self.d[pos + 12:pos + 12 + self.u32(pos + 8)]
            self.names = [s.decode("latin1") for s in blob.split(b"\0") if s]

    def _gsnh(self):
        d = self.d
        # The scene header is found through the pointer at 0x1C (relative to 0x20). In scene files that lands
        # 12 bytes into the GSNH chunk; character files (.ghg) have no GSNH chunk and keep it inside CDAT.
        g = self.gsnh = 0x20 + self.u32(0x1C)

        # textures
        self.textures = []
        tex_count = self.u32(g)
        table = self.ptr(g + 4)
        for i in range(tex_count):
            e = self.ptr(table + i * 4)
            w, h = struct.unpack_from("<II", d, e)
            self.textures.append({"index": i, "width": w, "height": h,
                                  "cubemap": self.u32(e + 0x34), "size": self.u32(e + 0x44)})

        # materials
        self.materials = []
        mat_count = self.u32(g + 0x0C)
        table = self.ptr(g + 0x08)
        for i in range(mat_count):
            m = self.ptr(table + i * 4)
            vf = self.u32(m + 0xB4 + 0x13C)
            fmt, stride = decode_vertex_format(vf)
            self.materials.append({
                "index": i,
                "id": self.u32(m + 0x38),
                "alpha_blend": self.u32(m + 0x40),
                "colour": [b / 255 for b in d[m + 0xC8:m + 0xCC]],
                "texture": struct.unpack_from("<h", d, m + 0x74)[0],
                "texture_flags": self.u32(m + 0xB4),
                "specular_tex": self.i32(m + 0xB4 + 0x48),
                "normal_tex": self.i32(m + 0xB4 + 0x4C),
                "cubemap_tex": self.i32(m + 0xB4 + 0x50),
                "shine_tex": self.i32(m + 0xB4 + 0x54),
                "ambient_tint": [b / 255 for b in d[m + 0xB4 + 0x6C:m + 0xB4 + 0x70]],
                "specular_tint": [b / 255 for b in d[m + 0xB4 + 0x74:m + 0xB4 + 0x78]],
                "reflection_power": struct.unpack_from("<f", d, m + 0xB4 + 0x78)[0],
                "specular_exponent": struct.unpack_from("<f", d, m + 0xB4 + 0x7C)[0],
                "vertex_format_flags": vf,
                "vertex_format": fmt,
                "vertex_stride": stride,
                "input_flags": self.u32(m + 0xB4 + 0x1B4),
                "shader_flags": self.u32(m + 0xB4 + 0x1B8),
            })

        # meshes
        self.meshes = []
        base = g + 0x1CC + 4 + self.i32(g + 0x1CC) + 0x0C
        block1 = base + self.i32(base)
        count1 = self.u32(base + 4)
        # Two mesh record layouts exist (measured on all 3,432 files of the three games, 2026-10-08):
        #   usual:  u32 primitive, u32 triangles, u16 stride, 8 bone bytes, u16 flags, then six u32
        #           (first vertex, vertices, first index, index buffer, vertex buffer, dynamic buffers)
        #   early:  u32 primitive, u16 triangles, u16 stride, 8 bone bytes, then u32 first vertex, vertices,
        #           first index, (0), (1), vertex buffer. Met in a few container-version-1 files left over from
        #           older games (e.g. TCS DROIDTRIFIGHTER_PC.GSC, Batman penguin_pc.gsc). The two u32 before
        #           the vertex buffer were always 0 and 1 there: taken as index buffer 0, the other is unknown.
        # In the usual layout the upper half of the triangle count is zero; in the early one it is the stride.
        mesh_at = [self.ptr(block1 + i * 4) for i in range(count1)]
        self.early_mesh_records = any(
            d[m] and 12 <= struct.unpack_from("<H", d, m + 6)[0] <= 255 for m in mesh_at)
        for i, m in enumerate(mesh_at):
            if self.early_mesh_records:
                prim, tri_count, stride = struct.unpack_from("<IHH", d, m)
                bones = list(struct.unpack_from("<8b", d, m + 8))
                flags, dyn_count = 0, 0
                v_off, v_count, i_off, ib_id, _, vb_id = struct.unpack_from("<6I", d, m + 16)
            else:
                prim, tri_count, stride = struct.unpack_from("<IIH", d, m)
                bones = list(struct.unpack_from("<8b", d, m + 10))
                flags = struct.unpack_from("<H", d, m + 18)[0]
                v_off, v_count, i_off, ib_id, vb_id, dyn_count = struct.unpack_from("<6I", d, m + 20)
            self.meshes.append({"index": i, "offset": m, "primitive": prim, "tri_count": tri_count, "stride": stride,
                                "bones": bones, "flags": flags, "vertex_offset": v_off, "vertex_count": v_count,
                                "index_offset": i_off, "index_buffer": ib_id, "vertex_buffer": vb_id,
                                "dynamic_buffers": dyn_count, "material": -1})
            if dyn_count & 0xFF00 == 0xF000 and not self.early_mesh_records:
                # vertex-animated mesh (see 0x10000000 in decode_vertex_format): the low byte counts the
                # frames, u32 at +44 is the size of a position (12), the frames' vertex buffers follow at +56
                frames = dyn_count & 0xFF
                if self.u32(m + 44) == 12 and frames <= 64:
                    self.meshes[-1]["position_buffers"] = list(struct.unpack_from(f"<{frames}I", d, m + 56))

        # skeleton (character files): count at +0x164, then a self-relative pointer to the bone records.
        # Bone record, 96 bytes: 4x4 matrix, vec3, name pointer (relative to itself), parent (s8), 15 pad.
        # After the records: one 4x4 bind matrix per bone (local to parent), then one inverse bind per bone.
        self.bones = []
        bone_count = self.i32(g + 0x164)
        if 0 < bone_count < 512 and self.i32(g + 0x168):
            rec = g + 0x168 + self.i32(g + 0x168)
            for i in range(bone_count):
                o = rec + i * 96
                name_rel = self.i32(o + 0x4C)
                self.bones.append({"index": i, "name": _cstr(d, o + 0x4C + name_rel) if name_rel else "",
                                   "parent": struct.unpack_from("<b", d, o + 0x50)[0]})
            bind = rec + bone_count * 96
            for i, bone in enumerate(self.bones):
                bone["bind_local"] = list(struct.unpack_from("<16f", d, bind + i * 64))
                bone["inverse_bind"] = list(struct.unpack_from("<16f", d, bind + (bone_count + i) * 64))
                # The record's own matrix is a second rest rotation (no translation), in the animation files'
                # mirrored space. Study only: the skinning pose is bind_local / inverse_bind, and the
                # exporters use that. rest_local (record rotation + bind translation) was a wrong turn, kept
                # so older notes still make sense.
                record = list(struct.unpack_from("<16f", d, rec + i * 96))
                bone["record_matrix"] = record
                rest = record[:12] + bone["bind_local"][12:15] + [1.0]
                rest[3] = rest[7] = rest[11] = 0.0
                bone["rest_local"] = rest

        # scene: models (mesh + material lists) and special objects (named, with a matrix)
        self.models = []
        self.special_objects = []
        self.is_model = self.i32(g + 0x18C) != 0
        disp_rel = self.i32(g + 0x10C)
        if disp_rel:
            disp = g + 0x10C + 4 + disp_rel - 4
            self.disp = disp
            model_count = self.i32(disp + 0x10)
            if model_count > 0:
                p = disp + 0x14
                models_at = p + 4 + self.i32(p) - 4
                starts_at = (disp + 0x1C) + 4 + self.i32(disp + 0x1C) - 4
                q = models_at
                for i in range(model_count):
                    mesh_count = self.i32(q)
                    mats_at = q + 4 + self.i32(q + 4)
                    ids_at = q + 8 + self.i32(q + 8)
                    mats = [self.i32(mats_at + (mesh_count - 1 - k) * 4) for k in range(mesh_count)]
                    ids = [self.i32(ids_at + (mesh_count - 1 - k) * 4) for k in range(mesh_count)]
                    self.models.append({"index": i, "offset": q, "materials": mats, "ids": ids, "meshes": []})
                    q += 12
                # Display command list: 16-byte records { u8 type, u8[3] flags, i32 self-relative pointer, 8 pad }.
                # 0x80 material, 0x82 draw mesh (pointer -> mesh record), 0x83 bounds, 0x84/0xB0 block markers.
                # A model's "ids" are indices of its 0x82 commands; its "materials" list pairs with them.
                cmd_count = self.i32(disp + 4)
                cmd_at = disp + 0x98
                # The list has two parts (measured on the three games, 2026-10-08). First the static draws sorted
                # by material: for each material { 0x85, 0x87, 0x87, 0x80 material, 0x8B, then 0x83 + 0x82 per
                # mesh }. A 0x84 command ends that part; the draws after it carry no material command, and get
                # theirs from the model lists alone.
                self.commands = []
                mesh_by_off = {m["offset"]: m["index"] for m in self.meshes}
                mat_table = self.ptr(g + 0x08)
                mat_by_off = {self.ptr(mat_table + i * 4): i for i in range(len(self.materials))}
                cmd_mesh = {}
                list_material = {}
                current = -1
                for i in range(cmd_count):
                    o = cmd_at + i * 16
                    ctype = d[o]
                    target = o + 4 + self.i32(o + 4) if self.i32(o + 4) else 0
                    self.commands.append((ctype, target))
                    if ctype == 0x80:
                        current = mat_by_off.get(target, -1)
                    elif ctype == 0x84:
                        current = -1
                    elif ctype == 0x82:
                        cmd_mesh[i] = mesh_by_off.get(target, -1)
                        if current >= 0 and cmd_mesh[i] >= 0:
                            list_material.setdefault(cmd_mesh[i], current)
                q = starts_at
                for model in self.models:
                    model["first_mesh"] = struct.unpack_from("<H", d, q)[0]
                    q += 2
                    for cid, mat in zip(model["ids"], model["materials"]):
                        mi = cmd_mesh.get(cid, -1)
                        model["meshes"].append(mi)
                        if mi >= 0 and 0 <= mat < len(self.materials):
                            self.meshes[mi]["material"] = mat
                            self.meshes[mi]["material_source"] = "model list"
                # A mesh no model names, or whose model material has another vertex size than the mesh, takes
                # the material of its own draw in the sorted part when that one fits the vertex size.
                for mi, mat in list_material.items():
                    mesh = self.meshes[mi]
                    if not mesh["stride"] or self.materials[mat]["vertex_stride"] != mesh["stride"]:
                        continue
                    have = mesh["material"]
                    if have < 0 or self.materials[have]["vertex_stride"] != mesh["stride"]:
                        mesh["material"] = mat
                        mesh["material_source"] = "display list"
            so_count = self.i32(disp + 0x6C)
            if so_count > 0:
                p = disp + 0x70
                so_at = p + 4 + self.i32(p) - 4
                by_offset = {m["offset"]: m["index"] for m in self.models}
                for i in range(so_count):
                    o = so_at + i * 0xD0
                    matrix = list(struct.unpack_from("<16f", d, o))
                    mesh_ptr = self.i32(o + 0xB0)
                    name_rel = self.i32(o + 0xB4)
                    name = _cstr(d, o + 0xB8 + name_rel - 4) if name_rel else ""
                    model_off = o + 0xB8 + mesh_ptr - 8
                    self.special_objects.append({"index": i, "name": name, "matrix": matrix,
                                                 "model": by_offset.get(model_off, -1)})

    def _payload(self):
        d = self.d
        if self.payload_missing:
            for t in self.textures:
                t["size"], t["cubemap"], t["missing"] = 0, 0, "the file holds no texture data"
            self.vertex_buffers, self.index_buffers, self.payload_end = [], [], self.nu20_size
            return
        if self.old_layout:
            # version 2: a count, then each texture as six numbers (width, height, levels, type, ?, size) and its DDS.
            # Cubemap faces are listed in the header but have no record here.
            pos = self.old_layout + 2
            for t in self.textures:
                t["size"], t["cubemap"] = 0, 0
            i = 0
            while i < len(self.textures) and d[pos + 24:pos + 28] == b"DDS ":
                t = self.textures[i]
                t["width"], t["height"] = self.u32(pos), self.u32(pos + 4)
                t["data_offset"], t["size"] = pos + 24, self.u32(pos + 20)
                t["cubemap"] = 1 if self.u32(pos + 24 + 0x70) & 0xFE00 else 0
                pos += 24 + t["size"]
                i += 6 if t["cubemap"] else 1          # a cubemap's five other faces are header entries with no data
        else:
            pos = self.nu20_size + 4
            for t in self.textures:
                t["data_offset"] = pos
                pos += t["size"]
        # Texture entries without data (measured on all three games, 2026-10-08): exactly five follow every
        # cubemap, and there are no others. They stand for the cubemap's other faces, whose pixels are inside
        # the cubemap's own DDS; nothing is missing from the file.
        last_cube = -1
        for t in self.textures:
            if t["size"]:
                t["format"] = dds_format(d[t["data_offset"]:t["data_offset"] + 128])
                last_cube = t["index"] if "cubemap" in t["format"] else -1
            elif 0 <= last_cube and t["index"] - last_cube <= 5:
                t["cubemap_face_of"] = last_cube
        self.vertex_buffers = []
        (n,) = struct.unpack_from("<H", d, pos)
        pos += 2
        for _ in range(n):
            size = self.u32(pos)
            self.vertex_buffers.append((pos + 4, size))
            pos += 4 + size
        self.index_buffers = []
        (n,) = struct.unpack_from("<H", d, pos)
        pos += 2
        for _ in range(n):
            size = self.u32(pos)
            self.index_buffers.append((pos + 4, size))
            pos += 4 + size
        self.payload_end = pos

    # -- geometry ------------------------------------------------------
    def mesh_layout(self, mesh):
        """Vertex layout of one mesh: ({attribute: (kind, offset)}, note).

        The layout comes from the vertex format flags of the mesh's material. When there is no material, or
        the flags imply another vertex size than the mesh record gives, only the position (always the first
        twelve bytes) is known and the note says why; nothing else is guessed."""
        mat = self.materials[mesh["material"]] if 0 <= mesh["material"] < len(self.materials) else None
        if mat is None:
            return {"position": ("float3", 0)}, "no material paired with this mesh: positions only"
        if mat["vertex_stride"] != mesh["stride"]:
            if mat["vertex_format_flags"] & 0x10000000:
                return {}, (f"vertex layout unknown: material {mat['index']} format "
                            f"{mat['vertex_format_flags']:#x} implies {mat['vertex_stride']} bytes a vertex, "
                            f"the mesh has {mesh['stride']}, and the vertex holds no position")
            return {"position": ("float3", 0)}, (
                f"vertex layout unknown: material {mat['index']} format {mat['vertex_format_flags']:#x} implies "
                f"{mat['vertex_stride']} bytes a vertex, the mesh has {mesh['stride']}: positions only")
        return {a: (k, o) for a, k, o in mat["vertex_format"]}, ""

    def mesh_problem(self, mesh):
        """Why a mesh cannot be read at all ('' when it can). Nothing is read past a buffer's end."""
        if not mesh["tri_count"] or not mesh["vertex_count"] or not mesh["stride"]:
            return "empty mesh record (no triangles, vertices or vertex size)"
        if mesh["primitive"] not in (5, 6):
            # 6 = triangle strip in every drawn mesh of the three games; 5 is read as a triangle list;
            # anything else is not a triangle primitive this reader knows
            return f"primitive type {mesh['primitive']} is not known"
        stride = mesh["stride"]
        if mesh["vertex_buffer"] >= len(self.vertex_buffers):
            return f"vertex buffer {mesh['vertex_buffer']} does not exist ({len(self.vertex_buffers)} in the file)"
        if mesh["index_buffer"] >= len(self.index_buffers):
            return f"index buffer {mesh['index_buffer']} does not exist ({len(self.index_buffers)} in the file)"
        _, vb_size = self.vertex_buffers[mesh["vertex_buffer"]]
        _, ib_size = self.index_buffers[mesh["index_buffer"]]
        if (mesh["vertex_offset"] + mesh["vertex_count"]) * stride > vb_size:
            return (f"vertices {mesh['vertex_offset']}..{mesh['vertex_offset'] + mesh['vertex_count']} of {stride} "
                    f"bytes run past vertex buffer {mesh['vertex_buffer']} ({vb_size} bytes)")
        n_idx = mesh["tri_count"] + 2 if mesh["primitive"] == 6 else mesh["tri_count"] * 3
        if (mesh["index_offset"] + n_idx) * 2 > ib_size:
            return (f"indices {mesh['index_offset']}..{mesh['index_offset'] + n_idx} run past index buffer "
                    f"{mesh['index_buffer']} ({ib_size // 2} indices)")
        return ""

    def mesh_geometry(self, mesh):
        """Returns (positions, normals, uvs, colours, triangles) for one mesh, or None when it cannot be read.

        mesh["geometry_note"] is set to the reason whenever something could not be read: None is returned for
        a mesh that cannot be read at all, and positions alone for a mesh whose vertex layout is not known."""
        d = self.d
        problem = self.mesh_problem(mesh)
        if problem:
            mesh["geometry_note"] = problem
            return None
        stride = mesh["stride"]
        vb_off, _ = self.vertex_buffers[mesh["vertex_buffer"]]
        ib_off, _ = self.index_buffers[mesh["index_buffer"]]
        v0 = vb_off + mesh["vertex_offset"] * stride
        count = mesh["vertex_count"]
        fmt, note = self.mesh_layout(mesh)
        if "position" in fmt and stride < 12:
            mesh["geometry_note"] = f"vertex size {stride} is too small for a position"
            return None
        raw = d[v0:v0 + count * stride]

        def column(kind_offset, code):
            o = kind_offset[1]
            return [struct.unpack_from(code, raw, b + o) for b in range(0, count * stride, stride)]

        if "position" in fmt:
            pos = column(fmt["position"], "<3f")
        else:
            # positions in vertex buffers of their own, one per animation frame: the first frame is given
            frames = mesh.get("position_buffers") or []
            end = (mesh["vertex_offset"] + count) * 12
            if not frames or frames[0] >= len(self.vertex_buffers) or self.vertex_buffers[frames[0]][1] < end:
                mesh["geometry_note"] = note or (
                    "the vertex holds no position and the mesh record names no usable position buffer")
                return None
            p0 = self.vertex_buffers[frames[0]][0] + mesh["vertex_offset"] * 12
            pos = [struct.unpack_from("<3f", d, p0 + i * 12) for i in range(count)]
        nrm, uv, col = [], [], []
        if "normal" in fmt:
            if fmt["normal"][0] == "float3":
                nrm = column(fmt["normal"], "<3f")
            else:
                nrm = [(x / 255 * 2 - 1, y / 255 * 2 - 1, z / 255 * 2 - 1)
                       for x, y, z in column(fmt["normal"], "<3B")]
        if "uv1" in fmt:
            uv = column(fmt["uv1"], "<2f" if fmt["uv1"][0] == "float2" else "<2e")
        if "colour1" in fmt:
            col = [(r / 255, g / 255, b_ / 255, a / 255) for r, g, b_, a in column(fmt["colour1"], "<4B")]
        tris = []
        bad_index = 0
        if mesh["primitive"] == 6:  # triangle strip
            n_idx = mesh["tri_count"] + 2
            idx = struct.unpack_from(f"<{n_idx}H", d, ib_off + mesh["index_offset"] * 2)
            for i in range(n_idx - 2):
                a, b_, c = idx[i], idx[i + 1], idx[i + 2]
                if a == b_ or b_ == c or a == c:
                    continue
                if a >= count or b_ >= count or c >= count:
                    bad_index += 1
                    continue
                tris.append((a, b_, c) if i % 2 == 0 else (b_, a, c))
        else:  # triangle list
            idx = struct.unpack_from(f"<{mesh['tri_count'] * 3}H", d, ib_off + mesh["index_offset"] * 2)
            for i in range(0, len(idx), 3):
                if max(idx[i:i + 3]) >= count:
                    bad_index += 1
                    continue
                tris.append(tuple(idx[i:i + 3]))
        if bad_index:
            note = (note + "; " if note else "") + (
                f"{bad_index} triangles left out: they name vertices beyond the mesh's {count}")
        if note:
            mesh["geometry_note"] = note
        else:
            mesh.pop("geometry_note", None)
        return pos, nrm, uv, col, tris

    # -- export --------------------------------------------------------
    def export(self, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        tex_dir = os.path.join(out_dir, "textures")
        os.makedirs(tex_dir, exist_ok=True)
        try:
            from PIL import Image
        except ImportError:
            Image = None
        png_ok = set()
        self.texture_report = report = {"declared": len(self.textures), "dds": 0, "png": 0, "no_data": []}
        for t in self.textures:
            if not t["size"]:
                # nothing to write: say why, so a missing tex_NNN file is never a silent gap
                if "cubemap_face_of" in t:
                    why = f"face of cubemap {t['cubemap_face_of']} (its pixels are in tex_{t['cubemap_face_of']:03d}.dds)"
                else:
                    why = t.get("missing", "entry without data")
                t["not_written"] = why
                report["no_data"].append((t["index"], why))
                continue
            data = self.d[t["data_offset"]:t["data_offset"] + t["size"]]
            dds_path = os.path.join(tex_dir, f"tex_{t['index']:03d}.dds")
            with open(dds_path, "wb") as f:
                f.write(data)
            report["dds"] += 1
            # PNG copy (top mip; of a cubemap the first face only) for tools that can't read DDS
            if Image is None:
                t["png_error"] = "Pillow is not installed"
                continue
            png_path = os.path.join(tex_dir, f"tex_{t['index']:03d}.png")
            try:
                if t.get("format") == "A32B32G32R32F":
                    im, why = float_dds_to_image(data, Image)
                    if im is None:
                        raise ValueError(why)
                    t["png_note"] = "8-bit copy of a float texture (values 0..1 times 255)"
                else:
                    im = Image.open(dds_path)
                    if "cubemap" in t.get("format", ""):
                        t["png_note"] = "first face of the cubemap only"
                with im:
                    t["has_alpha"] = im.mode == "RGBA" and im.getextrema()[3][0] < 255
                    im.save(png_path)
                png_ok.add(t["index"])
                report["png"] += 1
            except Exception as ex:  # formats Pillow cannot read stay DDS-only
                t["png_error"] = str(ex)[:80]
                if os.path.exists(png_path):
                    os.remove(png_path)
        with open(os.path.join(out_dir, "scene.mtl"), "w") as f:
            for m in self.materials:
                f.write(f"newmtl mat_{m['index']:03d}\nKd {m['colour'][0]:.4f} {m['colour'][1]:.4f} {m['colour'][2]:.4f}\n")
                if m["texture"] >= 0:
                    ext = "png" if m["texture"] in png_ok else "dds"
                    f.write(f"map_Kd textures/tex_{m['texture']:03d}.{ext}\n")
                f.write("\n")
        # Static world = every model no special object refers to (already in world space).
        # Special objects (builds, breakables, props, vehicles) keep local-space geometry in objects/
        # and are placed by their matrix (row-major, translation in elements 12..14).
        object_models = {o["model"] for o in self.special_objects if o["model"] >= 0}
        static_meshes = []
        for model in self.models:
            if model["index"] not in object_models:
                static_meshes += [(mi, None) for mi in model["meshes"] if mi >= 0]
        skipped = self._write_obj(os.path.join(out_dir, "static.obj"), "scene.mtl", static_meshes)
        obj_dir = os.path.join(out_dir, "objects")
        os.makedirs(obj_dir, exist_ok=True)
        placed = []
        for mi_model in sorted(object_models):
            meshes = [(mi, None) for mi in self.models[mi_model]["meshes"] if mi >= 0]
            skipped += self._write_obj(os.path.join(obj_dir, f"model_{mi_model:04d}.obj"), "../scene.mtl", meshes)
        for o in self.special_objects:
            if o["model"] >= 0:
                placed += [(mi, o["matrix"]) for mi in self.models[o["model"]]["meshes"] if mi >= 0]
        # scene.obj = everything composed in world space, for checking only
        self._write_obj(os.path.join(out_dir, "scene.obj"), "scene.mtl", static_meshes + placed)
        meta = {
            "source": os.path.basename(self.path), "version": self.version,
            "chunks": [{"tag": n, "offset": p, "size": s} for n, p, s in self.chunk_order],
            "names": self.names, "textures": self.textures,
            "materials": [{k: v for k, v in m.items()} for m in self.materials],
            "meshes": self.meshes, "models": self.models, "special_objects": self.special_objects,
        }
        with open(os.path.join(out_dir, "scene.json"), "w") as f:
            json.dump(meta, f, indent=1)
        return skipped

    def _write_obj(self, path, mtl, mesh_list):
        """mesh_list: [(mesh index, matrix or None)]. Returns number of meshes skipped."""
        vbase = tbase = nbase = 1
        skipped = 0
        with open(path, "w") as f:
            f.write(f"mtllib {mtl}\n")
            for n_inst, (mi, mtx) in enumerate(mesh_list):
                mesh = self.meshes[mi]
                try:
                    geo = self.mesh_geometry(mesh)
                except (struct.error, IndexError):
                    geo = None
                if not geo:
                    skipped += 1
                    continue
                pos, nrm, uv, col, tris = geo
                if mtx:
                    m = mtx
                    pos = [(x * m[0] + y * m[4] + z * m[8] + m[12],
                            x * m[1] + y * m[5] + z * m[9] + m[13],
                            x * m[2] + y * m[6] + z * m[10] + m[14]) for x, y, z in pos]
                    nrm = [(x * m[0] + y * m[4] + z * m[8],
                            x * m[1] + y * m[5] + z * m[9],
                            x * m[2] + y * m[6] + z * m[10]) for x, y, z in nrm]
                f.write(f"o mesh_{mesh['index']:04d}_{n_inst}\n")
                for p in pos:
                    f.write(f"v {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")
                for t in uv:
                    f.write(f"vt {t[0]:.6f} {1 - t[1]:.6f}\n")
                for n in nrm:
                    f.write(f"vn {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}\n")
                if mesh["material"] >= 0:
                    f.write(f"usemtl mat_{mesh['material']:03d}\n")
                # OBJ counts v, vt and vn separately, so each needs its own running base
                for a, b, c in tris:
                    if uv and nrm:
                        f.write("f " + " ".join(f"{x + vbase}/{x + tbase}/{x + nbase}" for x in (a, b, c)) + "\n")
                    elif uv:
                        f.write("f " + " ".join(f"{x + vbase}/{x + tbase}" for x in (a, b, c)) + "\n")
                    elif nrm:
                        f.write("f " + " ".join(f"{x + vbase}//{x + nbase}" for x in (a, b, c)) + "\n")
                    else:
                        f.write(f"f {a + vbase} {b + vbase} {c + vbase}\n")
                vbase += len(pos)
                tbase += len(uv)
                nbase += len(nrm)
        return skipped

    def info(self):
        print(f"{self.path}: NU20 v{self.version}, header block {self.nu20_size} bytes, file {len(self.d)} bytes")
        print(" chunks:", " ".join(f"{n}({s})" for n, _, s in self.chunk_order))
        print(f" names {len(self.names)}  textures {len(self.textures)}  materials {len(self.materials)}  "
              f"meshes {len(self.meshes)}  models {len(self.models)}  special objects {len(self.special_objects)}")
        print(f" vertex buffers {[s for _, s in self.vertex_buffers]}  index buffers {[s for _, s in self.index_buffers]}")
        print(f" payload ends at {self.payload_end} of {len(self.d)}")
        if self.payload_missing:
            print(" NOTE: this file holds only the scene description: its textures and buffers are not in it")
        with_data = [t for t in self.textures if t["size"]]
        kinds = {}
        for t in with_data:
            kinds[t.get("format", "?")] = kinds.get(t.get("format", "?"), 0) + 1
        faces = sum(1 for t in self.textures if "cubemap_face_of" in t)
        other = len(self.textures) - len(with_data) - faces
        print(f" textures with data: {len(with_data)} {kinds}; entries standing for cubemap faces: {faces}"
              + (f"; other entries without data: {other}" if other else ""))
        report = getattr(self, "texture_report", None)
        if report:
            print(f" textures written: {report['dds']} DDS, {report['png']} PNG of {report['declared']} entries")
            for t in self.textures:
                if t.get("png_error"):
                    print(f"  tex {t['index']}: no PNG ({t.get('format')}): {t['png_error']}")
        ok = sum(1 for m in self.meshes if 0 <= m["material"] < len(self.materials)
                 and self.materials[m['material']]['vertex_stride'] == m['stride'])
        print(f" meshes with a material: {sum(1 for m in self.meshes if m['material'] >= 0)}; stride matches material format: {ok}")
        for t in self.textures[:6]:
            print("  tex", t)
        for o in self.special_objects[:12]:
            print("  obj", o["name"], "model", o["model"], "pos", [round(x, 2) for x in o["matrix"][12:15]])


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    nu = NU20(argv[1])
    if argv[0] == "info":
        nu.info()
    elif argv[0] == "export":
        skipped = nu.export(argv[2])
        nu.info()
        print(f" exported to {argv[2]} ({skipped} meshes skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
