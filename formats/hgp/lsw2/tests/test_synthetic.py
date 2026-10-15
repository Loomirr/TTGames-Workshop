"""Asset-free tests: a small LEGO Star Wars II model and animation clip built here from the documented
layout (docs/FORMAT.md), then read, written, edited, extended and damaged. No game files needed.

    python tests/test_synthetic.py          (from the add-on folder; plain Python 3.10+, numpy optional)
"""
import math
import random
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import anim  # noqa: E402
import hgp   # noqa: E402

A = lambda x, n: (x + n - 1) // n * n
IDENT = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
CHILD_LOCAL = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0.1, 0, 1.0]


def tiny_dds():
    head = struct.pack('<4s31I', b'DDS ', 0x7C, 0x81007, 8, 8, 64, 0, 1, *([0] * 11),
                       0x20, 4, int.from_bytes(b'DXT5', 'little'), 0, 0, 0, 0, 0, 0x1000, 0, 0, 0, 0)
    return head + bytes(range(64))


def build_model():
    """Two bones, one attachment point, one layer with a rigid part (on bone 1) and a skinned part
    (two bones, with two shape slots, one empty), one material, one texture."""
    out = bytearray(0x98)
    put = lambda o, fmt, *v: struct.pack_into(fmt, out, o, *v)

    def at(n=16):
        out.extend(bytes(A(len(out), n) - len(out)))
        return len(out)

    mat_table = at(4)
    out += bytes(4)
    material = at(16)
    rec = bytearray(0xB4)
    struct.pack_into('<I', rec, 0x30, 0xFFFFFFFF)
    struct.pack_into('<3f', rec, 0x54, 1.0, 0.5, 0.25)
    struct.pack_into('<f', rec, 0x74, 1.0)
    struct.pack_into('<H', rec, 0x78, 1)                      # texture 0, counted from 1
    out += rec
    put(mat_table, '<I', material)
    names_at = at(16)
    names = b'root\0child\0defaultLayer\0tip\0'
    out += names
    joints = at(16)
    for i, (name_off, parent) in enumerate(((0, 255), (5, 0))):
        j = bytearray(0x60)
        struct.pack_into('<16f', j, 0, *IDENT)
        struct.pack_into('<I', j, 0x4C, names_at + name_off)
        j[0x50], j[0x51] = parent, 8 if parent == 255 else 33
        out += j
    local = at(16)
    out += struct.pack('<16f', *IDENT) + struct.pack('<16f', *CHILD_LOCAL)
    inverse = at(16)
    inv_child = list(CHILD_LOCAL)
    inv_child[13] = -0.1
    out += struct.pack('<16f', *IDENT) + struct.pack('<16f', *inv_child)
    bytes_a = at(16)
    point = at(16)
    p = bytearray(0x50)
    struct.pack_into('<16f', p, 0, *IDENT)
    struct.pack_into('<2I', p, 0x40, names_at + 24, 1)
    out += p
    layers = at(16)
    out += bytes(20)
    a_rec = at(4)
    out += bytes(8)
    rigid_array = at(4)
    out += bytes(8)
    d_array = at(4)
    out += bytes(8)
    # rigid part: a quad (4 vertices, strip 0 1 2 3) in buffer 0
    rigid_obj = at(16)
    out += bytes(hgp.OBJECT_SIZE)
    rigid_geo = at(4)
    g = bytearray(hgp.GEOMETRY_SIZE)
    struct.pack_into('<I', g, 0x2C, 0x8A80006C)
    struct.pack_into('<I', g, 0x44, 1)
    g[0x4C:0x68] = b'\xff' * 28
    struct.pack_into('<I', g, 0x9C, 6)
    out += g
    skinned_obj = at(16)
    out += bytes(hgp.OBJECT_SIZE)
    skinned_geo = at(4)
    out += g
    morph = hgp.encode_morph([(0, None), (1, [(0.0, 0.01, 0.0), (0.0, 0.0, 0.0), (0.02, 0.0, 0.0)])], 3)
    out += morph
    # patch the records
    rigid_pos = [(0.0, 0.0, 0.0), (0.1, 0.0, 0.0), (0.0, 0.1, 0.0), (0.1, 0.1, 0.0)]
    skin_pos = [(0.0, 0.0, 0.05), (0.1, 0.0, 0.05), (0.0, 0.2, 0.05)]
    for geo, kind, buf, count, n, start, palette in ((rigid_geo, hgp.RIGID, 0, 4, 4, 0, []),
                                                       (skinned_geo, hgp.SKINNED, 1, 3, 3, 4, [0, 1])):
        put(geo + 8, '<I', 0)
        put(geo + 0x10, '<3I', count, count, 0)
        put(geo + 0x38, '<I', hgp.MORPH_FLAG if kind == hgp.SKINNED else 0)
        put(geo + 0x48, '<I', buf)
        put(geo + 0x68, '<I', kind)
        put(geo + 0xA0, '<2H', n, n)
        put(geo + 0xAC, '<16H', len(palette), *(palette + [0] * (15 - len(palette))))
        put(geo + 0xD0, '<6I', 5, 0, 0, count, start, n - 2)
    put(rigid_obj + 12, '<I', rigid_geo)
    put(skinned_obj + 12, '<I', skinned_geo)
    put(rigid_obj + 0x14, '<13f', *hgp._bounds(rigid_pos))
    put(skinned_obj + 0x14, '<13f', *hgp._bounds(skin_pos))
    put(rigid_array + 4, '<I', rigid_obj)
    put(layers, '<5I', a_rec, rigid_array, skinned_obj, d_array, 0)
    tb = at(16)
    # texture block
    dds = tiny_dds()
    blob = dds + bytes(A(len(dds), 128) - len(dds))
    base = tb + 8
    start = A(base + 0x18 + 20, 128)
    vb = start + len(blob)
    out += struct.pack('<8I', base, vb, 1, vb - base - 0x14, 0x18, start - base, len(blob), 0)
    out += struct.pack('<5I', 8, 8, 1, 15, 0)
    out += bytes(start - len(out)) + blob
    # vertex block
    rigid_vb = b''.join(struct.pack('<3f3fI2f', *v, 0.0, 0.0, -1.0, 0xFF000000, v[0], v[1]) for v in rigid_pos)
    skin = [(1.0, 0.0, 0.0, -1.0, -1.0), (0.5, 0.5, 0.0, 1.0, -1.0), (0.0, 1.0, 0.0, 1.0, -1.0)]
    skin_vb = b''.join(struct.pack('<3f5f3fI2f', *v, *w, 0.0, 0.0, -1.0, 0xFF000000, 0.0, 0.0)
                       for v, w in zip(skin_pos, skin))
    indices = [0, 1, 2, 3, 0, 1, 2]
    raw = 2 * len(indices)
    hdr = A(0x30 + 24, 16)
    off1 = A(len(rigid_vb), 16)
    index_off = A(off1 + len(skin_vb), 16)
    block = bytearray(hdr + 16)
    struct.pack_into('<9I', block, 0, 2, 1, hdr + 16 + index_off + raw - 24, 0x30, hdr + 16, index_off, hdr,
                     index_off + hdr + 16, A(raw, 16))
    struct.pack_into('<6I', block, 0x30, len(rigid_vb), 0, 0, len(skin_vb), 1, off1)
    struct.pack_into('<I', block, hdr, raw)
    out += block + rigid_vb + bytes(off1 - len(rigid_vb)) + skin_vb
    out += bytes(index_off - off1 - len(skin_vb)) + struct.pack(f'<{len(indices)}H', *indices)
    out += bytes(A(raw, 16) - raw)
    put(0, '<I', len(out))
    out[4:8] = b'NU20'
    put(8, '<6I', 1, tb, 1, mat_table, 2, joints)
    put(32, '<3I', local, inverse, 0)
    put(44, '<8I', bytes_a, names_at, len(names), 0, bytes_a, 1, point, 1)
    put(76, '<2I', layers, 0)
    put(0x94, '<I', tb)
    return bytes(out)


