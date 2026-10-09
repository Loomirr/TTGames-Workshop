"""Take a real LEGO level area apart so one of ours can be built on its skeleton (python tools/level_anatomy.py
<area folder under extracted/> <export folder with scene.json and gltf/> <out folder>).

Reads, from the game's own files (LEGO Batman / Indiana Jones formats):
    <area>.git   the puzzle logic: flow boxes (each holds gizmos and waits on its parents), grouped by the designers
                 into named puzzles ("Collapse" boxes). Written out as chains: what must happen before what.
    <area>.giz   the pickups (studs, minikits, red brick) with positions.
    <area>.txt   camera blocks, doors, limits.
    scene.json   every named object of the scene with its position (the gizmos' models).
    gltf/        the static geometry, for a plan of the floor.
Writes: anatomy.md (the puzzles as chains, counts, sizes), anatomy.json (the same as data), plan.png (the area from
above: geometry shaded by height, objects named, studs and minikits marked).
Coordinates are given the way our levels use them: centimetres, x = game x * 100, y = -game z * 100, z = game y * 100.
"""
import glob
import json
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style_study  # noqa: E402  (its glTF reader)


def read_git(path):
    """The .git text -> {id: box}. A box: kind (FlowBox / Collapse / ...), name, parents, children, gizmos, lines."""
    text = open(path, encoding="latin1").read().replace("\r", "")
    boxes, pos = {}, 0
    for m in re.finditer(r"^(\w+) \{\n(.*?)^\}", text, re.S | re.M):
        kind, body = m.group(1), m.group(2)
        bid = re.search(r"^\tBoxID (-?\d+)", body, re.M)
        if not bid:
            continue
        box = {"kind": kind, "id": int(bid.group(1)), "name": (re.search(r'^\tName "([^"]*)"', body, re.M) or [None, ""])[1],
               "parents": [int(x) for x in re.findall(r"^\tParent (-?\d+)", body, re.M)],
               "children": [int(x) for x in re.findall(r"^\tChild (-?\d+)", body, re.M)], "gizmos": [], "other": []}
        for g in re.finditer(r"^\tGizmo \{\n(.*?)^\t\}", body, re.S | re.M):
            lines = [l.strip() for l in g.group(1).split("\n") if l.strip()]
            gz = {"type": "", "name": "", "flags": []}
            for l in lines:
                if l.startswith("Type ") and '"' in l:
                    gz["type"] = l.split('"')[1]
                elif l.startswith("Name ") and '"' in l:
                    gz["name"] = l.split('"')[1]
                else:
                    gz["flags"].append(l)
            box["gizmos"].append(gz)
        stripped = re.sub(r"^\tGizmo \{\n.*?^\t\}\n", "", body, flags=re.S | re.M)
        for l in stripped.split("\n"):
            l = l.strip()
            if l and not re.match(r"(BoxID|Name|Parent|Child|x|y|Num_Gizmos) ", l) and l not in ("{", "}"):
                box["other"].append(l)
        boxes[box["id"]] = box
    return boxes


def describe(box):
    if box["gizmos"]:
        parts = []
        for g in box["gizmos"]:
            parts.append(f'{g["type"]} "{g["name"]}"' + (" [" + ", ".join(g["flags"]) + "]" if g["flags"] else ""))
        s = " + ".join(parts)
    else:
        s = f'({box["kind"]}) "{box["name"]}"'
    if box["other"]:
        s += "  {" + "; ".join(box["other"][:6]) + "}"
    return s


