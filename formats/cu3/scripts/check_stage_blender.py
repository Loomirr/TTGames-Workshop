"""Asset-free static draw check. Supply a new output folder after --."""
import copy
from pathlib import Path
import sys

import bpy
from mathutils import Vector

root = Path(__file__).resolve().parents[1]
if '--' not in sys.argv or len(sys.argv[sys.argv.index('--')+1:])!=1:
    raise ValueError('Supply a new output folder after --')
output = Path(sys.argv[sys.argv.index('--')+1]).resolve()
output.mkdir(parents=True,exist_ok=False)
sys.path.insert(0, str(root / 'Addon'))
from io_scene_lego_cu3.blender_import import C, row_matrix
from io_scene_lego_cu3.cu3 import FormatError
from io_scene_lego_cu3.stage_geometry import decode_stage_commands
from io_scene_lego_cu3.stage_blender import build_static_stage

bpy.ops.wm.read_factory_settings(use_empty=True)
collection = bpy.data.collections.new('Stage fixture')
bpy.context.scene.collection.children.link(collection)
commands = [(0x84,4,0), (0x85,1,9), (0x80,3,0), (0x8b,1,0), (0xb0,3,2),
            (0x83,0,0), (0xb3,0,0), (0x83,0,1), (0xb3,0,0),
            (0x84,4,0), (0x87,0,0), (0x83,0,2), (0xb3,0,1), (0x8e,0,0)]
source = str(output / 'synthetic-stage.gsc')
Path(source).write_text('Asset-free native static stage fixture',encoding='utf-8')
positions = [(0,0,0), (1,0,0), (0,1,0)]
vertices = [dict(position=list(position), uv=[i / 4, .2 + i / 5],
                 uv2=[.1, .2, .3, .4], normal=[0,0,1], color=[32,64,128,255])
            for i, position in enumerate(positions)]
part = dict(index=0, vertices=vertices, triangles=[[0,1,2]], morphs=None,
            attribute_types={'normal':3})
model = dict(source=source, mesh_version=169, skeleton=None,
             parts=[part, dict(copy.deepcopy(part), index=1)],
             materials=[dict(name='Static material', render_flags={'colourWriteMask':15}),
                        dict(name='Named material', render_flags={'colourWriteMask':15})],
             display=dict(version=21, commands=commands,
                          specials=[dict(index=0, clip=0)],
                          clips=[dict(materials=[1], items=[12])]))
# Non-uniform scale and rotation plus translation expose wrong order, missing
# axis conversion, index reuse, or accidentally treating row matrices as columns.
matrices = [[0,2,0,0, -3,0,0,0, 0,0,4,0, 10,20,30,1],
            [1,0,0,0, 0,1,0,0, 0,0,1,0, -2,3,5,1],
            [1,0,0,0, 0,1,0,0, 0,0,1,0, 999,999,999,1]]
inventory = decode_stage_commands(model['display'], 3, 2, 2)
inventory.update(schema='tt.stage-geometry-inventory.v1', source=source,
                 display_version=21, display_matrices=matrices, commands=commands)
original_model, original_inventory = copy.deepcopy(model), copy.deepcopy(inventory)
material_calls = []
def material_factory(native_model, entry, definition):
    material_calls.append(entry['name'])
    return bpy.data.materials.new(entry['name'])

stage, objects, report = build_static_stage(model, inventory, collection, material_factory)
assert len(objects) == 2 and len(collection.objects) == 3
assert material_calls == ['Static material'], material_calls
assert report['named_draws_excluded'] == 1 and not report['can_render_faithfully']
assert report['render_controls'] == [{'command':4, 'opcode':0xb0, 'flags':3, 'value':2}]
assert not stage['tt_can_render_faithfully']
for obj, row in zip(objects, inventory['static_candidates']):
    transform = C @ row_matrix(matrices[row['matrix']])
    for vertex, original in zip(obj.data.vertices, positions):
        assert (vertex.co - transform @ Vector(original)).length < 1e-6
    assert [list(p.vertices) for p in obj.data.polygons] == [[0,1,2]]
    assert obj.parent == stage and obj.matrix_local.is_identity
    assert obj['source_part'] == 0 and obj['source_special'] == -1
    assert obj['source_draw_command'] == row['command']
    assert obj['source_draw_matrix'] == row['matrix']
    assert obj['source_material'] == 0 and obj['source_draw_flags'] == 0
    for field in ('uv', 'uv2'):
        for component in range(len(vertices[0][field]) // 2):
            layer = obj.data.uv_layers[f'Source {field} {component}']
            for loop in obj.data.loops:
                value = vertices[loop.vertex_index][field]
                expected = Vector((value[2*component], 1-value[2*component+1]))
                assert (layer.data[loop.index].uv - expected).length < 1e-6
    for actual in obj.data.color_attributes['SourceColor'].data:
        assert max(abs(a-b/255) for a,b in zip(actual.color_srgb, vertices[0]['color'])) < .005
assert model == original_model and inventory == original_inventory

# A malformed native pool or mismatched inventory must fail before any Blender
# objects, meshes or materials are allocated, instead of drawing a partial pool.
for kind in ('unknown_opcode', 'different_bindings', 'non_affine_matrix', 'wrong_version'):
    invalid_model, invalid_inventory = copy.deepcopy(model), copy.deepcopy(inventory)
    if kind == 'unknown_opcode':
        invalid_model['display']['commands'][4] = (0xab,3,2)
        invalid_inventory['commands'] = copy.deepcopy(invalid_model['display']['commands'])
    elif kind == 'different_bindings':
        invalid_inventory['static_candidates'][0]['part'] = 1
    elif kind == 'non_affine_matrix':
        invalid_inventory['display_matrices'][0][3] = 1
    else:
        invalid_model['display']['version'] = 34
    stores = ('objects','meshes','materials')
    before = tuple(len(getattr(bpy.data, name)) for name in stores)
    try:
        build_static_stage(invalid_model, invalid_inventory, collection, material_factory)
    except FormatError:
        pass
    else:
        raise AssertionError(f'{kind} was accepted')
    assert before == tuple(len(getattr(bpy.data, name)) for name in stores)
print('STAGE_BLENDER_CHECK_PASSED: native positions, matrices, UVs, topology, colors, material bindings; specials excluded; invalid input rejected before mutation')
