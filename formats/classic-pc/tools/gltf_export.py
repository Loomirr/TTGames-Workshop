"""Export an NU20 scene to glTF 2.0 for Unreal import.

    python tools/gltf_export.py <file_pc.gsc> <export_dir>

<export_dir> must already hold textures/*.png from `nu20.py export`. Writes <export_dir>/gltf/:
    static_NN.gltf/.bin   static world, split into buckets of at most MAX_MATERIALS materials
    objects.gltf/.bin     one mesh per special object, baked to world space (name = object name + index)
    export.json           list of meshes written and the coordinate convention

Coordinates: the game is left-handed, Y up, metres. glTF is right-handed, Y up, metres, so Z is negated
and triangle winding flipped. Vertex colours (the game's baked lighting) go out as COLOR_0.

Nothing is left out silently: every mesh that could not be written, or was written without something, is
listed with its reason on the screen and under "notes" in export.json; when no glTF file is written at all the
reason is printed.
"""
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
from nu20 import NU20  # noqa: E402

MAX_MATERIALS = 48


class GltfBuilder:
    def __init__(self, nu, tex_rel):
        self.nu = nu
        self.tex_rel = tex_rel
        self.bin = bytearray()
        self.views, self.accessors, self.meshes, self.nodes = [], [], [], []
        self.materials, self.textures, self.images = [], [], []
        self.mat_map, self.img_map = {}, {}
        self.tex_dir = None     # folder holding tex_NNN.png (callers set it); None = write no texture links
        self.notes = []         # (mesh index, what was left out and why)

    def _view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        v = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target:
            v["target"] = target
        self.bin += data
        self.views.append(v)
        return len(self.views) - 1

    def _accessor(self, data, comp, count, typ, target=None, minmax=None, normalized=False):
        a = {"bufferView": self._view(data, target), "componentType": comp, "count": count, "type": typ}
        if minmax:
            a["min"], a["max"] = minmax
        if normalized:
            a["normalized"] = True
        self.accessors.append(a)
        return len(self.accessors) - 1

    def material(self, index):
        if index in self.mat_map:
            return self.mat_map[index]
        m = self.nu.materials[index]
        pbr = {"baseColorFactor": [m["colour"][0], m["colour"][1], m["colour"][2], 1.0],
               "metallicFactor": 0.0, "roughnessFactor": 0.6}
        out = {"name": f"M_{index:03d}", "pbrMetallicRoughness": pbr, "doubleSided": True}
        t = m["texture"]
        if t >= 0 and self.tex_dir and os.path.exists(os.path.join(self.tex_dir, f"tex_{t:03d}.png")):
            if t not in self.img_map:
                self.images.append({"uri": f"{self.tex_rel}/tex_{t:03d}.png", "name": f"T_{t:03d}"})
                self.textures.append({"source": len(self.images) - 1})
                self.img_map[t] = len(self.textures) - 1
            pbr["baseColorTexture"] = {"index": self.img_map[t]}
            pbr["baseColorFactor"] = [1.0, 1.0, 1.0, 1.0]
            if t < len(self.nu.textures) and self.nu.textures[t].get("has_alpha"):
                out["alphaMode"] = "MASK"
                out["alphaCutoff"] = 0.5
        self.materials.append(out)
        self.mat_map[index] = len(self.materials) - 1
        return self.mat_map[index]

    def primitive(self, mesh, matrix=None, material=None):
        """One glTF primitive for a mesh, or None (the reason is added to self.notes).

        material: the material index to use instead of the mesh's own (a mesh drawn by several models can
        have a different material in each)."""
        def note(text):
            if (mesh["index"], text) not in self.notes:
                self.notes.append((mesh["index"], text))

        try:
            geo = self.nu.mesh_geometry(mesh)
        except (struct.error, IndexError) as ex:
            note(f"not written: reading it failed ({ex})")
            return None
        if not geo:
            note("not written: " + mesh.get("geometry_note", "no geometry"))
            return None
        pos, nrm, uv, col, tris = geo
        if mesh.get("geometry_note"):
            note(mesh["geometry_note"])
        if not tris:
            note("not written: no triangle left (every strip entry is degenerate)")
            return None
        if any(not math.isfinite(c) for p in pos for c in p):
            note("not written: a position is not a finite number")
            return None
        if uv and any(not math.isfinite(c) for t in uv for c in t):
            note("texture coordinates left out: one is not a finite number")
            uv = []
        if matrix:
            m = matrix
            pos = [(x * m[0] + y * m[4] + z * m[8] + m[12], x * m[1] + y * m[5] + z * m[9] + m[13],
                    x * m[2] + y * m[6] + z * m[10] + m[14]) for x, y, z in pos]
            nrm = [(x * m[0] + y * m[4] + z * m[8], x * m[1] + y * m[5] + z * m[9],
                    x * m[2] + y * m[6] + z * m[10]) for x, y, z in nrm]
        pos = [(x, y, -z) for x, y, z in pos]
        n = len(pos)
        attrs = {}
        lo = [min(p[i] for p in pos) for i in range(3)]
        hi = [max(p[i] for p in pos) for i in range(3)]
        attrs["POSITION"] = self._accessor(b"".join(struct.pack("<3f", *p) for p in pos), 5126, n, "VEC3", 34962, (lo, hi))
        if len(nrm) == n:
            fixed, no_normal = [], 0
            for x, y, z in nrm:
                z = -z
                length = (x * x + y * y + z * z) ** 0.5
                if length > 1e-6 and math.isfinite(length):
                    fixed.append((x / length, y / length, z / length))
                else:
                    fixed.append((0.0, 1.0, 0.0))  # glTF wants unit normals; the file's own is zero here
                    no_normal += 1
            if no_normal:
                note(f"{no_normal} of {n} vertices have a zero normal in the file: written as straight up")
            attrs["NORMAL"] = self._accessor(b"".join(struct.pack("<3f", *v) for v in fixed), 5126, n, "VEC3", 34962)
        if len(uv) == n:
            attrs["TEXCOORD_0"] = self._accessor(b"".join(struct.pack("<2f", *t) for t in uv), 5126, n, "VEC2", 34962)
        if len(col) == n:
            data = b"".join(bytes(min(255, max(0, int(c * 255 + 0.5))) for c in v) for v in col)
            attrs["COLOR_0"] = self._accessor(data, 5121, n, "VEC4", 34962, normalized=True)
        flat = []
        for a, b, c in tris:  # flip winding because Z was mirrored
            flat += (a, c, b)
        idx = self._accessor(struct.pack(f"<{len(flat)}H", *flat), 5123, len(flat), "SCALAR", 34963)
        prim = {"attributes": attrs, "indices": idx, "mode": 4}
        if material is None:
            material = mesh["material"]
        if 0 <= material < len(self.nu.materials):
            prim["material"] = self.material(material)
        return prim

    def add_mesh(self, name, prims):
        prims = [p for p in prims if p]
        if not prims:
            return False
        self.meshes.append({"name": name, "primitives": prims})
        self.nodes.append({"name": name, "mesh": len(self.meshes) - 1})
        return True

    def save(self, path):
        gltf = {"asset": {"version": "2.0", "generator": "legobatman-tools"},
                "scene": 0, "scenes": [{"nodes": list(range(len(self.nodes)))}],
                "nodes": self.nodes, "meshes": self.meshes, "materials": self.materials,
                "textures": self.textures, "images": self.images, "accessors": self.accessors,
                "bufferViews": self.views,
                "buffers": [{"uri": os.path.basename(path).replace(".gltf", ".bin"), "byteLength": len(self.bin)}]}
        for key in ("textures", "images", "materials"):
            if not gltf[key]:
                del gltf[key]
        with open(path.replace(".gltf", ".bin"), "wb") as f:
            f.write(self.bin)
        with open(path, "w") as f:
            json.dump(gltf, f)


