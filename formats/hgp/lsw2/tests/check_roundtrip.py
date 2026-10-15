"""Checks for the LEGO Star Wars II model reader and writer (formats/hgp/lsw2/hgp.py).

    python formats/hgp/lsw2/tests/check_roundtrip.py <folder with .hgp files> [--edit]

For every .hgp under the folder: read it, write it back unchanged and compare byte for byte.
With --edit it also re-strips every part from its triangle list, writes, reads the result again and
compares what was decoded (vertices, triangles, weights, materials, bones), which exercises the paths
an exported model takes.
"""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hgp  # noqa: E402


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return min(len(a), len(b)) if len(a) != len(b) else None


def decoded(model):
    out = []
    for p in model.parts:
        tris = sorted(tuple(t[i:] + t[:i]) for t in p.triangles() for i in [t.index(min(t))])
        out.append((p.layer, p.slot, p.bone, p.material, p.kind, tuple(p.positions), tuple(p.normals),
                    tuple(p.uvs), tuple(p.colours), tuple(tuple(sorted(w)) for w in p.weights), tuple(tris)))
    return out, [(b['name'], b['parent'], b['local']) for b in model.bones], model.textures


def main(argv):
    root = Path(argv[1])
    edit = '--edit' in argv
    st = collections.Counter()
    for path in sorted(root.rglob('*.hgp')):
        data = path.read_bytes()
        try:
            m = hgp.Model(data)
        except hgp.HGPError as e:
            st['refused'] += 1
            print(f'refused  {path.relative_to(root)}: {e}')
            continue
        out = m.write()
        if out == data:
            st['identical'] += 1
        else:
            st['DIFFERENT'] += 1
            i = first_diff(out, data)
            print(f'DIFFERENT {path.relative_to(root)}: first at {i:#x} (sizes {len(out)} / {len(data)})')
        if edit:
            for p in m.parts:
                p.set_triangles(p.triangles())
            m2 = hgp.Model(m.write())
            if decoded(m2) == decoded(hgp.Model(data)):
                st['edit round trip same'] += 1
            else:
                st['EDIT ROUND TRIP DIFFERS'] += 1
                print(f'EDIT DIFFERS {path.relative_to(root)}')
    print(dict(st))
    return 0 if not (st['DIFFERENT'] or st['EDIT ROUND TRIP DIFFERS']) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
