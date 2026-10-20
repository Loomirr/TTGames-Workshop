"""Asset-free Blender export regressions. Writes only into the supplied output directory.

blender -b --factory-startup --python-exit-code 1 --python THIS_FILE -- OUTPUT
Synthetic round trips are not evidence of in-game compatibility.
"""
import importlib
import json
import sys
from pathlib import Path

import bpy

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from synthetic_fixture import build_model

importer = importlib.import_module(f'{PACKAGE.name}.importer')
exporter = importlib.import_module(f'{PACKAGE.name}.exporter')
hgp = importlib.import_module(f'{PACKAGE.name}.hgp')
out = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
out.mkdir(parents=True, exist_ok=True)
source = out / 'synthetic_source.hgp'
original = build_model()
source.write_bytes(original)
passed = []


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return importer.import_hgp(bpy.context, str(source), animations=False)


def write(arm, label):
    data, _ = exporter.export_hgp(bpy.context, str(out / (label + '.hgp')), arm)
    assert source.read_bytes() == original, 'source changed'
    return data, hgp.Model(data)


def refused(label, arm, **kwargs):
    target = out / (label + '.hgp')
    assert not target.exists(), f'use a fresh output directory: {target}'
    try:
        exporter.export_hgp(bpy.context, str(target), arm, **kwargs)
    except exporter.ExportError as exc:
        print(label, str(exc))
    else:
        raise AssertionError(f'{label}: export should have refused')
    assert not target.exists()
    assert source.read_bytes() == original
    passed.append(label)


arm, model = fresh()
data, _ = write(arm, 'unchanged')
assert data == original, 'unchanged Blender round trip must preserve all bytes'
passed.append('unchanged')

arm, model = fresh()
obj = exporter.collect(arm)[0]
index = obj['lsw2_part']
attr = obj.data.attributes['lsw2_colour']
attr.data[0].value = 0x12345678
obj.data.update()
_, edited = write(arm, 'colour')
assert edited.parts[index].colours[0] == 0x12345678
assert edited.parts[index].positions == model.parts[index].positions
passed.append('colour-only edit')

arm, model = fresh()
obj = exporter.collect(arm)[0]
index = obj['lsw2_part']
obj.data.normals_split_custom_set_from_vertices([(1, 0, 0)] * len(obj.data.vertices))
obj.data.update()
_, edited = write(arm, 'normal')
assert all(n[0] > .999 for n in edited.parts[index].normals)
assert edited.parts[index].normals != model.parts[index].normals
passed.append('normal-only edit')

arm, model = fresh()
obj = exporter.collect(arm)[0]
index = obj['lsw2_part']
loop_normals = [(0, 1, 0)] * len(obj.data.loops)
for li in obj.data.polygons[0].loop_indices:
    loop_normals[li] = (1, 0, 0)
obj.data.normals_split_custom_set(loop_normals)
obj.data.update()
_, edited = write(arm, 'hard_normals')
assert len(edited.parts[index].positions) > len(model.parts[index].positions)
assert any(n[0] > .999 for n in edited.parts[index].normals)
assert any(n[2] > .999 for n in edited.parts[index].normals)
passed.append('split corner normals')

arm, model = fresh()
donor = hgp.Model(original)
donor_materials = [dict(m) for m in donor.materials]
donor_materials[0]['colour'] = (.2, .3, .4)
donor_path = out / 'donor.hgp'
donor_path.write_bytes(donor.write(materials=donor_materials))
donor_arm, _ = importer.import_hgp(bpy.context, str(donor_path), animations=False)
obj = exporter.collect(arm)[0]
obj.data.materials[0] = exporter.collect(donor_arm)[0].data.materials[0]
_, edited = write(arm, 'donor_material')
assert len(edited.materials) == len(model.materials) + 1
assert len(edited.textures) == len(model.textures) + 1
assert edited.materials[0] == model.materials[0]
assert edited.parts[0].material == len(model.materials)
passed.append('donor material and texture identity')

