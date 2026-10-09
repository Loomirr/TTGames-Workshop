"""Export the skeleton of an original character model (.ghg) for use as a STAND-IN rig.

    python tools/skeleton_export.py <character_pc.ghg> <out_dir> [name]

Writes <name>.gltf/.bin: every bone as a joint in its bind pose, plus one tiny skinned triangle (Unreal
needs some skinned geometry to create a skeletal mesh), and <name>.bones.json with each bone's bind-pose
transform in Unreal component space, which the minifig auto-rig uses to attach parts.

Output derives from game files: it goes under build\\extracted\\ and Content/Extracted, never into git.
Game space is metres, Y up, left-handed. glTF = (x, y, -z). Unreal = (100x, -100z, 100y) cm.
"""
import json
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nu20 import NU20  # noqa: E402

FLIP = (2, 6, 8, 9, 14)  # elements that change sign when Z is mirrored (S * M * S)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    src, out_dir = argv[0], argv[1]
    name = argv[2] if len(argv) > 2 else "SK_TT_Minifig"
    nu = NU20(src)
    bones = nu.bones
    if not bones:
        print("no skeleton in", src)
        return 1
    os.makedirs(out_dir, exist_ok=True)

    # rest pose = the skinning bind pose (bind array); row-vector convention
    local = [np.array(b["bind_local"], dtype=np.float64).reshape(4, 4) for b in bones]
    world = []
    for i, b in enumerate(bones):
        world.append(local[i] if b["parent"] < 0 else local[i] @ world[b["parent"]])

    # --- glTF ---------------------------------------------------------------------------------------
    def mirrored(m):
        flat = m.reshape(16).copy()
        for k in FLIP:
            flat[k] = -flat[k]
        return flat

    nodes = []
    for i, b in enumerate(bones):
        node = {"name": b["name"], "matrix": [float(v) for v in mirrored(local[i])]}
        kids = [j for j, c in enumerate(bones) if c["parent"] == i]
        if kids:
            node["children"] = kids
        nodes.append(node)
    roots = [i for i, b in enumerate(bones) if b["parent"] < 0]
    ibm = b"".join(struct.pack("<16f", *mirrored(np.linalg.inv(w))) for w in world)

    hips = next((i for i, b in enumerate(bones) if b["name"].lower() == "hips"), 0)
    centre = mirrored(world[hips])[12:15]
    e = 0.0005  # a 1 mm triangle hidden inside the hips
    positions = [(centre[0], centre[1], centre[2]), (centre[0] + e, centre[1], centre[2]), (centre[0], centre[1] + e, centre[2])]
    pos = b"".join(struct.pack("<3f", *p) for p in positions)
    nrm = struct.pack("<3f", 0, 0, 1) * 3
    joints = struct.pack("<4H", hips, 0, 0, 0) * 3
    weights = struct.pack("<4f", 1, 0, 0, 0) * 3
    idx = struct.pack("<3H", 0, 1, 2)

    binary = bytearray()
    views, accessors = [], []

    def add(data, comp, count, typ, target=None, minmax=None):
        while len(binary) % 4:
            binary.append(0)
        view = {"buffer": 0, "byteOffset": len(binary), "byteLength": len(data)}
        if target:
            view["target"] = target
        views.append(view)
        binary.extend(data)
        acc = {"bufferView": len(views) - 1, "componentType": comp, "count": count, "type": typ}
        if minmax:
            acc["min"], acc["max"] = minmax
        accessors.append(acc)
        return len(accessors) - 1

    lo = [min(p[k] for p in positions) for k in range(3)]
    hi = [max(p[k] for p in positions) for k in range(3)]
    a_pos = add(pos, 5126, 3, "VEC3", 34962, (lo, hi))
    a_nrm = add(nrm, 5126, 3, "VEC3", 34962)
    a_jnt = add(joints, 5123, 3, "VEC4", 34962)
    a_wgt = add(weights, 5126, 3, "VEC4", 34962)
    a_idx = add(idx, 5123, 3, "SCALAR", 34963)
    a_ibm = add(ibm, 5126, len(bones), "MAT4")

    mesh_node = len(nodes)
    nodes.append({"name": name, "mesh": 0, "skin": 0})
    gltf = {"asset": {"version": "2.0", "generator": "legobatman-tools skeleton_export"}, "scene": 0,
            "scenes": [{"nodes": roots + [mesh_node]}], "nodes": nodes,
            "meshes": [{"name": name, "primitives": [{"attributes": {"POSITION": a_pos, "NORMAL": a_nrm, "JOINTS_0": a_jnt,
                                                                        "WEIGHTS_0": a_wgt}, "indices": a_idx, "mode": 4}]}],
            "skins": [{"name": name, "joints": list(range(len(bones))), "inverseBindMatrices": a_ibm, "skeleton": roots[0]}],
            "accessors": accessors, "bufferViews": views,
            "buffers": [{"uri": name + ".bin", "byteLength": len(binary)}]}
    with open(os.path.join(out_dir, name + ".bin"), "wb") as f:
        f.write(binary)
    with open(os.path.join(out_dir, name + ".gltf"), "w") as f:
        json.dump(gltf, f)

    # --- bind pose in Unreal component space (row-vector matrices, cm) ---------------------------------
    c = np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]])  # game axis -> Unreal axis (unit scale)
    table = []
    for i, b in enumerate(bones):
        rot = c.T @ world[i][:3, :3] @ c
        t = world[i][3, :3] @ c * 100.0
        table.append({"name": b["name"], "parent": b["parent"],
                      "x_axis": [float(v) for v in rot[0]], "y_axis": [float(v) for v in rot[1]],
                      "z_axis": [float(v) for v in rot[2]], "location_cm": [float(v) for v in t]})
    with open(os.path.join(out_dir, name + ".bones.json"), "w") as f:
        json.dump({"source": os.path.basename(src), "stand_in": True, "bones": table}, f, indent=1)
    print(f"{name}: {len(bones)} bones -> {out_dir}")
    for want in ("Hips", "Spine1", "Head", "RightArm", "RightHand", "LeftUpLeg", "RightToeBase"):
        row = next((r for r in table if r["name"] == want), None)
        if row:
            print(f"  {want:<13} Unreal cm {[round(v, 1) for v in row['location_cm']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
