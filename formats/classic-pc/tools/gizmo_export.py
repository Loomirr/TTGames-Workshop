"""Export named objects of an NU20 scene as separate glTF files in their own local space (STAND-INS; git-ignored output).

    python tools/gizmo_export.py <file_pc.gsc> <export_dir> <out_dir> <object name> [<object name> ...]

<export_dir> must already hold textures/*.png from `nu20.py export` of the same file. Each object is written to
<out_dir>/<name>.gltf around its own pivot (the object's placement in the source file is NOT applied, because
in the shared "things" files the placements are only a layout sheet). Used for gizmos such as the lever.
Prints each object's size in metres so the pieces can be assembled.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from gltf_export import GltfBuilder  # noqa: E402
from nu20 import NU20  # noqa: E402


def main(argv):
    if not argv:
        print(__doc__)
        sys.exit(1)
    nu = NU20(argv[0])
    export_dir, out_dir, wanted = argv[1], argv[2], argv[3:]
    os.makedirs(out_dir, exist_ok=True)
    scene_json = os.path.join(export_dir, "scene.json")
    if os.path.exists(scene_json):
        for t in json.load(open(scene_json))["textures"]:
            if t.get("has_alpha"):
                nu.textures[t["index"]]["has_alpha"] = True
    report = []
    for name in wanted:
        obj = next((o for o in nu.special_objects if o["name"] == name and o["model"] >= 0), None)
        if obj is None:
            print("NOT FOUND:", name)
            continue
        b = GltfBuilder(nu, os.path.relpath(os.path.join(export_dir, "textures"), out_dir).replace("\\", "/"))
        b.tex_dir = os.path.join(export_dir, "textures")
        prims = [b.primitive(nu.meshes[mi]) for mi in nu.models[obj["model"]]["meshes"] if mi >= 0]
        if not b.add_mesh("SM_Giz_" + name, prims):
            print("EMPTY:", name)
            continue
        b.save(os.path.join(out_dir, name + ".gltf"))
        lo = [min(a["min"][k] for a in b.accessors if "min" in a and a["type"] == "VEC3") for k in range(3)]
        hi = [max(a["max"][k] for a in b.accessors if "max" in a and a["type"] == "VEC3") for k in range(3)]
        report.append({"name": name, "min": lo, "max": hi, "sheet_pos": obj["matrix"][12:15]})
        print(f"{name:14s} min {[round(v, 3) for v in lo]} max {[round(v, 3) for v in hi]} materials {len(b.materials)}")
    with open(os.path.join(out_dir, "gizmo_export.json"), "w") as f:
        json.dump({"source": os.path.basename(argv[0]), "convention": "glTF = (game x, game y, -game z), metres", "objects": report}, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