def build_clip(nodes=2, frames=8, child_ty=0.1):
    """A clip: node 0 still; node 1 holds translation (0, child_ty, 0) (mirrored z = 0) and turns about x
    from 0 to 1 radian through one curve."""
    key_types = []
    for n in range(nodes):
        ty = 16 + 1 if n == 1 else 16
        key_types += [16, ty, 16, 6 if n == 1 else 16, 16, 16, 18, 18, 18]
    segments = (frames + 3) // 4 + 1
    group = 4
    head = 0x40
    sm = head
    cp = sm + 8
    const_scale = child_ty / 1000.0
    const_u16 = [0, 1000, round(1.0 / const_scale)]
    ktp = cp + 2 * len(const_u16)
    kp = A(ktp + 2 * len(key_types), 4)
    csf = kp + 4 * segments
    data = bytearray(csf + nodes)
    struct.pack_into('<4s5H', data, 0, b'4INA', nodes, frames, group, frames, 9)
    struct.pack_into('<ff', data, 28, 0.0, const_scale)
    struct.pack_into('<5I', data, 36, sm, cp, ktp, kp, csf)
    struct.pack_into('<ff', data, sm, 1.0 / 255.0, 0.0)          # value = anchor / 255
    struct.pack_into(f'<{len(const_u16)}H', data, cp, *const_u16)
    struct.pack_into(f'<{len(key_types)}H', data, ktp, *key_types)
    for s in range(segments):
        anchor = min(255, round(255 * s * 4 / max(1, frames - 1)))
        struct.pack_into('<I', data, kp + 4 * s, anchor | (63 << 8) | (63 << 14) | (63 << 20) | (63 << 26))
    return bytes(data)