def model_prims(b, nu, model, matrix=None):
    """Primitives of one model, each mesh with the material this model gives it."""
    prims = []
    commands = getattr(nu, "commands", [])
    for mi, mat, cid in zip(model["meshes"], model["materials"], model["ids"]):
        if mi < 0:
            # in the three games every such entry is a 0x8F command: another kind of draw (a 16-byte record
            # of a count and a start), which this reader does not decode
            kind = f"{commands[cid][0]:#x}" if 0 <= cid < len(commands) else "out of range"
            b.notes.append((-1, f"model {model['index']} entry left out: display command {cid} is of kind "
                                f"{kind}, not a mesh draw (not decoded)"))
            continue
        prims.append(b.primitive(nu.meshes[mi], matrix, material=mat))
    return prims


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    try:
        nu = NU20(argv[0])
    except (ValueError, struct.error, IndexError) as ex:
        print(f"nothing written: {argv[0]} could not be read: {ex}")
        return 1
    export_dir = argv[1]
    out_dir = os.path.join(export_dir, "gltf")
    os.makedirs(out_dir, exist_ok=True)
    tex_dir = os.path.join(export_dir, "textures")
    if not os.path.isdir(tex_dir):
        print(f"note: {tex_dir} does not exist (run nu20.py export first): materials are written without textures")
    # has_alpha was computed during nu20 export; reuse it from scene.json when present
    scene_json = os.path.join(export_dir, "scene.json")
    if os.path.exists(scene_json):
        for t in json.load(open(scene_json))["textures"]:
            if t.get("has_alpha") and t["index"] < len(nu.textures):
                nu.textures[t["index"]]["has_alpha"] = True

    notes = []

    def builder():
        b = GltfBuilder(nu, "../textures")
        b.tex_dir = tex_dir
        b.notes = notes
        return b

    written = []
    object_models = {o["model"] for o in nu.special_objects if o["model"] >= 0}

    # static world: one glTF mesh per bucket, primitives merged per material would be ideal;
    # here each source mesh is a primitive and Unreal merges sections by material on import.
    static_models = [m for m in nu.models if m["index"] not in object_models]
    bucket, bucket_mats, n_bucket = [], set(), 0

    def flush():
        nonlocal bucket, bucket_mats, n_bucket
        if not bucket:
            return
        b = builder()
        name = f"static_{n_bucket:02d}"
        prims = []
        for model in bucket:
            prims += model_prims(b, nu, model)
        if b.add_mesh(f"SM_{name}", prims):
            b.save(os.path.join(out_dir, name + ".gltf"))
            written.append({"file": name + ".gltf", "mesh": f"SM_{name}", "kind": "static", "materials": len(b.materials)})
        n_bucket += 1
        bucket, bucket_mats = [], set()

    for model in static_models:
        mats = {mat for mi, mat in zip(model["meshes"], model["materials"]) if mi >= 0}
        if bucket and len(bucket_mats | mats) > MAX_MATERIALS:
            flush()
        bucket.append(model)
        bucket_mats |= mats
    flush()

    # special objects, baked to world space, one mesh each
    b = builder()
    for o in nu.special_objects:
        if o["model"] < 0:
            continue
        name = f"SM_obj_{o['index']:03d}_{o['name']}".replace(" ", "_")
        prims = model_prims(b, nu, nu.models[o["model"]], o["matrix"])
        if b.add_mesh(name, prims):
            written.append({"file": "objects.gltf", "mesh": name, "kind": "object", "object": o["name"],
                            "game_pos": o["matrix"][12:15]})
        else:
            notes.append((-1, f"object {o['index']} '{o['name']}' (model {o['model']}) has no mesh that could be written"))
    if b.meshes:
        b.save(os.path.join(out_dir, "objects.gltf"))

    drawn = {mi for model in nu.models for mi in model["meshes"] if mi >= 0}
    undrawn = [m["index"] for m in nu.meshes if m["vertex_count"] and m["index"] not in drawn]
    with open(os.path.join(out_dir, "export.json"), "w") as f:
        json.dump({"source": os.path.basename(argv[0]),
                   "convention": "glTF = (game x, game y, -game z), metres, winding flipped",
                   "meshes": written,
                   "notes": [{"mesh": mi, "note": text} for mi, text in notes],
                   "meshes_no_model_uses": undrawn}, f, indent=1)
    statics = [w for w in written if w["kind"] == "static"]
    print(f"static buckets: {len(statics)} (materials per bucket: {[w['materials'] for w in statics]})")
    print(f"object meshes: {sum(1 for w in written if w['kind'] == 'object')}")
    if undrawn:
        print(f"{len(undrawn)} meshes are used by no model of the file and are not written (listed in export.json)")
    if notes:
        kinds = {}
        for mi, text in notes:
            key = "".join("N" if c.isdigit() else c for c in text)
            kinds.setdefault(key, []).append((mi, text))
        print(f"{len(notes)} notes (all in export.json):")
        for key, items in sorted(kinds.items(), key=lambda kv: -len(kv[1])):
            mi, text = items[0]
            where = f"mesh {mi}: " if mi >= 0 else ""
            print(f"  {len(items)} x  e.g. {where}{text}")
    if not written:
        if getattr(nu, "payload_missing", False):
            why = "the file holds only the scene description, its vertex and index buffers are not in it"
        elif not nu.meshes:
            why = "the file has no meshes (it holds only materials, textures, a skeleton or object positions)"
        elif not nu.models:
            why = f"the file has {len(nu.meshes)} meshes but no model that draws them"
        elif not drawn:
            why = "no model of the file names a mesh draw"
        else:
            why = "none of the meshes could be written (see the notes above)"
        print(f"NO glTF written for {argv[0]}: {why}")
        return 2
    print("wrote", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
