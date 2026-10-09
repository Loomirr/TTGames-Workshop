"""Export the STAND-IN skeleton together with selected original animations as one glTF for Unreal.

    python tools/anim_export.py <character dir> <out_dir> [name] [--all] [--multi] [--strict] [--char <name>]

<character dir> is an extracted character folder (e.g. extracted\\game\\chars\\batman) holding <x>_pc.ghg,
<x>.txt and the animation files. Works on LEGO Batman, LEGO Indiana Jones (files '<anim>_pc.an3', lower case)
and LEGO Star Wars: The Complete Saga (files '<ANIM>.AN3', upper case): names are matched in any case.

Which file plays for which action is read from the character's .txt (measured on all three games):
    anim_start="<file name without _pc.an3>" / action="<what the game asks for>" / fpsec=<rate> / anim_end
plus every file named by anim_include="<file>.txt", which lies beside the character folders. The animation file
is looked for in the character's own folder first, then in the shared folder 'commonanims' beside it.

  default   the eleven roles of WANTED (A_TT_Idle, A_TT_Run, ...): the LEGO Batman file name if the folder has
            that file and the .txt names it (or names nothing for the role), otherwise the animation whose
            action is the role's name in lower case (idle, run, pulllever ...)
  --all     every animation the .txt names plus every animation file in the folder that the .txt does not
            name; clips are called by the animation's own name (lower case), no A_TT_ prefix
  --multi   files that hold several copies of this skeleton (two-character moves): every copy that fits is
            written as its own clip (<name>, <name>_set2, ...). Without it only the first copy is used.
  --strict  the old rule: skip every animation whose node count is not the skeleton's (or twice it).
            A --set recipe always works this way unless it says "loose_node_count": true.
  --char    another model and .txt of the same folder (a skin, e.g. --char hansolo in chars\\indianajones).
            If its .txt names no animations the folder's main .txt is used (a guess at what the game does).

Node counts: an animation moves node i -> bone i. A file with fewer nodes than the skeleton has bones leaves
the last bones at rest (LEGO Indiana Jones himself: 29 of 50, the rest is the whip); a file with more nodes
has extra things at the end (held props) that are left out. Both are noted in <name>.animations.json.
Playback rate comes from 'fpsec=' in the character's text file where given; otherwise DEFAULT_FPS (a placeholder).

Rotation convention (measured, GAME_STUDY.md): Euler angles in radians applied X, then Y, then Z, row-vector
matrices. Output goes under build\\extracted\\ and Content/Extracted (git-ignored): it derives from game files.
"""
import json
import os
import re
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from an3 import An3, euler_matrix  # noqa: E402
from nu20 import NU20  # noqa: E402

DEFAULT_FPS = 30.0  # placeholder for animations with no fpsec in the character file
FLIP = (2, 6, 8, 9, 14)
# Animation files are the mirror image (Z negated) of the model's skinning pose: measured, the animated
# translation z of every bone is exactly minus its bind z (foot -0.024 vs 0.024, toe 0.043 vs -0.043), and
# only the mirrored rotations keep the head upright and each arm rigid against the bind pose.
Z_MIRROR = np.diag([1.0, 1.0, -1.0, 1.0])
# game animation name -> role in the rebuild (the roles are what Core systems ask for)
WANTED = {"stand": "Idle", "run": "Run", "walk": "Walk", "tiptoe": "Tiptoe", "jump": "Jump", "fall": "Fall",
          "land": "Land", "build": "Build", "takehit": "TakeHit", "pullLever": "PullLever", "push": "Push"}


def mirrored(m):
    flat = np.array(m, dtype=np.float64).reshape(16).copy()
    for k in FLIP:
        flat[k] = -flat[k]
    return flat.reshape(4, 4)


