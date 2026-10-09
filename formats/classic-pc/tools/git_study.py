"""Summarise the original games' puzzle-logic files (*.git: plain text, one per level area).

    python tools/git_study.py <extracted game folder> [more folders]     # e.g. extracted\\game extracted\\indy\\game

A .git file is the level designers' flow chart: FlowBox blocks, each holding gizmos (interactive things,
by Type and Name), Condition blocks or Action blocks, linked parent -> child. When a box is satisfied its
children are triggered. This prints, per game: how many of each gizmo type, their flags, every condition and
action kind with its commonest settings, and which gizmo types most often trigger which (the puzzle chains).
Study aid only: read-only on extracted data, output to the console.
"""
import collections
import glob
import os
import re
import sys


def blocks(text):
    """Yield (kind, body) for top-level 'Kind { ... }' blocks, handling one level of nesting."""
    i = 0
    for m in re.finditer(r"^([A-Za-z_]+)\s*\{", text, re.M):
        if m.start() < i:
            continue
        depth, j = 1, m.end()
        while depth and j < len(text):
            depth += text[j] == "{"
            depth -= text[j] == "}"
            j += 1
        i = j
        yield m.group(1), text[m.end():j - 1]


def inner(body, kind):
    out = []
    for m in re.finditer(kind + r"\s*\{", body):
        depth, j = 1, m.end()
        while depth and j < len(body):
            depth += body[j] == "{"
            depth -= body[j] == "}"
            j += 1
        out.append(body[m.end():j - 1])
    return out


def study(root):
    files = glob.glob(os.path.join(root, "levels", "**", "*.git"), recursive=True)
    gizmo, flags, cond, act, chain = (collections.Counter() for _ in range(5))
    cond_keys, act_keys = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for f in files:
        text = open(f, errors="replace").read()
        boxes = {}
        for kind, body in blocks(text):
            if kind != "FlowBox":
                continue
            box_id = int(re.search(r"BoxID\s+(-?\d+)", body).group(1))
            kinds = []
            for g in inner(body, "Gizmo"):
                t = re.search(r'Type\s+"([^"]+)"', g)
                t = t.group(1) if t else "?"
                gizmo[t] += 1
                kinds.append(t)
                for line in g.splitlines():
                    line = line.strip()
                    if line and not line.startswith(("Type", "Name")):
                        flags[(t, line.split()[0])] += 1
            for c in inner(body, "Condition"):
                lines = [ln.strip() for ln in c.splitlines() if ln.strip()]
                name = lines[0] if lines else "?"
                cond[name.split('"')[0].strip() if '"' in name else name] += 1
                kinds.append("Condition")
                for ln in lines:
                    cond_keys[ln.split()[0]][" ".join(ln.split()[1:])[:40]] += 1
            for a in inner(body, "Action"):
                lines = [ln.strip() for ln in a.splitlines() if ln.strip()]
                kinds.append("Action")
                for ln in lines:
                    act_keys[ln.split()[0]][" ".join(ln.split()[1:])[:40]] += 1
                act[lines[0][:50] if lines else "?"] += 1
            boxes[box_id] = (kinds, [int(x) for x in re.findall(r"Child\s+(-?\d+)", body)])
        for kinds, children in boxes.values():
            for ch in children:
                if ch in boxes:
                    for a in set(kinds) or {"(empty)"}:
                        for b in set(boxes[ch][0]) or {"(empty)"}:
                            chain[(a, b)] += 1
    print(f"== {root}: {len(files)} puzzle-logic files, {sum(gizmo.values())} gizmos")
    print(" gizmo types:", gizmo.most_common(45))
    print(" gizmo flags:", [(f"{t}.{k}", n) for (t, k), n in flags.most_common(30)])
    print(" condition fields:", {k: v.most_common(6) for k, v in list(cond_keys.items())[:14]})
    print(" action fields:", {k: v.most_common(6) for k, v in list(act_keys.items())[:14]})
    print(" commonest chains (what triggers what):", [(f"{a} -> {b}", n) for (a, b), n in chain.most_common(30)])


if __name__ == "__main__":
    for root in sys.argv[1:]:
        study(root)
