"""Asset-free regressions for original LSW2 PC HGP and AN3."""
from synthetic_fixture import *

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

# New-joint validation is strict and never silently remaps native identities.
def write_new_bones(*extra):
    model = hgp.Model(data)
    return model.write(bones=list(model.bones) + list(extra))


for bad_name in ('', 'root', 'child', 'tip\0hidden', 'caf\u00e9', 17):
    check(f'invalid new bone name {bad_name!r} is refused',
          refused(lambda name=bad_name: write_new_bones(dict(name=name, parent=1, local=IDENT))))
check('new bone names cannot collide with each other', refused(lambda: write_new_bones(
      dict(name='new', parent=1, local=IDENT), dict(name='new', parent=2, local=IDENT))))
for bad_parent in (-2, 2, 999, 1.0, True, None, '1'):
    check(f'invalid new parent {bad_parent!r} is refused',
          refused(lambda parent=bad_parent: write_new_bones(dict(name='new', parent=parent, local=IDENT))))
for label, matrix in (
        ('short', IDENT[:15]), ('missing', None), ('not numbers', ['x'] * 16),
        ('NaN', [float('nan')] + IDENT[1:]), ('infinite', [float('inf')] + IDENT[1:]),
        ('float32 overflow', [1e100] + IDENT[1:]), ('singular', [0.0] + IDENT[1:]),
        ('perspective', IDENT[:3] + [0.1] + IDENT[4:]),
        ('float32 singular', [1e-50] + IDENT[1:])):
    check(f'invalid {label} bone matrix is refused', refused(lambda value=matrix: write_new_bones(
          dict(name='new', parent=1, local=value))))


def changed_original_bind(in_place):
    model = hgp.Model(data)
    bones = model.bones if in_place else [dict(b) for b in model.bones]
    bones[1]['local'] = list(bones[1]['local'])
    bones[1]['local'][13] += 0.1
    return model.write(bones=bones)


check('modified original bind cannot be silently ignored', refused(lambda: changed_original_bind(False)))
check('in-place modified original bind is also refused', refused(lambda: changed_original_bind(True)))
# Nested added bones and a separate root exercise both legal parent cases. A stale
# derived world is deliberately supplied: the local matrix must define the file.
first = dict(name='added_first', parent=1, local=list(CHILD_LOCAL), world=list(IDENT))
second = dict(name='added_second', parent=2, local=list(CHILD_LOCAL), world=list(IDENT))
separate = dict(name='added_root', parent=-1, local=list(IDENT))
result = hgp.Model(write_new_bones(first, second, separate))
check('new child chains recompute world and inverse from local transforms',
      abs(result.bones[3]['world'][13] - 0.3) < 1e-6 and
      max(abs(a-b) for a,b in zip(hgp._mul(result.bones[3]['world'], result.bones[3]['inverse']), IDENT)) < 1e-6)
check('new root arrives and source joint bytes stay intact', result.bones[4]['parent'] == -1 and all(
      result.data[result.header[7]+i*0x60:result.header[7]+(i+1)*0x60] ==
      hgp.Model(data).data[hgp.Model(data).header[7]+i*0x60:hgp.Model(data).header[7]+(i+1)*0x60]
      for i in range(2)))
check('validation does not mutate caller cached matrices', first['world'] == IDENT and second['world'] == IDENT)

# Appending directly to the parsed list must still copy the native tables using
# the source bone count rather than accidentally treating the addition as original.
direct = hgp.Model(data)
direct.bones.append(dict(name='direct_added', parent=1, local=IDENT))
check('direct append uses the immutable original joint count',
      len(hgp.Model(direct.write()).bones) == 3)
scaled = list(IDENT)
scaled[0], scaled[5], scaled[10] = 2.0, 3.0, 4.0
scaled_result = hgp.Model(write_new_bones(dict(name='scaled_added', parent=1, local=scaled)))
check('valid nonuniform bone scales are retained',
      scaled_result.bones[2]['local'][0:11:5] == (2.0, 3.0, 4.0))
large = list(IDENT)
large[0] = 1e30
check('finite local matrices whose hierarchy overflows float32 are refused', refused(lambda: write_new_bones(
      dict(name='large_parent', parent=1, local=large), dict(name='large_child', parent=2, local=large))))

# Geometry must be serializable finite float32 values, even through the pure writer.
def invalid_geometry(field, value):
    model = hgp.Model(data)
    part = model.parts[1]
    if field == 'shape':
        deltas = list(part.shapes[1][1])
        deltas[0] = value
        part.shapes = [part.shapes[0], (1, deltas)]
    elif field == 'weights':
        part.weights[0] = value
        part.raw_skin = []
    elif field == 'palette':
        part.palette = value
    elif field == 'strip':
        part.strip[0] = value
    else:
        getattr(part, field)[0] = value
    return model.write()


for field, size in (('positions', 3), ('normals', 3), ('uvs', 2), ('shape', 3)):
    for label, first in (('NaN', float('nan')), ('infinity', float('inf')), ('overflow', 1e100)):
        check(f'{field} {label} is refused', refused(lambda f=field, v=first, n=size:
              invalid_geometry(f, (v,) + (0.0,) * (n-1))))
    check(f'{field} incomplete components are refused', refused(lambda f=field, n=size:
          invalid_geometry(f, (0.0,) * (n-1))))
for label, slots in (('NaN', [(0, float('nan'))]), ('infinity', [(0, float('inf'))]),
                     ('overflow', [(0, 1e100)]), ('negative', [(0, -1.0), (1, 2.0)]),
                     ('unnormalized', [(0, 0.25)]), ('not a pair', [(0,)])):
    check(f'{label} weights are refused', refused(lambda w=slots: invalid_geometry('weights', w)))
check('negative palette bone is refused', refused(lambda: invalid_geometry('palette', [-1, 1])))
check('negative strip index is refused', refused(lambda: invalid_geometry('strip', -1)))

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
