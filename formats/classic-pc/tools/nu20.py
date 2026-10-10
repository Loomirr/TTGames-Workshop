"""Classic PC NU20 model reader, adapted from Gibby / stryderjoe (MIT).

See ../LICENSE. This reader is separate from NXG/DX11 and Xbox NU20.
Only the observed PC chunk/payload layouts are accepted. No native writer.
"""
import math
import struct
try:
    from .reader_bounds import span, finite, read_file
except ImportError:
    from reader_bounds import span, finite, read_file

def unpack(fmt, data, at=0):
    span(data, at, struct.calcsize(fmt), 'NU20 field')
    return struct.unpack_from(fmt, data, at)

def _cstr(d, off):
    span(d, off, 1, "NU20 string")
    end = d.find(b"\0", off, min(len(d), off+4096))
    if end < 0: raise ValueError("Unterminated or overlong NU20 string")
    return d[off:end].decode("latin1")


def decode_vertex_format(vf):
    """Returns list of (attribute, kind, offset) and the stride implied by the format flags.

    Contributor-reported measurements (2026-10-08) on TCS, Indiana Jones 1 and Batman 1 (3,431 files): in every
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
    pf_flags, fourcc, bits, r_mask, g_mask, b_mask, a_mask = unpack("<I4sIIIII", header, 80)
    caps2 = unpack("<I", header, 112)[0]
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


class NU20:
    def __init__(self, path):
        self.path = path
        self.d = d = read_file(path, 256 * 1024 * 1024)
        self.old_layout = 0
        self.payload_missing = False
        if d[:4] != b"NU20" and len(d) > 8:
            # LEGO Star Wars: The Complete Saga (container version 2) keeps the same chunks AFTER its textures and
            # buffers: the file starts with the offset of the NU20 block. Put the block first, so every offset in
            # this reader means the same thing, and remember where the textures now start (found 2026-10-05).
            (at,) = unpack("<I", d, 0)
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
        magic, neg_size, self.version, _ = unpack("<4siIi", d, 0)
        if magic != b"NU20" or neg_size >= 0:
            raise ValueError(f"{path}: not an NU20-first file ({magic!r}, {neg_size})")
        if self.version not in (1, 2, 4):
            raise ValueError(f"Unsupported classic PC NU20 version {self.version}")
        self.nu20_size = -neg_size
        span(d, 0, self.nu20_size, "NU20 metadata")
        if self.old_layout and self.old_layout < self.nu20_size:
            raise ValueError("Relocated NU20 metadata overlaps the payload")
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
            tag, size = unpack("<4sI", d, pos)
            if size < 8 or pos + size > self.nu20_size:
                raise ValueError("Invalid NU20 chunk extent")
            name = tag.decode("latin1")
            if name in self.chunks: raise ValueError("Duplicate NU20 chunk: " + name)
            self.chunks[name] = (pos, size)
            self.chunk_order.append((name, pos, size))
            pos += size
            # VBIB is followed by its counted buffer descriptors, not another
            # ordinary chunk header. The geometry tables address them directly.
            if name == 'VBIB':
                break
        self._names()
        self._gsnh()
        self._payload()

    # -- helpers -------------------------------------------------------
    def i32(self, off):
        return unpack("<i", self.d, off)[0]

    def u32(self, off):
        return unpack("<I", self.d, off)[0]

    def ptr(self, off):
        """Follow a self-relative pointer stored at off. 0 means null."""
        rel = self.i32(off)
        target = off + rel if rel else 0
        if rel and not 0 < target < self.nu20_size:
            raise ValueError('NU20 pointer outside metadata')
        return target

    def table(self, at, count, stride, label, limit=1000000):
        if not 0 <= count <= limit or (count and not at):
            raise ValueError(label + ': invalid count or null table')
        if count and (at < 0 or at + count * stride > self.nu20_size):
            raise ValueError(label + ': outside NU20 metadata')
        return count

    # -- sections ------------------------------------------------------
    def _names(self):
        self.names = []
        if "NTBL" in self.chunks:
            pos, size = self.chunks["NTBL"]
            self.ntbl_data = pos + 12
            length = self.u32(pos + 8)
            if 12 + length > size: raise ValueError("NU20 names exceed their chunk")
            blob = self.d[pos + 12:pos + 12 + length]
            self.names = [s.decode("latin1") for s in blob.split(b"\0") if s]

    def _gsnh(self):
        d = self.d
        # The scene header is found through the pointer at 0x1C (relative to 0x20). In scene files that lands
        # 12 bytes into the GSNH chunk; character files (.ghg) have no GSNH chunk and keep it inside CDAT.
        g = self.gsnh = 0x20 + self.u32(0x1C)

        self.table(g, 1, 0x1D0, "scene header")

        # textures
        self.textures = []
        tex_count = self.u32(g)
        table = self.ptr(g + 4)
        self.table(table, tex_count, 4, "textures", 65536)
        for i in range(tex_count):
            e = self.ptr(table + i * 4)
            self.table(e, 1, 0x48, "texture record")
            w, h = unpack("<II", d, e)
            self.textures.append({"index": i, "width": w, "height": h,
                                  "cubemap": self.u32(e + 0x34), "size": self.u32(e + 0x44)})

        # materials
        self.materials = []
        mat_count = self.u32(g + 0x0C)
        table = self.ptr(g + 0x08)
        self.table(table, mat_count, 4, "materials", 65536)
        for i in range(mat_count):
            m = self.ptr(table + i * 4)
            self.table(m, 1, 0x270, "material record")
            vf = self.u32(m + 0xB4 + 0x13C)
            fmt, stride = decode_vertex_format(vf)
            self.materials.append({
                "index": i,
                "id": self.u32(m + 0x38),
                "alpha_blend": self.u32(m + 0x40),
                "colour": [b / 255 for b in d[m + 0xC8:m + 0xCC]],
                "texture": unpack("<h", d, m + 0x74)[0],
                "texture_flags": self.u32(m + 0xB4),
                "specular_tex": self.i32(m + 0xB4 + 0x48),
                "normal_tex": self.i32(m + 0xB4 + 0x4C),
                "cubemap_tex": self.i32(m + 0xB4 + 0x50),
                "shine_tex": self.i32(m + 0xB4 + 0x54),
                "ambient_tint": [b / 255 for b in d[m + 0xB4 + 0x6C:m + 0xB4 + 0x70]],
                "specular_tint": [b / 255 for b in d[m + 0xB4 + 0x74:m + 0xB4 + 0x78]],
                "reflection_power": unpack("<f", d, m + 0xB4 + 0x78)[0],
                "specular_exponent": unpack("<f", d, m + 0xB4 + 0x7C)[0],
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
        self.table(block1, count1, 4, "mesh pointers")
        mesh_at = [self.ptr(block1 + i * 4) for i in range(count1)]
        for at in mesh_at: self.table(at, 1, 44, "mesh record")
        self.early_mesh_records = self.version == 1 and any(
            d[m] and 12 <= unpack("<H", d, m + 6)[0] <= 255 for m in mesh_at)
        for i, m in enumerate(mesh_at):
            if self.early_mesh_records:
                prim, tri_count, stride = unpack("<IHH", d, m)
                bones = list(unpack("<8b", d, m + 8))
                flags, dyn_count = 0, 0
                v_off, v_count, i_off, ib_id, _, vb_id = unpack("<6I", d, m + 16)
            else:
                prim, tri_count, stride = unpack("<IIH", d, m)
                bones = list(unpack("<8b", d, m + 10))
                flags = unpack("<H", d, m + 18)[0]
                v_off, v_count, i_off, ib_id, vb_id, dyn_count = unpack("<6I", d, m + 20)
            self.meshes.append({"index": i, "offset": m, "primitive": prim, "tri_count": tri_count, "stride": stride,
                                "bones": bones, "flags": flags, "vertex_offset": v_off, "vertex_count": v_count,
                                "index_offset": i_off, "index_buffer": ib_id, "vertex_buffer": vb_id,
                                "dynamic_buffers": dyn_count, "material": -1})
            if dyn_count & 0xFF00 == 0xF000 and not self.early_mesh_records:
                # vertex-animated mesh (see 0x10000000 in decode_vertex_format): the low byte counts the
                # frames, u32 at +44 is the size of a position (12), the frames' vertex buffers follow at +56
                frames = dyn_count & 0xFF
                if self.u32(m + 44) == 12 and frames <= 64:
                    self.meshes[-1]["position_buffers"] = list(unpack(f"<{frames}I", d, m + 56))

        # skeleton (character files): count at +0x164, then a self-relative pointer to the bone records.
        # Bone record, 96 bytes: 4x4 matrix, vec3, name pointer (relative to itself), parent (s8), 15 pad.
        # After the records: one 4x4 bind matrix per bone (local to parent), then one inverse bind per bone.
        self.bones = []
        bone_count = self.i32(g + 0x164)
        if not 0 <= bone_count < 512: raise ValueError("Invalid NU20 bone count")
        if bone_count and not self.i32(g+0x168): raise ValueError("Missing NU20 bone table")
        if bone_count:
            rec = g + 0x168 + self.i32(g + 0x168)
            self.table(rec, bone_count, 224, "bones and binds", 511)
            for i in range(bone_count):
                o = rec + i * 96
                name_rel = self.i32(o + 0x4C)
                self.bones.append({"index": i, "name": _cstr(d, o + 0x4C + name_rel) if name_rel else "",
                                   "parent": unpack("<b", d, o + 0x50)[0]})
            bind = rec + bone_count * 96
            for i, bone in enumerate(self.bones):
                bone["bind_local"] = list(unpack("<16f", d, bind + i * 64))
                bone["inverse_bind"] = list(unpack("<16f", d, bind + (bone_count + i) * 64))
                # The record's own matrix is a second rest rotation (no translation), in the animation files'
                # mirrored space. Study only: the skinning pose is bind_local / inverse_bind, and the
                # exporters use that. rest_local (record rotation + bind translation) was a wrong turn, kept
                # so older notes still make sense.
                record = list(unpack("<16f", d, rec + i * 96))
                bone["record_matrix"] = record
                rest = record[:12] + bone["bind_local"][12:15] + [1.0]
                rest[3] = rest[7] = rest[11] = 0.0
                bone["rest_local"] = rest
                finite(bone["bind_local"] + bone["inverse_bind"] + record, "bone matrices")
                if not -1 <= bone["parent"] < i: raise ValueError("Invalid/cyclic NU20 parent order")
            names = [b["name"] for b in self.bones]
            if any(not name for name in names) or len(set(names)) != len(names):
                raise ValueError("Empty/duplicate NU20 bone names")

        # scene: models (mesh + material lists) and special objects (named, with a matrix)
        self.models = []
        self.special_objects = []
        self.is_model = self.i32(g + 0x18C) != 0
        disp_rel = self.i32(g + 0x10C)
        if disp_rel:
            disp = g + 0x10C + 4 + disp_rel - 4
            self.disp = disp
            self.table(disp, 1, 0x98, "display header")
            model_count = self.i32(disp + 0x10)
            if not 0 <= model_count <= 1000000: raise ValueError("Invalid model count")
            if model_count > 0:
                p = disp + 0x14
                models_at = p + 4 + self.i32(p) - 4
                starts_at = (disp + 0x1C) + 4 + self.i32(disp + 0x1C) - 4
                self.table(models_at, model_count, 12, "model records")
                self.table(starts_at, model_count, 2, "model starts")
                q = models_at
                for i in range(model_count):
                    mesh_count = self.i32(q)
                    mats_at = q + 4 + self.i32(q + 4)
                    ids_at = q + 8 + self.i32(q + 8)
                    self.table(mats_at, mesh_count, 4, "model materials")
                    self.table(ids_at, mesh_count, 4, "model commands")
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
                self.table(cmd_at, cmd_count, 16, "display commands")
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
                    model["first_mesh"] = unpack("<H", d, q)[0]
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
            if not 0 <= so_count <= 1000000: raise ValueError("Invalid object count")
            if so_count > 0:
                p = disp + 0x70
                so_at = p + 4 + self.i32(p) - 4
                self.table(so_at, so_count, 0xD0, "special objects")
                by_offset = {m["offset"]: m["index"] for m in self.models}
                for i in range(so_count):
                    o = so_at + i * 0xD0
                    matrix = list(unpack("<16f", d, o))
                    finite(matrix, "object matrix")
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
                span(d, t["data_offset"], t["size"], "DDS payload")
                if d[t["data_offset"]:t["data_offset"]+4] != b"DDS ": raise ValueError("Missing NU20 DDS signature")
                t["format"] = dds_format(d[t["data_offset"]:t["data_offset"] + 128])
                last_cube = t["index"] if "cubemap" in t["format"] else -1
            elif 0 <= last_cube and t["index"] - last_cube <= 5:
                t["cubemap_face_of"] = last_cube
        self.vertex_buffers = []
        (n,) = unpack("<H", d, pos)
        pos += 2
        for _ in range(n):
            size = self.u32(pos)
            span(d, pos + 4, size, "vertex buffer")
            self.vertex_buffers.append((pos + 4, size))
            pos += 4 + size
        self.index_buffers = []
        (n,) = unpack("<H", d, pos)
        pos += 2
        for _ in range(n):
            size = self.u32(pos)
            span(d, pos + 4, size, "index buffer")
            self.index_buffers.append((pos + 4, size))
            pos += 4 + size
        self.payload_end = pos

    # -- geometry ------------------------------------------------------
    def mesh_layout(self, mesh):
        """Vertex layout of one mesh: ({attribute: (kind, offset)}, note).

        The material's explicit vertex flags must agree with the mesh stride.
        A note means the layout is unsupported; no position-only fallback."""
        mat = self.materials[mesh["material"]] if 0 <= mesh["material"] < len(self.materials) else None
        if mat is None:
            return {}, "no material paired with this mesh; geometry refused"
        if mat["vertex_stride"] != mesh["stride"]:
            if mat["vertex_format_flags"] & 0x10000000:
                return {}, (f"vertex layout unknown: material {mat['index']} format "
                            f"{mat['vertex_format_flags']:#x} implies {mat['vertex_stride']} bytes a vertex, "
                            f"the mesh has {mesh['stride']}, and the vertex holds no position")
            return {}, (
                f"vertex layout unknown: material {mat['index']} format {mat['vertex_format_flags']:#x} implies "
                f"{mat['vertex_stride']} bytes a vertex, the mesh has {mesh['stride']}; geometry refused")
        return {a: (k, o) for a, k, o in mat["vertex_format"]}, ""

    def mesh_problem(self, mesh):
        """Why a mesh cannot be read at all ('' when it can). Nothing is read past a buffer's end."""
        if not mesh["tri_count"] or not mesh["vertex_count"] or not mesh["stride"]:
            return "empty mesh record (no triangles, vertices or vertex size)"
        if mesh["vertex_count"] > 2000000 or mesh["tri_count"] > 4000000:
            return "Mesh exceeds the supported geometry budget"
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

        mesh["geometry_note"] explains unavailable geometry. Unknown layouts
        and invalid attribute/index data raise ValueError rather than guessing."""
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
        if note: raise ValueError(note)
        if "position" in fmt and stride < 12:
            mesh["geometry_note"] = f"vertex size {stride} is too small for a position"
            return None
        raw = d[v0:v0 + count * stride]

        def column(kind_offset, code):
            o = kind_offset[1]
            return [unpack(code, raw, b + o) for b in range(0, count * stride, stride)]

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
            pos = [unpack("<3f", d, p0 + i * 12) for i in range(count)]
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
            idx = unpack(f"<{n_idx}H", d, ib_off + mesh["index_offset"] * 2)
            for i in range(n_idx - 2):
                a, b_, c = idx[i], idx[i + 1], idx[i + 2]
                if a == b_ or b_ == c or a == c:
                    continue
                if a >= count or b_ >= count or c >= count:
                    bad_index += 1
                    continue
                tris.append((a, b_, c) if i % 2 == 0 else (b_, a, c))
        else:  # triangle list
            idx = unpack(f"<{mesh['tri_count'] * 3}H", d, ib_off + mesh["index_offset"] * 2)
            for i in range(0, len(idx), 3):
                if max(idx[i:i + 3]) >= count:
                    bad_index += 1
                    continue
                tris.append(tuple(idx[i:i + 3]))
        if bad_index: raise ValueError(f"{bad_index} triangles reference vertices outside the mesh")
        for values in (pos, nrm, uv, col):
            for row in values: finite(row, "mesh attributes")
        if note:
            mesh["geometry_note"] = note
        else:
            mesh.pop("geometry_note", None)
        return pos, nrm, uv, col, tris


def inspect(path):
    """Inventory explicit refusals as well as decoded meshes; no file writes."""
    nu = NU20(path)
    result = dict(version=nu.version, meshes=len(nu.meshes), models=len(nu.models),
                  bones=len(nu.bones), textures=len(nu.textures), decoded_meshes=0, issues=[])
    for mesh in nu.meshes:
        try:
            if nu.mesh_geometry(mesh):
                result['decoded_meshes'] += 1
            else:
                result['issues'].append({'mesh': mesh['index'], 'error': mesh['geometry_note']})
        except ValueError as error:
            result['issues'].append({'mesh': mesh['index'], 'error': str(error)})
    return result


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser(description='Inspect classic PC NU20 geometry; no native edits or complete character assembly')
    parser.add_argument('source')
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.source), indent=2))
    except (OSError, ValueError) as error:
        parser.error(str(error))