def quat_from_matrix(r):
    """Column-vector rotation matrix -> (x, y, z, w)."""
    t = r[0, 0] + r[1, 1] + r[2, 2]
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        q = ((r[2, 1] - r[1, 2]) / s, (r[0, 2] - r[2, 0]) / s, (r[1, 0] - r[0, 1]) / s, 0.25 * s)
    elif r[0, 0] > r[1, 1] and r[0, 0] > r[2, 2]:
        s = np.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2]) * 2
        q = (0.25 * s, (r[0, 1] + r[1, 0]) / s, (r[0, 2] + r[2, 0]) / s, (r[2, 1] - r[1, 2]) / s)
    elif r[1, 1] > r[2, 2]:
        s = np.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2]) * 2
        q = ((r[0, 1] + r[1, 0]) / s, 0.25 * s, (r[1, 2] + r[2, 1]) / s, (r[0, 2] - r[2, 0]) / s)
    else:
        s = np.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1]) * 2
        q = ((r[0, 2] + r[2, 0]) / s, (r[1, 2] + r[2, 1]) / s, 0.25 * s, (r[1, 0] - r[0, 1]) / s)
    q = np.array(q)
    return q / np.linalg.norm(q)


def read_fps(txt_path, fps=None):
    """Playback rate per animation from a game text file: fpsec.
    'speed=' is NOT a playback rate (corrected 2026-10-06, GAME_STUDY.md 3aa): it is how fast the character moves
    forward while the animation plays, in metres per second, until 'frame_stop' (the recoil has speed=-0.435)."""
    fps = {} if fps is None else fps
    current, base, speed = None, None, 1.0

    def close():
        if current and base:
            fps[current] = base
    if os.path.exists(txt_path):
        for line in open(txt_path, errors="replace"):
            line = line.split(";")[0].strip()
            m = re.match(r'anim_start="?([^"]+)"?', line)
            if m:
                close()
                current, base, speed = m.group(1).lower(), None, 1.0
            m = re.match(r"fpsec=([\d.]+)", line)
            if m:
                base = float(m.group(1))
            m = re.match(r"speed=([\d.]+)", line)
            if m and float(m.group(1)) > 0:   # zero and negative speeds mean something else in the game; ignored
                speed = float(m.group(1))
        close()
    return fps


def listing(folder):
    """lower-case name -> real name for everything in a folder (TCS files are upper-case, the 2008 games' lower)."""
    try:
        return {n.lower(): n for n in os.listdir(folder)}
    except OSError:
        return {}


def find_anim(folder, name, files=None):
    """<name>_pc.an3 (LEGO Batman, Indiana Jones) or <name>.an3 (TCS) in a folder, in any case; None if absent."""
    files = listing(folder) if files is None else files
    hit = files.get(name.lower() + "_pc.an3") or files.get(name.lower() + ".an3")
    return os.path.join(folder, hit) if hit else None


def read_anims(txt_path, chars_root, blocks=None, seen=None):
    """The anim_start .. anim_end blocks of a character .txt in file order, with those of every anim_include
    (the included files lie in the folder that holds the character folders). Each block: name, action, fpsec."""
    blocks = [] if blocks is None else blocks
    seen = set() if seen is None else seen
    key = os.path.normcase(os.path.abspath(txt_path))
    if key in seen or not os.path.exists(txt_path):
        return blocks
    seen.add(key)
    current = None
    for line in open(txt_path, errors="replace"):
        line = re.split(r"//|;", line)[0].strip()
        m = re.match(r'anim_include\s*=\s*"?([^"]+)"?', line, re.I)
        if m:
            inc = listing(chars_root).get(m.group(1).strip().lower())
            if inc:
                read_anims(os.path.join(chars_root, inc), chars_root, blocks, seen)
            continue
        m = re.match(r'anim_start\s*=\s*"?([^"]+)"?', line, re.I)
        if m:
            current = {"name": m.group(1).strip(), "action": None, "fpsec": None, "from": os.path.basename(txt_path)}
            blocks.append(current)
            continue
        if re.match(r"anim_end", line, re.I):
            current = None
        elif current is not None:
            m = re.match(r'action\s*=\s*"?([^"]+)"?', line, re.I)
            if m and current["action"] is None:
                current["action"] = m.group(1).strip()
            m = re.match(r"fpsec\s*=\s*([\d.]+)", line, re.I)
            if m:
                current["fpsec"] = float(m.group(1))
    return blocks


