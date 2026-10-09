"""Measure the LOOK of a level's geometry and textures, so an original level and ours can be put side by side in numbers.

    python tools/style_study.py original <export folder with gltf/ and textures/> <out.json> [textures to leave out]

What it measures (everything is weighted by surface area, in square metres, so one big wall counts for more than a bolt):
    triangles, area, triangles per square metre
    per material: share of the area; textured or flat colour; the texture's size; texel density (pixels per metre)
    baked lighting: the vertex colours' brightness and tint (the originals light their levels this way)
    per texture: size, mean colour, brightness, saturation, contrast (spread of brightness), fine detail (mean
    difference between neighbouring pixels), and whether it is a normal map (pink)
"""
import colorsys
import glob
import json
import os
import re
import struct
import sys

import numpy as np
from PIL import Image

COMP = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def load(path):
    if path.endswith(".glb"):
        raw = open(path, "rb").read()
        n = struct.unpack_from("<I", raw, 12)[0]
        g = json.loads(raw[20:20 + n])
        bins = [raw[20 + n + 8:]]
    else:
        g = json.load(open(path))
        bins = [open(os.path.join(os.path.dirname(path), b["uri"]), "rb").read() for b in g["buffers"]]
    return g, bins


def accessor(g, bins, i):
    a = g["accessors"][i]
    v = g["bufferViews"][a["bufferView"]]
    w = WIDTH[a["type"]]
    dt = np.dtype("<" + COMP[a["componentType"]])
    start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = v.get("byteStride") or dt.itemsize * w
    buf = bins[v["buffer"]]
    if stride == dt.itemsize * w:
        out = np.frombuffer(buf, dt, a["count"] * w, start).reshape(a["count"], w)
    else:
        out = np.stack([np.frombuffer(buf, dt, w, start + k * stride) for k in range(a["count"])])
    out = out.astype(np.float64)
    if a.get("normalized"):
        out /= {"B": 255.0, "H": 65535.0, "b": 127.0, "h": 32767.0}[COMP[a["componentType"]]]
    return out


def texture_stats(path):
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im, dtype=np.float64) / 255.0
    rgb = a[..., :3]
    mean = rgb.reshape(-1, 3).mean(0)
    lum = rgb @ np.array([0.299, 0.587, 0.114])
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    detail = (np.abs(np.diff(lum, axis=0)).mean() + np.abs(np.diff(lum, axis=1)).mean()) / 2
    return {"size": list(im.size), "mean": [round(float(x), 3) for x in mean], "brightness": round(float(lum.mean()), 3),
            "contrast": round(float(lum.std()), 3), "saturation": round(float(sat.mean()), 3), "detail": round(float(detail), 4),
            "normal_map": bool(mean[2] > 0.75 and mean[0] > 0.4 and abs(mean[0] - mean[1]) < 0.25 and mean[1] < mean[2] - 0.15),
            "alpha": round(float(a[..., 3].mean()), 3)}


