"""Quick look at glTF models without Unreal: front, side and top line drawings of each file, side by side.

    python tools/gltf_views.py <out.png> <a.gltf> [<b.gltf> ...]

Axes are glTF's (Y up). Front = X across, Y up. Side = Z across, Y up. Top = X across, Z down.
One grid square is 10 cm. Used to work out how extracted gizmo pieces fit together.
"""
import json
import os
import struct
import sys

from PIL import Image, ImageDraw

SCALE, CELL = 600.0, 300  # pixels per metre, pixels per view


def load(path):
    g = json.load(open(path))
    data = open(os.path.join(os.path.dirname(path), g["buffers"][0]["uri"]), "rb").read()

    def acc(i):
        a = g["accessors"][i]
        v = g["bufferViews"][a["bufferView"]]
        off = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        n = {"VEC3": 3, "SCALAR": 1, "VEC2": 2, "VEC4": 4}[a["type"]]
        fmt = {5126: "f", 5123: "H", 5125: "I", 5121: "B"}[a["componentType"]]
        vals = struct.unpack_from("<" + fmt * (n * a["count"]), data, off)
        return [vals[k:k + n] for k in range(0, len(vals), n)]

    tris = []
    for mesh in g["meshes"]:
        for p in mesh["primitives"]:
            pos = acc(p["attributes"]["POSITION"])
            idx = [i[0] for i in acc(p["indices"])]
            tris += [(pos[idx[k]], pos[idx[k + 1]], pos[idx[k + 2]]) for k in range(0, len(idx) - 2, 3)]
    return tris


def main(argv):
    out, files = argv[0], argv[1:]
    img = Image.new("RGB", (CELL * 3, CELL * len(files)), "white")
    d = ImageDraw.Draw(img)
    views = ((0, 1, "front x/y"), (2, 1, "side z/y"), (0, 2, "top x/z"))
    for row, path in enumerate(files):
        tris = load(path)
        for col, (ax, ay, label) in enumerate(views):
            cx, cy = col * CELL + CELL // 2, row * CELL + CELL // 2
            for k in range(-4, 5):
                d.line([(cx + k * 0.1 * SCALE, row * CELL), (cx + k * 0.1 * SCALE, row * CELL + CELL)], fill=(225, 225, 225))
                d.line([(col * CELL, cy + k * 0.1 * SCALE), (col * CELL + CELL, cy + k * 0.1 * SCALE)], fill=(225, 225, 225))
            d.line([(cx - 8, cy), (cx + 8, cy)], fill="red")
            d.line([(cx, cy - 8), (cx, cy + 8)], fill="red")
            for t in tris:
                pts = [(cx + v[ax] * SCALE, cy - v[ay] * SCALE if ay == 1 else cy + v[ay] * SCALE) for v in t]
                d.line(pts + [pts[0]], fill=(40, 60, 120))
            d.text((col * CELL + 6, row * CELL + 4), f"{os.path.basename(path)[:-5]}  {label}", fill="black")
    img.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1:])