def main(argv):
    global WANTED
    if not argv or argv[0] in ("-h", "--help") or (argv[0] != "--set" and len([a for a in argv if not a.startswith("--")]) < 2):
        print(__doc__)
        return 1
    root = os.getcwd()   # paths inside a set are relative to the current folder
    want_all = multi = strict = False
    info = {}            # animation name (lower case) -> (action, file) for the report
    hints = {}           # animation name (lower case) -> words added to its note
    own_jobs = None      # the character's own animations when they come from its .txt (None: the --set way)
    if argv[0] == "--set":   # --set <name>: a recipe from your own anim_sets.json beside this script (none is shipped)
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "anim_sets.json")) as f:
            spec = json.load(f)[argv[1]]
        name, WANTED = spec["name"], spec["wanted"]
        strict = not spec.get("loose_node_count", False)   # a set keeps the old rule unless it asks otherwise
        borrowed = spec.get("borrowed", [])
        char_dir, out_dir = os.path.join(root, spec["anim_dir"]), os.path.join(root, spec["out_dir"])
        model = os.path.join(root, spec["model"])
        char = os.path.splitext(os.path.basename(model))[0].replace("_pc", "")
        fps_table = {}
        for path in spec["rate_files"]:
            read_fps(os.path.join(root, path), fps_table)
    else:
        borrowed = []
        want_all, multi, strict = "--all" in argv, "--multi" in argv, "--strict" in argv
        skin = argv[argv.index("--char") + 1] if "--char" in argv and argv.index("--char") + 1 < len(argv) else None
        plain = [a for i, a in enumerate(argv) if not a.startswith("--") and not (i and argv[i - 1] == "--char")]
        char_dir, out_dir = plain[0], plain[1]
        name = plain[2] if len(plain) > 2 else "SK_TT_Minifig"
        folder_char = os.path.basename(os.path.normpath(os.path.abspath(char_dir)))
        char = skin or os.path.basename(os.path.normpath(char_dir))
        files = listing(char_dir)
        chars_root = os.path.dirname(os.path.normpath(os.path.abspath(char_dir)))
        if (char.lower() + "_pc.ghg") not in files:
            print("no model %s_pc.ghg in %s; models there: %s" % (char, char_dir, ", ".join(
                sorted(n[:-7] for n in files if n.endswith("_pc.ghg") and not n.endswith("_lr_pc.ghg"))) or "none"))
            return 1
        model = os.path.join(char_dir, files[char.lower() + "_pc.ghg"])
        blocks = read_anims(os.path.join(char_dir, files.get(char.lower() + ".txt", char + ".txt")), chars_root)
        if not blocks and char.lower() != folder_char.lower():
            # a skin whose own .txt names no animations: the folder's main character's are used (a guess)
            blocks = read_anims(os.path.join(char_dir, files.get(folder_char.lower() + ".txt", folder_char + ".txt")), chars_root)
        fps_table = {}
        for b in blocks:
            if b["fpsec"]:
                fps_table[b["name"].lower()] = b["fpsec"]
        common = os.path.join(chars_root, listing(chars_root).get("commonanims", "commonanims"))
        common_files = listing(common)

        def where(anim_name):
            return find_anim(char_dir, anim_name, files) or find_anim(common, anim_name, common_files)

        for b in blocks:    # a later block of the same name or action replaces an earlier one (includes come first)
            info[b["name"].lower()] = (b["action"], where(b["name"]))
        own_jobs = []
        if want_all:
            for low in info:
                own_jobs.append((low, low, info[low][1] or os.path.join(char_dir, low + ".an3"), None, None))
            for low in sorted(files):
                base = re.sub(r"(_pc)?\.an3$", "", low)
                if low.endswith(".an3") and base not in info:
                    info[base] = (None, os.path.join(char_dir, files[low]))
                    own_jobs.append((base, base, info[base][1], None, None))
        else:
            by_action = {}
            for b in blocks:
                if b["action"]:
                    by_action[b["action"].lower()] = b["name"]
            for g, r in WANTED.items():
                # The LEGO Batman file name is used when the folder has that file and the .txt names it (under any
                # action) or names no animation for the role. Otherwise the .txt's animation for the action is
                # used: other games' names (idle, buildit) and leftover files the .txt never mentions (measured:
                # 10 of 150 such roles in LEGO Indiana Jones, 7 of 232 in LEGO Batman, none in chars\batman or robin).
                # Where the two disagree and the file name wins, the note says what the .txt plays instead
                # (chars\batman: 'takehit' is the .txt's recoil, its takehit action plays 'takehit_high').
                by_txt = by_action.get(r.lower())
                by_txt_path = where(by_txt) if by_txt else None
                path = find_anim(char_dir, g, files)
                if path and (g.lower() in info or not by_txt_path):
                    if by_txt_path and by_txt.lower() != g.lower():
                        hints[g.lower()] = "; the .txt plays '%s' for action '%s' and uses this file for '%s'" % (
                            by_txt, r.lower(), info[g.lower()][0])
                elif by_txt_path:
                    g, path = by_txt, by_txt_path
                if path:
                    own_jobs.append((g, r, path, None, None))
    nu = NU20(model)
    bones = nu.bones
    if not bones:
        print("no skeleton in", model)
        return 1
    os.makedirs(out_dir, exist_ok=True)

    # rest pose = the skinning bind pose (the bind array, whose world transforms are exactly the inverses of
    # the inverse bind matrices). Animations are stored mirrored along Z relative to it; see Z_MIRROR.
    local = [np.array(b["bind_local"], dtype=np.float64).reshape(4, 4) for b in bones]
    world = []
    for i, b in enumerate(bones):
        world.append(local[i] if b["parent"] < 0 else local[i] @ world[b["parent"]])

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

    nodes = []
    for i, b in enumerate(bones):
        node = {"name": b["name"], "matrix": [float(v) for v in mirrored(local[i]).reshape(16)]}
        kids = [j for j, c in enumerate(bones) if c["parent"] == i]
        if kids:
            node["children"] = kids
        nodes.append(node)
    roots = [i for i, b in enumerate(bones) if b["parent"] < 0]
    a_ibm = add(b"".join(struct.pack("<16f", *mirrored(np.linalg.inv(w)).reshape(16)) for w in world), 5126, len(bones), "MAT4")

    mesh_json = spec.get("mesh_json") if argv[0] == "--set" else None
    if mesh_json:
        # a real body for this skeleton, made by another tool (tools/whip_chain.py: LEGO chain links on the whip's
        # bones): positions already in this file's space, one bone per corner
        with open(os.path.join(root, mesh_json)) as f:
            body = json.load(f)
        tri, count = body["positions"], len(body["positions"])
        lo = [min(p[k] for p in tri) for k in range(3)]
        hi = [max(p[k] for p in tri) for k in range(3)]
        a_pos = add(b"".join(struct.pack("<3f", *p) for p in tri), 5126, count, "VEC3", 34962, (lo, hi))
        a_nrm = add(b"".join(struct.pack("<3f", *p) for p in body["normals"]), 5126, count, "VEC3", 34962)
        a_jnt = add(b"".join(struct.pack("<4H", j, 0, 0, 0) for j in body["joints"]), 5123, count, "VEC4", 34962)
        a_wgt = add(struct.pack("<4f", 1, 0, 0, 0) * count, 5126, count, "VEC4", 34962)
        a_idx = add(struct.pack(f"<{count}I", *range(count)), 5125, count, "SCALAR", 34963)
    else:
        hips = next((i for i, b in enumerate(bones) if b["name"].lower() in ("hips", "uppertorso")), 0)
        c = mirrored(world[hips])[3, :3]
        e = 0.0005
        tri = [(c[0], c[1], c[2]), (c[0] + e, c[1], c[2]), (c[0], c[1] + e, c[2])]
        lo = [min(p[k] for p in tri) for k in range(3)]
        hi = [max(p[k] for p in tri) for k in range(3)]
        a_pos = add(b"".join(struct.pack("<3f", *p) for p in tri), 5126, 3, "VEC3", 34962, (lo, hi))
        a_nrm = add(struct.pack("<3f", 0, 0, 1) * 3, 5126, 3, "VEC3", 34962)
        a_jnt = add(struct.pack("<4H", hips, 0, 0, 0) * 3, 5123, 3, "VEC4", 34962)
        a_wgt = add(struct.pack("<4f", 1, 0, 0, 0) * 3, 5126, 3, "VEC4", 34962)
        a_idx = add(struct.pack("<3H", 0, 1, 2), 5123, 3, "SCALAR", 34963)

    # Jobs: this character's own animations, then "borrowed" ones: an animation made for ANOTHER character's
    # skeleton, carried over bone by bone by name (anim_sets.json "borrowed": file, role, from_model, optional
    # fps and "names" = this skeleton's bone name -> the other skeleton's). Bones the other skeleton does not
    # have (capes) stay in their rest pose. Only sound when the shared bones rest the same way in both
    # skeletons: measured for hero / goon / second-hero skeletons, all identical (GAME_STUDY.md 3j).
    jobs = own_jobs if own_jobs is not None else [(g, r, os.path.join(char_dir, g + "_pc.an3"), None, None) for g, r in WANTED.items()]
    # "joined": several of this character's OWN files played one after the other as one animation
    for item in (spec.get("joined", []) if argv[0] == "--set" else []):
        class Run:
            def __init__(self, names):
                self.parts = [An3(os.path.join(char_dir, q + "_pc.an3")) for q in names]
                self.nodes, self.frames = self.parts[0].nodes, sum(q.frames for q in self.parts)

            def pose(self, frame):
                for q in self.parts:
                    if frame < q.frames:
                        return q.pose(frame)
                    frame -= q.frames
                return self.parts[-1].pose(self.parts[-1].frames - 1)
        jobs.append(("+".join(item["files"]), item["role"], Run(item["files"]), None, item.get("fps")))
    for item in borrowed:
        src_names = [x["name"] for x in NU20(os.path.join(root, item["from_model"])).bones]
        rename = item.get("names", {})
        jmap = [src_names.index(rename.get(x["name"], x["name"])) if rename.get(x["name"], x["name"]) in src_names else None for x in bones]
        # "compose": a bone of ours whose lender has one bone more above it (LEGO Indiana Jones has an upper-arm
        # roll bone between arm and forearm): that bone's movement is folded into ours. "first_nodes": the file
        # animates only the lender's first N bones (Indy's files: 29 of 50; the rest are props), the others rest.
        # "files": several files played one after the other as ONE animation (Indy's whip_start + whip_crack).
        fold = {j: src_names.index(v) for j, x in enumerate(bones) for k, v in item.get("compose", {}).items() if x["name"] == k}
        if item.get("files"):
            class Joined:
                def __init__(self, paths):
                    self.parts = [An3(os.path.join(root, q)) for q in paths]
                    self.nodes, self.frames = self.parts[0].nodes, sum(q.frames for q in self.parts)

                def pose(self, frame):
                    for q in self.parts:
                        if frame < q.frames:
                            return q.pose(frame)
                        frame -= q.frames
                    return self.parts[-1].pose(self.parts[-1].frames - 1)
            source, label = Joined(item["files"]), item["role"].lower()
        else:
            source, label = os.path.join(root, item["file"]), os.path.basename(item["file"]).replace("_pc.an3", "")
        jobs.append((label, item["role"], source, (jmap, len(src_names), fold, bool(item.get("first_nodes"))), item.get("fps")))
    # "made": an animation of the project's own, for a gesture neither game has. It holds one frame of this
    # character's own animation ("base") and, for the bones listed, blends to the pose those bones have at one frame
    # of another animation ("pose_file" / "pose_frame", read by bone name from "pose_model"), holds it while one
    # bone rocks ("rock": bone, euler axis 0-2, radians, times per second), then blends back.
    class Made:
        def __init__(self, item):
            base = An3(os.path.join(char_dir, item["base"] + "_pc.an3")).pose(0)
            src_names = [x["name"] for x in NU20(os.path.join(root, item["pose_model"])).bones]
            lent = An3(os.path.join(root, item["pose_file"])).pose(item["pose_frame"])
            self.fps, self.length, self.blend, self.rock = item.get("fps", 30), item["seconds"], item.get("blend", 0.2), item.get("rock")
            self.frames, self.nodes = int(round(self.length * self.fps)) + 1, len(bones)
            self.base = [list(v[:6]) for v in base]
            self.up = [list(v[:6]) for v in base]
            for j, b in enumerate(bones):
                if b["name"] in item["bones"] and b["name"] in src_names:
                    self.up[j] = list(self.base[j][:3]) + list(lent[src_names.index(b["name"])][3:6])
            self.names = [b["name"] for b in bones]

        def pose(self, frame):
            t = frame / self.fps
            k = min(1.0, t / self.blend, max(0.0, (self.length - t) / self.blend))
            k = k * k * (3 - 2 * k)
            out = [[a + (b - a) * k for a, b in zip(self.base[j], self.up[j])] for j in range(self.nodes)]
            if self.rock:
                bone, axis, amount, per_second = self.rock
                out[self.names.index(bone)][3 + axis] += k * amount * np.sin(t * per_second * 2 * np.pi)
            return out

    for item in (spec.get("made", []) if argv[0] == "--set" else []):
        jobs.append((item["role"].lower(), item["role"], Made(item), None, item.get("fps", 30)))
    # "cut": a character's performance in one of the game's own cutscenes (tools/cu2.py): file, character (its number
    # in the cutscene), role, optional from_model + names when the cutscene character has another skeleton (as
    # "borrowed"), optional first / last (cutscene frames). Only the skeleton's movement: where the character stands
    # in the scene is its root track, which the cutscene layout uses (tools/cutscene_study.py).
    class Cut:
        def __init__(self, item):
            import cu2
            scene = cu2.Cutscene(os.path.join(root, item["file"]))
            self.block = scene.block(scene.characters[item["character"]]["skeleton_at"])
            self.first = max(0, item.get("first", self.block.start) - self.block.start)
            last = min(self.block.frames, item.get("last", self.block.start + self.block.frames) - self.block.start)
            self.frames, self.nodes = last - self.first, self.block.nodes

        def pose(self, frame):
            return self.block.pose(self.first + frame)

    for item in (spec.get("cut", []) if argv[0] == "--set" else []):
        borrow = None
        if item.get("from_model"):
            src_names = [x["name"] for x in NU20(os.path.join(root, item["from_model"])).bones]
            rename = item.get("names", {})
            borrow = ([src_names.index(rename.get(x["name"], x["name"])) if rename.get(x["name"], x["name"]) in src_names else None for x in bones], len(src_names))
        jobs.append((os.path.basename(item["file"]).replace("_pc.cu2", "") + " #%d" % item["character"], item["role"], Cut(item), borrow, 30))
    animations, report = [], []
    for game_name, role, path, borrow, fps_given in jobs:
        if isinstance(path, str) and not os.path.exists(path):
            if want_all:
                report.append((role, game_name, "skipped: no such animation file in the folder or in commonanims"))
            continue
        try:
            anim = An3(path) if isinstance(path, str) else path
        except Exception as ex:     # one unreadable file must not stop the others
            report.append((role, game_name, "skipped: unreadable (%s)" % ex))
            continue
        if anim.frames < 1 or anim.nodes < 1:
            report.append((role, game_name, "skipped: %d frames, %d nodes" % (anim.frames, anim.nodes)))
            continue
        copies = anim.nodes // len(bones) if borrow is None and anim.nodes % len(bones) == 0 else 1
        if copies > 1 and len(bones) < 4:
            copies = 1          # with a skeleton of one to three bones a whole multiple says nothing
        doubled = copies == 2 or (copies > 2 and not strict)
        sets, lead = [0], ""    # where this skeleton's nodes start in the file, one entry per clip to write
        if borrow is not None:
            if anim.nodes != borrow[1] and not (len(borrow) > 3 and borrow[3] and anim.nodes < borrow[1]):
                report.append((role, game_name, "skipped: %d nodes, the lending skeleton has %d bones" % (anim.nodes, borrow[1])))
                continue
        elif doubled:
            # Two-skeleton files (the heroes' fight1..6 have 90 nodes for a 45-bone skeleton). The first set
            # is used if its fixed bone offsets match this skeleton's; that it is the attacker is an assumption.
            # --multi: every set that fits becomes its own clip.
            first = anim.pose(0)
            body = [j for j, b in enumerate(bones) if j > 0 and "cloak" not in b["name"].lower()]   # cape bones move freely

            def misfit(start):
                return max((abs(abs(first[start + j][k]) - abs(local[j][3, k])) for j in body for k in range(3)), default=0.0)
            off = misfit(0)
            if off > 0.03 and not multi:   # was 0.01; fight3 to fight5 start 1.2 to 2.7 cm off the rest pose (a stance shift), 2026-10-05
                report.append((role, game_name, "skipped: %d nodes and the first set does not fit (%.3f m)" % (anim.nodes, off)))
                continue
            if multi:
                sets = [c * len(bones) for c in range(copies) if misfit(c * len(bones)) <= 0.03]
                if not sets:
                    report.append((role, game_name, "skipped: %d nodes = %d skeletons, none fits this one" % (anim.nodes, copies)))
                    continue
        elif anim.nodes != len(bones):
            if strict:
                report.append((role, game_name, "skipped: node count %d" % anim.nodes))
                continue
            lead = ("%d nodes: the first %d bones move, the other %d rest; " % (anim.nodes, anim.nodes, len(bones) - anim.nodes)
                    if anim.nodes < len(bones) else
                    "%d nodes: the first %d drive the skeleton, the other %d are left out; " % (anim.nodes, len(bones), anim.nodes - len(bones)))
            # how far the shared nodes' offsets at frame 0 are from this skeleton's own (cape bones aside): a large
            # number means the file was probably made for a skeleton with another bone order, so judge the clip by eye
            first = anim.pose(0)
            gap = max((abs(abs(first[j][k]) - abs(local[j][3, k])) for j, b in enumerate(bones)
                       if 0 < j < anim.nodes and "cloak" not in b["name"].lower() for k in range(3)), default=0.0)
            lead += "bone offsets at frame 0 within %.1f cm of the skeleton's; " % (gap * 100)
        fps = fps_given or fps_table.get(game_name.lower(), DEFAULT_FPS)
        times = [f / fps for f in range(anim.frames)]
        a_time = add(struct.pack(f"<{len(times)}f", *times), 5126, len(times), "SCALAR", None, ([0.0], [times[-1]]))
        poses = [anim.pose(f) for f in range(anim.frames)]
        for start in sets:
            samplers, channels = [], []
            for j in range(len(bones)):
                trans, rots = [], []
                prev = None
                src = start + j if borrow is None else borrow[0][j]
                if src is not None and src >= anim.nodes:
                    src = None                       # a bone the file does not animate ("first_nodes")
                above = borrow[2].get(j) if borrow is not None and len(borrow) > 2 else None
                for pose in poses:
                    if src is None:
                        mm = mirrored(local[j])      # a bone the lending skeleton lacks: rest pose
                    else:
                        def one(k):
                            tx, ty, tz, rx, ry, rz = pose[k][:6]
                            m = np.eye(4)
                            m[:3, :3] = np.array(euler_matrix(rx, ry, rz, "xyz"))
                            m[3, :3] = (tx, ty, tz)
                            return m
                        m = one(src) if above is None else one(src) @ one(above)
                        mm = mirrored(Z_MIRROR @ m @ Z_MIRROR)
                    trans.append(mm[3, :3])
                    q = quat_from_matrix(mm[:3, :3].T)  # row-vector matrix -> column-vector matrix
                    if prev is not None and np.dot(q, prev) < 0:
                        q = -q  # keep neighbouring keys in the same hemisphere
                    prev = q
                    rots.append(q)
                a_t = add(b"".join(struct.pack("<3f", *t) for t in trans), 5126, len(trans), "VEC3")
                a_r = add(b"".join(struct.pack("<4f", *q) for q in rots), 5126, len(rots), "VEC4")
                samplers += [{"input": a_time, "output": a_t, "interpolation": "LINEAR"},
                             {"input": a_time, "output": a_r, "interpolation": "LINEAR"}]
                channels += [{"sampler": len(samplers) - 2, "target": {"node": j, "path": "translation"}},
                             {"sampler": len(samplers) - 1, "target": {"node": j, "path": "rotation"}}]
            nth = start // len(bones) + 1
            clip = role + ("" if nth == 1 else "_set%d" % nth)
            animations.append({"name": clip if want_all else f"A_TT_{clip}", "samplers": samplers, "channels": channels})
            report.append((clip, game_name, lead + (("first of two skeletons; " if copies == 2 and not multi else "skeleton %d of %d in the file; " % (nth, copies)) if doubled else "")
                           + f"{anim.frames} frames at {fps:g} fps = {times[-1]:.2f} s"
                           + ("" if (fps_given or game_name.lower() in fps_table) else " (fps is a placeholder)")
                           + ("; borrowed from another skeleton by bone name" if borrow is not None else "")
                           + hints.get(game_name.lower(), "")))

    mesh_node = len(nodes)
    nodes.append({"name": name, "mesh": 0, "skin": 0})
    gltf = {"asset": {"version": "2.0", "generator": "legobatman-tools anim_export"}, "scene": 0,
            "scenes": [{"nodes": roots + [mesh_node]}], "nodes": nodes,
            "meshes": [{"name": name, "primitives": [{"attributes": {"POSITION": a_pos, "NORMAL": a_nrm, "JOINTS_0": a_jnt,
                                                                        "WEIGHTS_0": a_wgt}, "indices": a_idx, "mode": 4}]}],
            "skins": [{"name": name, "joints": list(range(len(bones))), "inverseBindMatrices": a_ibm, "skeleton": roots[0]}],
            "animations": animations, "accessors": accessors, "bufferViews": views,
            "buffers": [{"uri": name + ".bin", "byteLength": len(binary)}]}
    with open(os.path.join(out_dir, name + ".bin"), "wb") as f:
        f.write(binary)
    with open(os.path.join(out_dir, name + ".gltf"), "w") as f:
        json.dump(gltf, f)
    with open(os.path.join(out_dir, name + ".animations.json"), "w") as f:
        json.dump({"source_character": char, "stand_in": True,
                   "animations": [dict({"role": r, "game_name": g, "note": n}, **({} if not want_all else {
                       "action": info.get(g, (None, None))[0],
                       "file": os.path.relpath(info[g][1], chars_root) if info.get(g, (None, None))[1] else None}))
                                  for r, g, n in report]}, f, indent=1)
    print(f"{name}: {len(bones)} bones, {len(animations)} animations -> {out_dir}")
    for role, game_name, note in report:
        print(f"  {role:<10} from '{game_name}': {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