failures = []


def check(label, ok, detail=''):
    print(f'{"ok    " if ok else "FAILED"} {label} {detail}')
    if not ok:
        failures.append(label)


def refused(fn):
    try:
        fn()
    except (hgp.HGPError, anim.AnimationError):
        return True
    except Exception as e:                        # any other exception is a crash, not a refusal
        print('   crashed with', type(e).__name__, e)
        return False
    return False


data = build_model()
m = hgp.Model(data)
check('reads two bones, a point, two parts, one material and texture',
      [b['name'] for b in m.bones] == ['root', 'child'] and m.points[0]['name'] == 'tip' and len(m.parts) == 2
      and len(m.materials) == 1 and len(m.textures) == 1 and m.layers[0]['name'] == 'defaultLayer')
check('child world and inverse', abs(m.bones[1]['world'][13] - 0.1) < 1e-6 and
      max(abs(a - b) for a, b in zip(hgp._mul(m.bones[1]['world'], m.bones[1]['inverse']), IDENT)) < 1e-6)
rigid, skinned = m.parts
check('rigid quad: two triangles on bone 1', rigid.bone == 1 and len(rigid.triangles()) == 2)
check('skinned weights by bone', skinned.weights[1] == [(0, 0.5), (1, 0.5)] and skinned.weights[2] == [(1, 1.0)])
check('shapes: one empty slot, one with offsets', skinned.shapes[0] == (0, None) and
      abs(skinned.shapes[1][1][2][0] - 0.02) < 1e-7)
check('unchanged write is byte-identical', m.write() == data)

# re-stripping and editing
m = hgp.Model(data)
for p in m.parts:
    p.set_triangles(p.triangles())
r = hgp.Model(m.write())
check('re-stripped parts read back with the same triangles',
      [sorted(p.triangles()) for p in r.parts] == [sorted(p.triangles()) for p in hgp.Model(data).parts])

# new bone, part, material, texture; grown morph block
m = hgp.Model(data)
bones = list(m.bones) + [dict(name='added', parent=1, local=CHILD_LOCAL)]
new = hgp.Part()
new.layer, new.slot, new.bone, new.kind = 0, 'rigid', 2, hgp.RIGID
new.template, new.buffer = m.template_for(hgp.RIGID), m.buffer_for(hgp.RIGID)
new.positions, new.normals = list(rigid.positions), list(rigid.normals)
new.uvs, new.colours, new.strip = list(rigid.uvs), list(rigid.colours), list(rigid.strip)
textures = list(m.textures) + [dict(width=8, height=8, levels=1, format=15, dds=tiny_dds())]
materials = [dict(x) for x in m.materials] + [dict(template=0, colour=(0.0, 1.0, 0.0), alpha=0.5, texture=1)]
new.material = 1
sk = m.parts[1]
sk.positions = sk.positions + [(0.05, 0.05, 0.05)]
sk.normals, sk.uvs, sk.colours = sk.normals + [(0, 0, -1.0)], sk.uvs + [(0, 0)], sk.colours + [0xFF000000]
sk.weights, sk.raw_skin = sk.weights + [[(1, 1.0)]], []
sk.shapes = [(0, None), (1, sk.shapes[1][1] + [(0.0, 0.0, 0.03)])]
sk.set_triangles(sk.triangles() + [(1, 3, 2)])
out = m.write(parts=list(m.parts) + [new], textures=textures, bones=bones, materials=materials)
r = hgp.Model(out)
check('new bone arrives with its world matrix', len(r.bones) == 3 and r.bones[2]['parent'] == 1 and
      abs(r.bones[2]['world'][13] - 0.2) < 1e-6)
got = [p for p in r.parts if p.bone == 2]
check('part on the new bone, new material and texture', len(got) == 1 and got[0].material == 1 and
      r.materials[1]['texture'] == 1 and abs(r.materials[1]['alpha'] - 0.5) < 1e-6 and len(r.textures) == 2)
grown = next(p for p in r.parts if p.kind == hgp.SKINNED)
check('grown morph block moved and arrived', grown.offset != m.parts[1].offset and len(grown.positions) == 4 and
      abs(grown.shapes[1][1][3][2] - 0.03) < 1e-7)

