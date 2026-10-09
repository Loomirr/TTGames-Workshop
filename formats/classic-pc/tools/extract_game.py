"""Extract every .DAT archive of a TT game install into one folder (read-only on the install).

    python tools/extract_game.py "<install folder>" <out_dir> [workers]

Runs one tools/ttdat.py process per archive, several at a time, and writes a log per archive plus a summary
to <out_dir>\\_extract_log\\. Later archives overwrite earlier ones where paths repeat (the game's own
patch order: GAME.DAT first, then GAME0, GAME1 ...). Output folders are git-ignored.
"""
import os
import re
import subprocess
import sys
import time

if len(sys.argv) < 3:
    print(__doc__)
    sys.exit(1)
install, out = sys.argv[1], sys.argv[2]
workers = int(sys.argv[3]) if len(sys.argv) > 3 else 6
tools = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(out, "_extract_log")
os.makedirs(log_dir, exist_ok=True)


def order(name):
    # GAME.DAT first, then GAME0, GAME1 ...; archives with other names (LEGO Indiana Jones: RAIDERS.DAT,
    # TEMPLE.DAT, CRUSADE.DAT) after those, alphabetically
    m = re.match(r"GAME(\d*)\.DAT", name.upper())
    if not m:
        return (1, 0, name.upper())
    return (0, -1 if not m.group(1) else int(m.group(1)), "")


archives = sorted((n for n in os.listdir(install) if n.upper().endswith(".DAT")), key=order)
running, done, start = [], [], time.time()
queue = list(archives)
while queue or running:
    while queue and len(running) < workers:
        name = queue.pop(0)
        log = open(os.path.join(log_dir, name + ".log"), "w")
        p = subprocess.Popen([sys.executable, os.path.join(tools, "ttdat.py"), "extract", os.path.join(install, name), out],
                             stdout=log, stderr=subprocess.STDOUT, cwd=tools)
        running.append((name, p, log))
    time.sleep(2)
    for item in list(running):
        name, p, log = item
        if p.poll() is not None:
            log.close()
            running.remove(item)
            last = open(os.path.join(log_dir, name + ".log")).read().strip().split("\n")[-1]
            done.append((name, p.returncode, last))
            print(f"[{time.time() - start:6.0f} s] {name}: {last}", flush=True)
with open(os.path.join(log_dir, "summary.txt"), "w") as f:
    for name, code, last in done:
        f.write(f"{name}\texit {code}\t{last}\n")
print("ALL DONE in %.0f s" % (time.time() - start), flush=True)
