"""Structural checks on decoded native data, independent of Blender and game names.

Do not repair topology, normalize weights or infer a new layout here. Invalid
references/non-finite data fail; quality observations remain report warnings.
"""
import math
from .cu3 import FormatError


def fail(stage, detail):
    raise FormatError(f'[{stage}] {detail}')


def matrix(values, stage, label):
    if len(values) != 16 or not all(math.isfinite(x) for x in values):
        fail(stage, f'{label}: expected 16 finite matrix values')
    rows = [list(values[i:i+4]) for i in range(0, 16, 4)]
    for col in range(4):
        pivot = max(range(col, 4), key=lambda row: abs(rows[row][col]))
        if rows[pivot][col] == 0:
            fail(stage, f'{label}: singular matrix')
        rows[col], rows[pivot] = rows[pivot], rows[col]
        for row in range(col+1, 4):
            factor = rows[row][col] / rows[col][col]
            for index in range(col+1, 4):
                rows[row][index] -= factor * rows[col][index]


def validate_model(model):
    """Validate all decoded parts; return portable layout/quality provenance."""
    warnings = []
    skeleton = model['skeleton']
    joints = skeleton['joints'] if skeleton else []
    if skeleton:
        names = set()
        for i, joint in enumerate(joints):
            parent = joint['parent']
            if joint['index'] != i or (parent is not None and not 0 <= parent < i):
                fail('skeleton association', f'joint {i}: invalid index or parent')
            if joint['name'] in names:
                fail('skeleton association', f'joint {i}: duplicate bone name')
            names.add(joint['name'])
            for field in ('local_bind_row_major', 'inverse_world_bind_row_major'):
                matrix(joint[field], 'skeleton association', f'joint {i} {field}')
    summaries = []
    for index, part in enumerate(model['parts']):
        if part['index'] != index:
            fail('mesh validation', f'part {index}: index differs from table position')
        vertices = part['vertices']
        numeric_fields = ('position', 'normal', 'tangent', 'bitangent', 'uv', 'uv2', 'uv3')
        degenerate = weight_sums = zero_weights = 0
        skin_diagnostics = []
        for vi, vertex in enumerate(vertices):
            if len(vertex.get('position', ())) < 3:
                fail('mesh validation', f'part {index}, vertex {vi}: missing position')
            for field in numeric_fields:
                if field not in vertex:
                    if vertices and field in vertices[0]:
                        fail('mesh validation', f'part {index}, vertex {vi}: missing {field} attribute')
                    continue
                values = vertex[field]
                if not all(math.isfinite(x) for x in values):
                    fail('mesh validation', f'part {index}, vertex {vi}: non-finite {field}')
                if len(values) != len(vertices[0].get(field, ())):
                    fail('mesh validation', f'part {index}, vertex {vi}: inconsistent {field} width')
                if field.startswith('uv') and (not values or len(values) % 2):
                    fail('mesh validation', f'part {index}, vertex {vi}: incomplete {field} pairs')
            weights = vertex.get('weights', ())
            diagnostics = vertex.get('weight_diagnostics')
            if diagnostics is not None:
                if not isinstance(diagnostics, dict):
                    fail('skin validation', f'part {index}, vertex {vi}: weight diagnostics must be a record')
                for field in ('raw_total', 'retained_total', 'skipped_sentinel_weight'):
                    value = diagnostics.get(field)
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                        fail('skin validation', f'part {index}, vertex {vi}: invalid {field} diagnostic')
                slots = diagnostics.get('skipped_sentinel_slots')
                if (not isinstance(slots, (list, tuple)) or len(slots) > 4 or
                        any(type(slot) is not int or not 0 <= slot < 4 for slot in slots) or
                        len(set(slots)) != len(slots)):
                    fail('skin validation', f'part {index}, vertex {vi}: invalid skipped_sentinel_slots diagnostic')
                merged = diagnostics.get('merged_duplicate_influences')
                if type(merged) is not int or not 0 <= merged <= 3:
                    fail('skin validation', f'part {index}, vertex {vi}: invalid merged_duplicate_influences diagnostic')
                skin_diagnostics.append(diagnostics)
            for joint, weight in weights:
                if not isinstance(joint, int) or joint < 0 or not math.isfinite(weight) or weight < 0:
                    fail('skin validation', f'part {index}, vertex {vi}: invalid joint/weight')
            if weights:
                total = sum(w for _, w in weights)
                zero_weights += total == 0
                weight_sums += abs(total-1) > .01
        for ti, triangle in enumerate(part['triangles']):
            if len(triangle) != 3 or any(not isinstance(v, int) or not 0 <= v < len(vertices) for v in triangle):
                fail('mesh validation', f'part {index}, triangle {ti}: invalid vertex indices')
            degenerate += len(set(triangle)) != 3
        for code, count in (('repeated_triangle_indices', degenerate), ('non_unit_weight_sums', weight_sums), ('zero_weight_sums', zero_weights)):
            if count:
                warnings.append(dict(stage='mesh/skin validation', code=code, part=index, count=count))
        if not vertices or not part['triangles']:
            warnings.append(dict(stage='mesh validation', code='empty_part', part=index))
        summary = dict(part=index, vertices=len(vertices), triangles=len(part['triangles']),
                       attributes=list(part['attribute_types']), morph_targets=len(part['morphs']['targets']) if part['morphs'] else 0)
        if skin_diagnostics:
            summary['source_weight_totals'] = dict(
                vertices=len(skin_diagnostics),
                raw_min=min(d['raw_total'] for d in skin_diagnostics),
                raw_max=max(d['raw_total'] for d in skin_diagnostics),
                retained_min=min(d['retained_total'] for d in skin_diagnostics),
                retained_max=max(d['retained_total'] for d in skin_diagnostics),
                skipped_sentinel_slots=sum(len(d['skipped_sentinel_slots']) for d in skin_diagnostics),
                skipped_sentinel_weight=sum(d['skipped_sentinel_weight'] for d in skin_diagnostics),
                scope='Authored totals before normalized viewing weights')
            observations = (
                ('non_unit_raw_weight_totals', lambda d: abs(d['raw_total']-1) > .01),
                ('non_unit_retained_weight_totals', lambda d: abs(d['retained_total']-1) > .01),
                ('nonzero_sentinel_weights', lambda d: d['skipped_sentinel_weight'] > 0),
                ('duplicate_skin_influences', lambda d: d['merged_duplicate_influences'] > 0),
                ('zero_retained_weight_totals', lambda d: d['retained_total'] == 0),
            )
            for code, predicate in observations:
                count = sum(predicate(d) for d in skin_diagnostics)
                if count:
                    warnings.append(dict(stage='skin validation', code=code, part=index, count=count))
        summaries.append(summary)
    return dict(schema='tt.model-validation.v1', mesh_version=model['mesh_version'],
                display_version=model['display']['version'], skeleton_version=skeleton['version'] if skeleton else None,
                material_versions=sorted({m['table_version'] for m in model['materials']}),
                joints=len(joints), parts=summaries, warnings=warnings,
                scope='Decoded structure only; visual fidelity, source texture resolution and selected skin associations are separate checks.')


def validate_draw(model, binding, joint):
    """Validate selected associations before Blender can use negative indices."""
    for field, table in (('part', model['parts']), ('material', model['materials'])):
        value = binding[field]
        if not isinstance(value, int) or not 0 <= value < len(table):
            fail('draw association', f'{field} reference {value} outside table of {len(table)}')
    if model['skeleton'] is None:
        return
    count = len(model['skeleton']['joints'])
    if joint is not None:
        if not isinstance(joint, int) or not 0 <= joint < count:
            fail('skin association', f'rigid joint {joint} outside skeleton of {count}')
    else:
        for vi, vertex in enumerate(model['parts'][binding['part']]['vertices']):
            weights = vertex.get('weights', ())
            if not weights or not any(w > 0 for _, w in weights) or any(not 0 <= j < count for j, _ in weights):
                fail('skin association', f'part {binding["part"]}, vertex {vi}: unresolved skin palette or no positive influence')
