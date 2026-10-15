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


def check_features(data):
    """Add a bone, a rigid part on it (a new object), a texture and a material; read back and check."""
    import copy
    m = hgp.Model(data)
    rigid = next((p for p in m.parts if p.slot == 'rigid'), None)
    source = rigid or m.parts[0]
    parent = rigid.bone if rigid else 0
    local = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0.0, 0.05, 0.0, 1.0]
    bones = list(m.bones) + [dict(name='added_bone', parent=parent, local=local)]
    new = copy.copy(source)
    new.offset, new.slot, new.bone, new.kind = None, 'rigid', len(m.bones), hgp.RIGID
    new.template, new.buffer = m.template_for(hgp.RIGID), m.buffer_for(hgp.RIGID)
    new.palette, new.weights, new.raw_skin, new.morph, new.shapes = [], [], [], None, None
    new.positions, new.normals = list(source.positions), list(source.normals)
    new.uvs, new.colours, new.strip = list(source.uvs), list(source.colours), list(source.strip)
    textures = list(m.textures) + [dict(width=8, height=8, levels=1, format=15, dds=_tiny_dds())]
    materials = [dict(mt) for mt in m.materials]
    materials[0]['colour'] = (1.0, 0.0, 0.0)
    materials.append(dict(template=0, colour=(0.0, 0.5, 1.0), alpha=0.75, texture=len(textures) - 1, linked=None))
    new.material = len(materials) - 1
    out = m.write(parts=list(m.parts) + [new], textures=textures, bones=bones, materials=materials)
    r = hgp.Model(out)
    if len(r.bones) != len(m.bones) + 1 or r.bones[-1]['name'] != 'added_bone' or r.bones[-1]['parent'] != parent:
        return 'bone did not arrive'
    w = hgp._mul(local, m.bones[parent]['world'])
    if max(abs(a - b) for a, b in zip(w, r.bones[-1]['world'])) > 1e-5:
        return 'bone world matrix wrong'
    ident = hgp._mul(r.bones[-1]['world'], r.bones[-1]['inverse'])
    if max(abs(a - (1.0 if i % 5 == 0 else 0.0)) for i, a in enumerate(ident)) > 1e-4:
        return 'bone inverse wrong'
    if [b['name'] for b in r.bones[:-1]] != [b['name'] for b in m.bones]:
        return 'original bones changed'
    got = [p for p in r.parts if p.bone == len(m.bones)]
    if len(got) != 1 or got[0].positions != new.positions or got[0].material != len(materials) - 1:
        return 'part on the new bone did not arrive'
    mt = r.materials[-1]
    if mt['texture'] != len(textures) - 1 or abs(mt['alpha'] - 0.75) > 1e-6 or r.materials[0]['colour'] != (1.0, 0.0, 0.0):
        return 'materials did not arrive'
    if r.textures[-1]['dds'][:len(textures[-1]['dds'])] != textures[-1]['dds']:
        return 'texture did not arrive'
    obj = next(o for o in r.objects if o['bone'] == len(m.bones))
    import struct
    if list(struct.unpack_from('<13f', r.data, obj['offset'] + 0x14)) != hgp._bounds(new.positions):
        return 'new object bounds wrong'
    others = [(p.positions, p.strip, p.material) for p in r.parts if p.bone != len(m.bones)]
    if others != [(p.positions, p.strip, p.material) for p in m.parts]:
        return 'other parts changed'
    # shapes: a part with facial shapes gains a vertex and one shape changes; the record has to move
    m = hgp.Model(data)
    face = next((p for p in m.parts if p.shapes and any(d for _, d in p.shapes)), None)
    if face is not None:
        face.positions = face.positions + [face.positions[0]]
        face.normals = face.normals + [face.normals[0]]
        face.uvs, face.colours = face.uvs + [face.uvs[0]], face.colours + [face.colours[0]]
        if face.kind == hgp.SKINNED:
            face.weights = face.weights + [face.weights[0]]
            face.raw_skin = []
        k = next(i for i, (_, d) in enumerate(face.shapes) if d)
        face.shapes = [(sid, None if d is None else d + [(0.0, 0.0, 0.0)]) for sid, d in face.shapes]
        sid, d = face.shapes[k]
        face.shapes[k] = (sid, [(x + 0.001, y, z) for x, y, z in d])
        index = m.parts.index(face)
        r = hgp.Model(m.write())
        got = r.parts[index]
        if got.offset == face.offset or len(got.positions) != len(face.positions):
            return 'part with a grown morph block did not move'
        same = all((a[0] == b[0]) and (a[1] is None) == (b[1] is None) and
                   (a[1] is None or max(abs(x - y) for u, v in zip(a[1], b[1]) for x, y in zip(u, v)) < 1e-6)
                   for a, b in zip(got.shapes, face.shapes))
        if not same or len(got.shapes) != len(face.shapes):
            return 'shapes did not arrive'
    return None


def _tiny_dds():
    import struct
    head = struct.pack('<4s31I', b'DDS ', 0x7C, 0x81007, 8, 8, 64, 0, 1, *([0] * 11),
                       0x20, 4, int.from_bytes(b'DXT5', 'little'), 0, 0, 0, 0, 0, 0x1000, 0, 0, 0, 0)
    return head + bytes(64)


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
        if '--features' in argv:
            problem = check_features(data)
            st['features ok' if problem is None else 'FEATURES FAILED'] += 1
            if problem:
                print(f'FEATURES {path.relative_to(root)}: {problem}')
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
