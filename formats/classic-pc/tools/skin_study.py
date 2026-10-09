"""How does the original game rig a minifig? Reads a character model's skin weights (study tool).

    python tools/skin_study.py <character_pc.ghg> [out.json]

For every mesh: its size, where it sits, and which skeleton bones its vertices follow (share of total weight).
With out.json: also writes every vertex (position, bone names, weights) for the weight-transfer step.
Game space: metres, Y up.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nu20 import NU20  # noqa: E402


def skinned_vertices(nu, mesh):
    """Yield (position, [(bone index, weight), ...]) for each vertex of a mesh.

    Skinned character vertices (measured on batman_pc.ghg): the last 8 bytes of the vertex are
    3 weight bytes + 1 unused, then 3 palette-index bytes + 1 unused. The palette (8 signed bytes in the mesh
    record) turns a palette index into a skeleton bone index. Unskinned meshes have an empty palette."""
    d = nu.d
    stride = mesh["stride"]
    vb_off, _ = nu.vertex_buffers[mesh["vertex_buffer"]]
    v0 = vb_off + mesh["vertex_offset"] * stride
    palette = mesh["bones"]
    skinned = any(p >= 0 for p in palette)
    for i in range(mesh["vertex_count"]):
        b = v0 + i * stride
        pos = struct.unpack_from("<3f", d, b)
        pairs = []
        if skinned:
            w = d[b + stride - 8:b + stride - 5]
            idx = d[b + stride - 4:b + stride - 1]
            total = sum(w) or 1
            for j, weight in zip(idx, w):
                if weight and j < 8 and palette[j] >= 0:
                    pairs.append((palette[j], weight / total))
        yield pos, pairs, palette


def main(argv):
    nu = NU20(argv[0])
    names = [b["name"] for b in nu.bones]
    print("bones:", len(names))
    for b in nu.bones:
        print(f"  {b['index']:2d} {b['name']:16s} parent {b['parent']}")
    dump = []
    for mesh in nu.meshes:
        if not mesh["vertex_count"] or mesh["material"] < 0 or mesh["material"] >= len(nu.materials):
            continue
        mat = nu.materials[mesh["material"]]
        share, lo, hi, n = {}, [9e9] * 3, [-9e9] * 3, 0
        raw_idx = set()
        for pos, pairs, palette in skinned_vertices(nu, mesh):
            n += 1
            lo = [min(a, b) for a, b in zip(lo, pos)]
            hi = [max(a, b) for a, b in zip(hi, pos)]
            row = []
            for j, w in pairs:
                raw_idx.add(j)
                share[j] = share.get(j, 0.0) + w
                row.append((j, w))
            if row:
                dump.append({"mesh": mesh["index"], "pos": pos, "w": row})
        total = sum(share.values()) or 1.0
        print(f"mesh {mesh['index']:3d} mat {mesh['material']:3d} verts {n:5d} tris {mesh['tri_count']:5d} "
              f"min {[round(v, 3) for v in lo]} max {[round(v, 3) for v in hi]}")
        if share:
            print("      follows " + ", ".join(f"{names[j]} {v / total:.0%}" for j, v in sorted(share.items(), key=lambda kv: -kv[1])))
    if len(argv) > 1:
        json.dump({"bones": names, "vertices": dump}, open(argv[1], "w"))
        print("wrote", argv[1], len(dump), "vertices")


if __name__ == "__main__":
    main(sys.argv[1:])