# refusals of edits the writer cannot represent
m = hgp.Model(data)


def too_many_bones():
    p = m.parts[1]
    p.palette = list(range(9))
    m.write()


check('a part over eight bones is refused', refused(too_many_bones))
m = hgp.Model(data)


def weight_off_palette():
    m.parts[1].weights[0] = [(5, 1.0)]
    m.parts[1].raw_skin = []
    m.write()


check('a weight naming a bone outside the part is refused', refused(weight_off_palette))
m = hgp.Model(data)
check('a new bone whose parent comes after it is refused',
      refused(lambda: m.write(bones=list(m.bones) + [dict(name='x', parent=5, local=IDENT)])))
check('a removed bone is refused', refused(lambda: m.write(bones=list(m.bones[:1]))))

# damaged files
check('not NU20 is refused', refused(lambda: hgp.Model(b'\0' * 0x200)))
bad = bytearray(data)
struct.pack_into('<I', bad, 0, len(data) + 4)
check('a wrong size field is refused', refused(lambda: hgp.Model(bytes(bad))))
crashes = 0
for cut in range(0x98, len(data), 37):
    if not refused(lambda: hgp.Model(data[:cut])):
        crashes += 1
check('every truncation is refused cleanly', crashes == 0, f'({crashes} crashed or were accepted)')
random.seed(7)
odd = 0
for _ in range(300):
    b = bytearray(data)
    for _k in range(4):
        b[random.randrange(8, len(b))] = random.randrange(256)
    try:
        hgp.Model(bytes(b))
    except hgp.HGPError:
        pass
    except Exception as e:
        odd += 1
        print('   random damage crashed:', type(e).__name__, e)
check('random byte damage never crashes (refused or read)', odd == 0)

# strips
random.seed(3)
ok = True
for _ in range(200):
    n = random.randrange(3, 30)
    tris = [tuple(random.sample(range(n), 3)) for _ in range(random.randrange(1, 40))]
    p = hgp.Part()
    p.set_triangles(tris)
    norm = lambda ts: sorted(t[t.index(min(t)):] + t[:t.index(min(t))] for t in ts)
    ok &= norm(p.triangles()) == norm(tris)
check('strip builder keeps every triangle and its winding (200 random lists)', ok)

# animation
clip_data = build_clip()
c = anim.Clip(clip_data, 'synthetic')
mid = c.pose(c.frames - 1)[1]
check('clip reads: node 1 turns to 1 radian about x, holds y 0.1', abs(mid[3] - 1.0) < 1e-6 and abs(mid[1] - 0.1) < 1e-6)
check('ownership proven for its own skeleton', anim.ownership(c, m.bones) >= anim.OWNED)
other = [dict(b) for b in m.bones]
other[1] = dict(other[1], local=[1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0.3, 0, 0, 1.0])
check('ownership refused for other proportions', anim.ownership(c, other) < anim.OWNED)
check('ownership refused for another bone count', anim.ownership(anim.Clip(build_clip(nodes=3)), m.bones) == 0.0)
loc = c.local_matrices(c.frames - 1, m.bones)[1]
check('pose matrix: bind rotation then mirrored x turn', abs(loc[5] - math.cos(1.0)) < 1e-6 and
      abs(loc[6] + math.sin(1.0)) < 1e-6 and abs(loc[13] - 0.1) < 1e-6)
check('damaged clip refused', refused(lambda: anim.Clip(clip_data[:40], 'cut')) and
      refused(lambda: anim.Clip(b'XXXX' + clip_data[4:], 'tag')))
check('declared clips and frame rates from a character file',
      anim.declared_clips('anim_start="Idle"\nfpsec=24\nanim_end\nanim_start="run"\nanim_end\n') == ['idle', 'run']
      and anim.frame_rates('anim_start="Idle"\nfpsec=24\nanim_end\n') == {'idle': 24.0})

try:
    import numpy as np
    import dxt
    ramp = np.zeros((16, 16, 4), np.uint8)
    ramp[..., 0] = np.arange(16)[None, :] * 16
    ramp[..., 3] = np.arange(16)[:, None] * 16
    back = dxt.decode_dxt5(dxt.encode_dxt5(ramp), 16, 16)
    err = np.abs(back.astype(int) - ramp.astype(int)).max()
    check('DXT5 encode/decode of a gradient', err <= 12, f'(largest error {err})')
except ImportError:
    print('skipped DXT5 check (numpy not installed)')

print(f'\n{"all passed" if not failures else "FAILED: " + ", ".join(failures)}')
sys.exit(1 if failures else 0)
