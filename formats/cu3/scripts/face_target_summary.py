"""Bounded diagnostics for already decoded native position targets.

Target IDs have no inferred expression names. Statistics are in native source
coordinates, not Blender units, and do not establish timing or visible masks.
"""
import math

MAX_PARTS = 128
MAX_TARGETS = 64


def summarize_targets(model):
    parts = [part for part in model['parts'] if part['morphs']]
    rows = []
    for part in parts[:MAX_PARTS]:
        morph = part['morphs']
        targets = []
        for target in morph['targets'][:MAX_TARGETS]:
            offsets = target['offsets']
            if len(offsets) != part['vertex_count'] or not offsets:
                raise ValueError('Target vertex count differs from the decoded mesh part')
            if any(len(delta) != 3 or not all(math.isfinite(v) for v in delta) for delta in offsets):
                raise ValueError('Target diagnostics require finite source-space vectors')
            targets.append(dict(id=target['id'], encoding=target['encoding'],
                record_offset=target['record_offset'],
                affected_vertices=sum(any(v != 0 for v in delta) for delta in offsets),
                max_displacement=max(math.hypot(*delta) for delta in offsets),
                delta_min=[min(delta[axis] for delta in offsets) for axis in range(3)],
                delta_max=[max(delta[axis] for delta in offsets) for axis in range(3)]))
        rows.append(dict(index=part['index'], vertex_count=part['vertex_count'],
            palette_size=len(part['palette']), mesh_record_offset=part['record_offset'],
            target_table_offset=morph['table_offset'], target_end_offset=morph['end_offset'],
            total_targets=len(morph['targets']), omitted_targets=max(0,len(morph['targets'])-MAX_TARGETS),
            targets=targets))
    return dict(schema='tt.face-target-summary.v1', mesh_version=model['mesh_version'],
        semantics='Additive vertex offsets in native source coordinates; IDs are preserved without expression labels',
        static_weights='Imported static shape targets start at zero; this report does not sample animation weights',
        renderer_evaluation='None; visibility, depth masks, skeleton binding and facial timing are separate checks',
        total_parts=len(parts), omitted_parts=max(0,len(parts)-MAX_PARTS),
        total_part_targets=sum(len(part['morphs']['targets']) for part in parts),
        limits=dict(parts=MAX_PARTS,targets_per_part=MAX_TARGETS),parts=rows)