def chains(boxes):
    """Each designers' group (Collapse) -> its boxes, in the order things must happen (a box after its parents)."""
    groups = [b for b in boxes.values() if b["kind"] == "Collapse"]
    out, used = [], set()
    for g in sorted(groups, key=lambda b: -b["id"]):
        members = [boxes[c] for c in g["children"] if c in boxes]
        seen, order = set(), []

        def walk(b, depth):
            if b["id"] in seen:
                return
            seen.add(b["id"])
            order.append((depth, b))
            for c in b["children"]:
                if c in boxes and boxes[c]["kind"] != "Collapse":
                    walk(boxes[c], depth + 1)

        roots = [m for m in members if not any(p in boxes and boxes[p] in members for p in m["parents"])] or members
        for r in roots:
            walk(r, 0)
        used |= seen
        out.append((g["name"], order))
    rest = [b for b in boxes.values() if b["kind"] != "Collapse" and b["id"] not in used and (b["gizmos"] or b["other"])]
    return out, rest


def to_ours(p):
    return [round(p[0] * 100), round(-p[2] * 100), round(p[1] * 100)]


def main(area_dir, export_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    name = os.path.basename(os.path.normpath(area_dir))
    boxes = read_git(os.path.join(area_dir, name + ".git"))
    groups, rest = chains(boxes)
    scene = json.load(open(os.path.join(export_dir, "scene.json")))
    objects = {o["name"]: to_ours(o["matrix"][12:15]) for o in scene["special_objects"]}
    pick_path = os.path.join(out_dir, "pickups.json")
    os.system(f'"{sys.executable}" "{os.path.join(os.path.dirname(os.path.abspath(__file__)), "giz.py")}" pickups "{os.path.join(area_dir, name + ".giz")}" "{pick_path}" > NUL 2>&1')
    pickups = json.load(open(pick_path)) if os.path.exists(pick_path) else []
    pickups = pickups.get("pickups", pickups) if isinstance(pickups, dict) else pickups

    # ---- the floor plan, from the static geometry: a height map at 10 cm a pixel (the highest up-facing surface per cell)
    pts = []
    for f in sorted(glob.glob(os.path.join(export_dir, "gltf", "static_*.gltf"))):
        g, bins = style_study.load(f)
        for mesh in g["meshes"]:
            for prim in mesh["primitives"]:
                pos = style_study.accessor(g, bins, prim["attributes"]["POSITION"])
                idx = style_study.accessor(g, bins, prim["indices"]).astype(np.int64).reshape(-1, 3)
                a, b, c = pos[idx[:, 0]], pos[idx[:, 1]], pos[idx[:, 2]]
                n = np.cross(b - a, c - a)
                area = np.linalg.norm(n, axis=1)
                up = (np.abs(n[:, 1]) > 0.7 * np.maximum(area, 1e-9)) & (area > 0.02)
                for k in range(0, 4):                       # sample each walkable-facing triangle at a few points
                    w = np.random.default_rng(k).dirichlet((1, 1, 1), size=int(up.sum()))
                    pts.append(a[up] * w[:, :1] + b[up] * w[:, 1:2] + c[up] * w[:, 2:3])
    pts = np.concatenate(pts)                               # glTF: (game x, game y, -game z), metres
    X, Y, Z = pts[:, 0] * 100, pts[:, 2] * 100, pts[:, 1] * 100          # ours: x, y (= -game z = glTF z), z up
    cell = 10.0
    x0, x1, y0, y1 = np.percentile(X, 0.5), np.percentile(X, 99.5), np.percentile(Y, 0.5), np.percentile(Y, 99.5)
    W, H = int((x1 - x0) / cell) + 1, int((y1 - y0) / cell) + 1
    hm = np.full((H, W), np.nan)
    ix, iy = ((X - x0) / cell).astype(int), ((Y - y0) / cell).astype(int)
    ok = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
    # the floor is the LOWEST up-facing surface that people could stand on in a cell; take a low percentile to skip pits
    order = np.argsort(Z[ok])[::-1]
    hm[iy[ok][order], ix[ok][order]] = Z[ok][order]
    zs = hm[~np.isnan(hm)]
    zlo, zhi = np.percentile(zs, 2), np.percentile(zs, 98)
    scale = 3
    img = Image.new("RGB", (W * scale, H * scale), (12, 12, 16))
    shade = np.clip((hm - zlo) / max(zhi - zlo, 1), 0, 1)
    rgb = np.zeros((H, W, 3), np.uint8)
    m = ~np.isnan(hm)
    rgb[m] = np.stack([60 + 150 * shade[m], 70 + 120 * shade[m], 110 - 40 * shade[m]], 1).astype(np.uint8)
    img.paste(Image.fromarray(rgb).resize((W * scale, H * scale), Image.NEAREST))
    d = ImageDraw.Draw(img)

    def px(p):
        return (p[0] - x0) / cell * scale, (p[1] - y0) / cell * scale

    for p in pickups:
        loc = to_ours([p["x"], p["y"], p["z"]]) if "x" in p else to_ours(p.get("position", [0, 0, 0]))
        u, v = px(loc)
        t = p.get("type", "?")
        col = {"s": (200, 200, 200), "g": (255, 210, 40), "b": (80, 140, 255), "p": (200, 80, 255), "m": (255, 60, 60), "r": (255, 0, 0)}.get(t, (255, 255, 255))
        r = 6 if t in ("m", "r") else 2
        d.ellipse((u - r, v - r, u + r, v + r), fill=col)
    gz_names = {g["name"]: g["type"] for b in boxes.values() for g in b["gizmos"]}
    for nm, loc in objects.items():
        u, v = px(loc)
        if 0 <= u < W * scale and 0 <= v < H * scale:
            d.rectangle((u - 2, v - 2, u + 2, v + 2), outline=(0, 255, 160) if nm in gz_names else (150, 150, 150))
            if nm in gz_names:
                d.text((u + 4, v - 5), nm, fill=(0, 255, 160))
    img.save(os.path.join(out_dir, "plan.png"))

    # ---- the write-up
    types = {}
    for b in boxes.values():
        for g in b["gizmos"]:
            types[g["type"]] = types.get(g["type"], 0) + 1
    floor_cells = int(m.sum())
    lines = [f"# Anatomy of `{name}` (from the game's own files; python tools/level_anatomy.py)", "",
             f"- Extent of the geometry seen from above: {round((x1 - x0) / 100, 1)} m by {round((y1 - y0) / 100, 1)} m; heights of standable surfaces {round(zlo)} to {round(zhi)} cm.",
             f"- Standable surface seen from above: about {round(floor_cells * cell * cell / 10000)} square metres.",
             f"- Puzzle logic: {len(boxes)} boxes; gizmos in it by kind: " + ", ".join(f"{k} {v}" for k, v in sorted(types.items(), key=lambda kv: -kv[1])),
             f"- Pickups placed: {len(pickups)} (" + ", ".join(f"{t} {sum(1 for p in pickups if p.get('type') == t)}" for t in sorted({p.get('type', '?') for p in pickups})) + ")",
             f"- Named objects in the scene: {len(objects)}", "", "## The puzzles, as the designers grouped them (a line indented under another waits for it)", ""]
    for gname, order in groups:
        lines.append(f"### {gname}")
        for depth, b in order:
            where = ""
            for g in b["gizmos"]:
                if g["name"] in objects:
                    where = f"   @ {objects[g['name']]}"
                    break
            lines.append("    " * depth + "- " + describe(b) + where)
        lines.append("")
    lines.append("### Not in any group")
    for b in rest:
        lines.append("- " + describe(b))
    open(os.path.join(out_dir, "anatomy.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    json.dump({"extent_cm": [float(x0), float(x1), float(y0), float(y1)], "heights_cm": [float(zlo), float(zhi)], "objects": objects, "pickups": pickups,
               "groups": [{"name": gname, "boxes": [{"depth": dpt, "id": b["id"], "name": b["name"], "gizmos": b["gizmos"], "other": b["other"], "parents": b["parents"]} for dpt, b in order]}
                          for gname, order in groups]}, open(os.path.join(out_dir, "anatomy.json"), "w"), indent=1)
    print("\n".join(lines[:9]))
    print("written:", out_dir)


if __name__ == "__main__":
    main(*sys.argv[1:4])