def study(files, tex_of, tint_of, uv_scale=1.0, scale_of=None):
    """tex_of(g, material index, file) -> texture path or None; tint_of(...) -> rgb factor. Returns the summary."""
    mats, tex_cache = {}, {}
    total_tris, total_area = 0, 0.0
    vc_lum, vc_rgb, vc_w = [], [], []
    for f in files:
        g, bins = load(f)
        for mesh in g["meshes"]:
            for prim in mesh["primitives"]:
                at = prim["attributes"]
                pos = accessor(g, bins, at["POSITION"])
                idx = accessor(g, bins, prim["indices"]).astype(np.int64).reshape(-1, 3) if "indices" in prim else np.arange(len(pos)).reshape(-1, 3)
                p0, p1, p2 = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
                area = np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1) / 2
                keep = area > 1e-9
                uv_area = None
                if "TEXCOORD_0" in at:
                    uv = accessor(g, bins, at["TEXCOORD_0"]) * (scale_of(g, prim.get("material", -1), f) if scale_of else uv_scale)
                    u0, u1, u2 = uv[idx[:, 0]], uv[idx[:, 1]], uv[idx[:, 2]]
                    uv_area = np.abs((u1[:, 0] - u0[:, 0]) * (u2[:, 1] - u0[:, 1]) - (u1[:, 1] - u0[:, 1]) * (u2[:, 0] - u0[:, 0])) / 2
                m = prim.get("material", -1)
                tex = tex_of(g, m, f)
                if tex and os.path.basename(tex) in SKIP:       # a painted backdrop: not part of the near, playable look
                    continue
                key = (g["materials"][m]["name"] if m >= 0 else "none", tex, tuple(round(x, 3) for x in tint_of(g, m, f)))
                rec = mats.setdefault(key, {"area": 0.0, "tris": 0, "density": [], "density_w": []})
                rec["area"] += float(area.sum())
                rec["tris"] += len(idx)
                total_tris += len(idx)
                total_area += float(area.sum())
                if tex and tex not in tex_cache:
                    tex_cache[tex] = texture_stats(tex)
                if tex and uv_area is not None:
                    w, h = tex_cache[tex]["size"]
                    d = np.sqrt(uv_area[keep] * w * h / area[keep])            # pixels per metre
                    rec["density"].append(d)
                    rec["density_w"].append(area[keep])
                if "COLOR_0" in at:
                    col = accessor(g, bins, at["COLOR_0"])[:, :3]
                    if col.max() > 1.5:
                        col = col / 255.0
                    tri = (col[idx[:, 0]] + col[idx[:, 1]] + col[idx[:, 2]]) / 3
                    vc_rgb.append(tri[keep])
                    vc_lum.append(tri[keep] @ np.array([0.299, 0.587, 0.114]))
                    vc_w.append(area[keep])
    out = {"triangles": total_tris, "area_m2": round(total_area, 1), "triangles_per_m2": round(total_tris / max(total_area, 1e-9), 2), "materials": []}

    def wq(values, weights, q):
        order = np.argsort(values)
        c = np.cumsum(weights[order])
        return float(values[order][np.searchsorted(c, q * c[-1])])

    look_rgb, look_w, dens_all, dens_w_all, textured_area = [], [], [], [], 0.0
    for (name, tex, tint), rec in sorted(mats.items(), key=lambda kv: -kv[1]["area"]):
        item = {"material": name, "share": round(rec["area"] / total_area, 4), "area_m2": round(rec["area"], 1), "tris": rec["tris"],
                "texture": os.path.basename(tex) if tex else None, "tint": list(tint)}
        base = np.array(tint, dtype=np.float64)
        if tex:
            item["texture_stats"] = tex_cache[tex]
            base = base * np.array(tex_cache[tex]["mean"])
            textured_area += rec["area"]
            if rec["density"]:
                d, w = np.concatenate(rec["density"]), np.concatenate(rec["density_w"])
                item["pixels_per_metre"] = round(wq(d, w, 0.5), 1)
                dens_all.append(d)
                dens_w_all.append(w)
        item["surface_colour"] = [round(float(x), 3) for x in base]
        look_rgb.append(base)
        look_w.append(rec["area"])
        out["materials"].append(item)
    out["textured_share"] = round(textured_area / total_area, 3)
    if dens_all:
        d, w = np.concatenate(dens_all), np.concatenate(dens_w_all)
        out["pixels_per_metre"] = {"quarter": round(wq(d, w, 0.25), 1), "median": round(wq(d, w, 0.5), 1), "three_quarters": round(wq(d, w, 0.75), 1)}
    lw = np.array(look_w)
    mean = (np.array(look_rgb) * lw[:, None]).sum(0) / lw.sum()
    out["surface_colour_mean"] = [round(float(x), 3) for x in mean]
    out["surface_saturation"] = round(colorsys.rgb_to_hsv(*[min(1.0, float(x)) for x in mean])[1], 3)
    if vc_lum:
        lum, w, rgb = np.concatenate(vc_lum), np.concatenate(vc_w), np.concatenate(vc_rgb)
        out["baked_light"] = {"mean": round(float((lum * w).sum() / w.sum()), 3), "tenth": round(wq(lum, w, 0.1), 3), "median": round(wq(lum, w, 0.5), 3),
                              "ninetieth": round(wq(lum, w, 0.9), 3), "tint": [round(float(x), 3) for x in (rgb * w[:, None]).sum(0) / w.sum()]}
    out["textures_used"] = {os.path.basename(k): v for k, v in sorted(tex_cache.items())}
    return out


def original(folder):
    files = sorted(glob.glob(os.path.join(folder, "gltf", "*.gltf")))

    def tex_of(g, m, f):
        t = g["materials"][m].get("pbrMetallicRoughness", {}).get("baseColorTexture") if m >= 0 else None
        if not t:
            return None
        return os.path.normpath(os.path.join(os.path.dirname(f), g["images"][g["textures"][t["index"]]["source"]]["uri"]))

    def tint_of(g, m, f):
        return g["materials"][m].get("pbrMetallicRoughness", {}).get("baseColorFactor", [1, 1, 1, 1])[:3] if m >= 0 else [1, 1, 1]

    out = study(files, tex_of, tint_of)
    allt = [texture_stats(p) for p in sorted(glob.glob(os.path.join(folder, "textures", "*.png")))]
    sizes = {}
    for t in allt:
        sizes["%dx%d" % tuple(t["size"])] = sizes.get("%dx%d" % tuple(t["size"]), 0) + 1
    out["all_textures"] = {"count": len(allt), "normal_maps": sum(t["normal_map"] for t in allt), "sizes": dict(sorted(sizes.items(), key=lambda kv: -kv[1]))}
    return out


SKIP = set()        # texture file names left out (argument 4, comma separated): the painted skyline walls
UV_METRES = 1.0


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    SKIP.update(sys.argv[4].split(",") if len(sys.argv) > 4 else [])
    result = original(sys.argv[2])
    with open(sys.argv[3], "w") as fh:
        json.dump(result, fh, indent=1)
    brief = {k: v for k, v in result.items() if k not in ("materials", "textures_used")}
    print(json.dumps(brief, indent=1))
    for item in result["materials"][:14]:
        print("  %5.1f%%  %-22s %-26s %s  %s" % (item["share"] * 100, item["material"], item["texture"], item.get("pixels_per_metre", "-"), item["surface_colour"]))
