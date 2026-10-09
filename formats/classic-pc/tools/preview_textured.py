"""Texture/UV sanity check without a renderer: sample each vertex's diffuse colour
(texture at its UV, or the material colour) and draw a top-down point plot.

    python tools/preview_textured.py <file_pc.gsc> <export_dir> <out.png> [xmin xmax zmin zmax]

<export_dir> is the folder written by `nu20.py export` (needs textures/*.png).
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from nu20 import NU20  # noqa: E402


def main(argv):
    nu = NU20(argv[0])
    export_dir, out = argv[1], argv[2]
    tex_cache = {}

    def texture(i):
        if i not in tex_cache:
            p = os.path.join(export_dir, "textures", f"tex_{i:03d}.png")
            tex_cache[i] = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32) / 255 if os.path.exists(p) else None
        return tex_cache[i]

    object_models = {o["model"]: [] for o in nu.special_objects if o["model"] >= 0}
    for o in nu.special_objects:
        if o["model"] >= 0:
            object_models[o["model"]].append(o["matrix"])
    pts, cols = [], []
    for model in nu.models:
        matrices = object_models.get(model["index"], [None])
        for mi in model["meshes"]:
            if mi < 0:
                continue
            mesh = nu.meshes[mi]
            geo = nu.mesh_geometry(mesh)
            if not geo:
                continue
            pos, _nrm, uv, vcol, _tris = geo
            p = np.array(pos, dtype=np.float32)
            mat = nu.materials[mesh["material"]]
            c = np.tile(np.array(mat["colour"][:3], dtype=np.float32), (len(p), 1))
            tex = texture(mat["texture"]) if mat["texture"] >= 0 else None
            if tex is not None and uv:
                u = np.array(uv, dtype=np.float32)
                h, w = tex.shape[:2]
                x = (np.mod(u[:, 0], 1.0) * (w - 1)).astype(int)
                y = (np.mod(u[:, 1], 1.0) * (h - 1)).astype(int)
                c = tex[y, x]
            if vcol:  # baked lighting lives in vertex colours
                c = c * np.clip(np.array(vcol, dtype=np.float32)[:, :3] * 2.0, 0, 1.5)
            for m in matrices:
                q = p
                if m:
                    mm = np.array(m, dtype=np.float32).reshape(4, 4)
                    q = p @ mm[:3, :3] + mm[3, :3]
                pts.append(q)
                cols.append(c)
    pts = np.concatenate(pts)
    cols = np.clip(np.concatenate(cols), 0, 1)
    order = np.argsort(pts[:, 1])  # draw low points first so the top surface wins
    pts, cols = pts[order], cols[order]
    fig, ax = plt.subplots(figsize=(18, 13))
    ax.set_facecolor("#202020")
    ax.scatter(pts[:, 0], pts[:, 2], s=2.0, c=cols, linewidths=0)
    ax.set_aspect("equal")
    if len(argv) >= 7:
        ax.set_xlim(float(argv[3]), float(argv[4]))
        ax.set_ylim(float(argv[5]), float(argv[6]))
    ax.set_title(os.path.basename(argv[0]) + ": vertex colours sampled from textures (top-down, X right, Z up)")
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    print("points", len(pts), "wrote", out)


if __name__ == "__main__":
    main(sys.argv[1:])
