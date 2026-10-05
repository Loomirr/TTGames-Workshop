"""Experimental static stage geometry, using verified native draw bindings.

This deliberately excludes named specials and preserves the native model input.
The decoded static section is not yet an engine-equivalent visibility/pass list.
"""
import json
import math
from pathlib import Path

from .cu3 import FormatError
from .native_model_blender import create_model
from .stage_geometry import decode_stage_commands


def build_static_stage(model, inventory, collection, material_factory=None):
    """Return ``(root, objects, report)`` for bounded static stage candidates.

    ``model`` comes from ``load_model`` and ``inventory`` from
    ``read_stage_geometry`` for the same GSC. Layout and binding checks happen
    before creating Blender data. The caller owns its scene import transaction,
    including rollback if material construction subsequently fails.
    """
    if model.get('skeleton') is not None or Path(model['source']).suffix.lower() != '.gsc':
        raise FormatError('Static stage building requires a native GSC without a skeleton')
    display = model['display']
    if (model.get('mesh_version'), display.get('version')) not in ((169, 21), (175, 32)):
        raise FormatError('Unverified native stage mesh/display version pair')
    if (inventory.get('schema') != 'tt.stage-geometry-inventory.v1' or
            inventory.get('display_version') != display['version'] or
            Path(inventory.get('source', '')).resolve() != Path(model['source']).resolve()):
        raise FormatError('Stage inventory does not belong to this native model')
    if inventory.get('commands') != display['commands']:
        raise FormatError('Stage inventory command pool differs from its native model')
    matrices = inventory['display_matrices']
    for matrix in matrices:
        if (len(matrix) != 16 or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in matrix)
                or tuple(matrix[index] for index in (3, 7, 11, 15)) != (0, 0, 0, 1)):
            raise FormatError('Invalid native affine stage matrix')
    verified = decode_stage_commands(display, len(matrices), len(model['parts']), len(model['materials']))
    if inventory.get('static_candidates') != verified['static_candidates']:
        raise FormatError('Static stage inventory differs from verified command bindings')

    draws = []
    for row in verified['static_candidates']:
        draws.append({'index':row['command'], 'name':f'Static draw {row["command"]}',
                      'matrix':matrices[row['matrix']],
                      'parts':[{'part':row['part'], 'material':row['material']}],
                      'unsupported_commands':[]})
    # Reuse the native mesh/UV/color/normal/material implementation without
    # replacing the caller's display table or changing any source vertex data.
    static_model = dict(model)
    static_model['display'] = dict(display, specials=draws)
    name = f'{Path(model["source"]).stem} / Recovered static stage'
    root, objects = create_model(static_model, name, collection, None, material_factory)
    for obj, row in zip(objects, verified['static_candidates']):
        # This geometry is not a named special; do not impersonate one using a
        # command index in the source_special field emitted by create_model.
        obj['source_special'] = -1
        obj['source_draw_command'] = row['command']
        obj['source_draw_matrix'] = row['matrix']
        obj['source_material'] = row['material']
        obj['source_draw_flags'] = row['flags']
        obj['source_draw_group'] = row['group']
        obj['tt_static_stage_candidate'] = True
    report = {
        'schema':'tt.static-stage-build.v1', 'source':str(model['source']),
        'display_version':display['version'], 'objects':len(objects),
        'static_bindings':verified['static_candidates'],
        'named_draws_excluded':len(verified['named_draws']),
        'render_controls':verified['render_controls'],
        'can_render_faithfully':False,
        'limitations':list(verified['limitations']),
    }
    root['tt_static_stage_candidate'] = True
    root['tt_can_render_faithfully'] = False
    root['tt_stage_status'] = 'Experimental static geometry; visibility and render passes are approximate'
    root['tt_stage_render_controls'] = json.dumps(report['render_controls'])
    return root, objects, report