arm, model = fresh()
first, second = exporter.collect(arm)
copy_mat = first.data.materials[0].copy()
first.data.materials[0] = copy_mat
mix = next(n for n in copy_mat.node_tree.nodes if n.type == 'MIX')
mix.inputs['A'].default_value = (0, 1, 0, 1)
_, edited = write(arm, 'copied_material')
assert edited.parts[0].material != edited.parts[1].material
assert edited.materials[edited.parts[0].material]['colour'] == (0, 1, 0)
assert edited.materials[edited.parts[1].material]['colour'] == model.materials[0]['colour']
passed.append('same-source copied material')

arm, model = fresh()
first, second = exporter.collect(arm)
copy_mat = first.data.materials[0].copy()
first.data.materials[0] = copy_mat
tex = next(n for n in copy_mat.node_tree.nodes if n.type == 'TEX_IMAGE')
tex.image = tex.image.copy()
tex.image.pixels[:] = [1, 0, 0, 1] * (tex.image.size[0] * tex.image.size[1])
_, edited = write(arm, 'copied_texture')
t0 = edited.materials[edited.parts[0].material]['texture']
t1 = edited.materials[edited.parts[1].material]['texture']
assert t0 != t1
assert edited.textures[t0]['dds'] != edited.textures[t1]['dds']
assert edited.textures[0]['dds'] == model.textures[0]['dds']
passed.append('same-source copied image')

part = model.parts[0]
bad_positions = list(part.positions)
bad_positions[0] = (float('nan'), 0, 0)
try:
    exporter.matches_original(part, bad_positions, part.normals, part.uvs,
                              part.weights, part.triangles(), part.shapes, part.colours)
except exporter.ExportError:
    passed.append('nonfinite unchanged comparison')
else:
    raise AssertionError('NaN position accepted')

arm, _ = fresh()
other = out / 'different_source.hgp'
changed = hgp.Model(original)
changed.parts[0].colours[0] = 0x12345678
other.write_bytes(changed.write(parts=changed.parts))
refused('wrong_source', arm, source=str(other))

arm, _ = fresh()
try:
    exporter.export_hgp(bpy.context, str(source), arm)
except exporter.ExportError:
    pass
else:
    raise AssertionError('source overwrite accepted')
assert source.read_bytes() == original
passed.append('source overwrite')

arm, _ = fresh()
arm.data.bones[0].name = 'renamed_native_bone'
refused('native_name_edit', arm)

arm, _ = fresh()
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
bone = arm.data.edit_bones[0]
bone.head.x += .1
bone.tail.x += .1
bpy.ops.object.mode_set(mode='OBJECT')
refused('native_rest_edit', arm)

arm, _ = fresh()
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
arm.data.edit_bones[1].parent = None
bpy.ops.object.mode_set(mode='OBJECT')
refused('native_parent_edit', arm)

arm, _ = fresh()
del arm['lsw2_source_sha256']
refused('missing_source_identity', arm)

arm, _ = fresh()
obj = exporter.collect(arm)[0]
obj.data.materials.append(obj.data.materials[0].copy())
obj.data.polygons[0].material_index = 1
refused('multiple_face_materials', arm)

arm, _ = fresh()
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
bone = arm.data.edit_bones.new('new_\N{SNOWMAN}')
bone.head = (0, 0, 0)
bone.tail = (0, .1, 0)
bpy.ops.object.mode_set(mode='OBJECT')
refused('lossy_bone_name', arm)

arm, _ = fresh()
obj = next(o for o in exporter.collect(arm) if o.data.shape_keys)
obj.modifiers.new('unbaked deformation', 'SIMPLE_DEFORM')
refused('shape_modifier', arm)

(out / 'results.json').write_text(json.dumps({'blender': bpy.app.version_string,
    'passed': passed, 'input': 'synthetic fixture; no original game file'}, indent=2), encoding='utf-8')
print('PASSED', len(passed), passed)
