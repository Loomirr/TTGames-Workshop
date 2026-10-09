"""Quick sanity preview of an exported scene.obj: top-down (X/Z) and side (X/Y) vertex plots.

    python tools/preview_obj.py <scene.obj> <out.png> [scene.json]

If scene.json is given, special-object positions are overlaid with their names.
"""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main(argv):
    obj, out = argv[0], argv[1]
    verts = []
    with open(obj) as f:
        for line in f:
            if line.startswith("v "):
                _, x, y, z = line.split()
                verts.append((float(x), float(y), float(z)))
    v = np.array(verts)
    print("vertices", len(v), "min", v.min(axis=0).round(2), "max", v.max(axis=0).round(2))
    fig, axes = plt.subplots(2, 1, figsize=(16, 14), gridspec_kw={"height_ratios": [3, 1]})
    axes[0].scatter(v[:, 0], v[:, 2], s=0.05, c=v[:, 1], cmap="viridis")
    axes[0].set_title("top-down: X right, Z up, colour = height")
    axes[0].set_aspect("equal")
    axes[1].scatter(v[:, 0], v[:, 1], s=0.05, c="k")
    axes[1].set_title("side: X right, Y up")
    axes[1].set_aspect("equal")
    if len(argv) > 2:
        meta = json.load(open(argv[2]))
        for o in meta["special_objects"]:
            x, y, z = o["matrix"][12:15]
            axes[0].plot(x, z, "r.", ms=4)
            axes[0].annotate(o["name"], (x, z), fontsize=5, color="red")
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1:])
