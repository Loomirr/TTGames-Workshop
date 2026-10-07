"""Bounded summaries of decoded HGOL candidates; no ownership inference.

Reports contain offsets, counts, digests and differing field paths. They omit
native byte buffers, names, matrix values and opaque payloads. A decoded span
records reader consumption, not a proven native container boundary.
"""
from .skeleton import (
    SUPPORTED_VERSIONS, _digest, _display_owned, _validate,
    select_skeleton, skeleton_identity,
)


OWNERSHIP_FIELDS = (
    'version', 'byte_order', 'points_of_interest', 'pre_poi_bytes',
    'post_poi_bytes', 'opaque_tail_hex', 'layer_metadata', 'layers',
)
JOINT_FIELDS = (
    'index', 'name', 'parent', 'flags', 'orient_row_major', 'locator_offset',
    'local_bind_row_major', 'inverse_world_bind_row_major',
)


def _limit(value, label, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f'{label} must be an integer from 1 to {maximum}')
    return value


def _message(error, limit=1024):
    text = str(error)
    return dict(detail=text[:limit], detail_truncated=len(text) > limit)


def _identity_values(candidate):
    values = {field: candidate.get(field) for field in OWNERSHIP_FIELDS}
    values['joints'] = candidate['joints']
    return values


def _components(candidate):
    result = {field: _digest(candidate.get(field)) for field in OWNERSHIP_FIELDS}
    result.update({f'joints.{field}': _digest([joint.get(field) for joint in candidate['joints']])
                   for field in JOINT_FIELDS})
    return result


def _different_paths(first, other, prefix=''):
    """Yield field/index paths only; do not copy native values into a report."""
    if type(first) is not type(other):
        yield prefix
    elif isinstance(first, dict):
        for key in sorted(first.keys() | other.keys()):
            path = f'{prefix}.{key}' if prefix else key
            if key not in first or key not in other:
                yield path
            else:
                yield from _different_paths(first[key], other[key], path)
    elif isinstance(first, (list, tuple)):
        if len(first) != len(other):
            yield f'{prefix}.length'
        for index, (left, right) in enumerate(zip(first, other)):
            yield from _different_paths(left, right, f'{prefix}[{index}]')
    elif first != other:
        yield prefix


def _differences(first, other, limit):
    paths = []
    for path in _different_paths(_identity_values(first), _identity_values(other)):
        if len(paths) == limit:
            return dict(paths=paths, truncated=True)
        paths.append(path)
    return dict(paths=paths, truncated=False)


def _display_references(candidate, limit):
    metadata = candidate.get('layer_metadata', [])
    references = []
    for layer in candidate.get('layers', []):
        first = layer['metadata_index']
        references.extend(metadata[first:first + layer['rigids'] + layer['skins']])
    specials = sorted({item['special'] for item in references})
    return dict(layers=len(candidate.get('layers', [])), entries=len(references),
                unique_specials=len(specials), special_indices=specials[:limit],
                omitted_special_indices=max(0, len(specials)-limit),
                note='Compatible references are structural evidence only. Empty layer tables provide no ownership evidence.')


def _groups(records, field, reported, limit):
    groups = {}
    for record in records:
        if record['compatible']:
            groups.setdefault(record['identity'][field], []).append(record['index'])
    result = []
    for digest, indices in list(groups.items())[:limit]:
        shown = [index for index in indices if index < reported]
        result.append(dict(sha256=digest, candidates_total=len(indices),
                           reported_candidate_indices=shown,
                           omitted_candidate_indices=len(indices)-len(shown)))
    return dict(groups_total=len(groups), groups=result, omitted_groups=max(0, len(groups)-limit),
                scope='Valid candidates after the optional display compatibility check.')


def _section_at(candidate, offset):
    for span in candidate.get('decoded_section_spans', []):
        if span['start'] <= offset < span['end']:
            return span
    return None


def _relationships(candidates, tables, limit):
    """Only compare reported spans; retain nested candidates in selection."""
    items, total = [], 0

    def add(item):
        nonlocal total
        total += 1
        if len(items) < limit:
            items.append(item)

    for index, left in enumerate(candidates):
        for second in range(index + 1, len(candidates)):
            right = candidates[second]
            a, b = left['hgol_offset'], left['end_offset']
            c, d = right['hgol_offset'], right['end_offset']
            if a == c:
                add(dict(kind='same_marker_interpretations', candidates=[index, second],
                         name_table_offsets=[left.get('name_table_offset'), right.get('name_table_offset')]))
            elif b == c or d == a:
                add(dict(kind='adjacent_decoded_spans', candidates=[index, second]))
            elif max(a, c) < min(b, d):
                if a <= c and d <= b:
                    outer, inner, inner_index, outer_index = left, right, second, index
                elif c <= a and b <= d:
                    outer, inner, inner_index, outer_index = right, left, index, second
                else:
                    add(dict(kind='overlapping_decoded_spans', candidates=[index, second],
                             overlap_start=max(a, c), overlap_end=min(b, d)))
                    continue
                section = _section_at(outer, inner['hgol_offset'])
                add(dict(kind='contained_decoded_span', outer_candidate=outer_index,
                         inner_candidate=inner_index,
                         containing_field=section['field'] if section else None,
                         inner_end_within_field=bool(section and inner['end_offset'] <= section['end'])))
        for table in tables:
            if table['data_offset'] <= left['hgol_offset'] < table['end_offset']:
                add(dict(kind='marker_inside_name_table_data', candidate=index,
                         name_table_offset=table['offset']))
    return dict(items=items, observations_total=total, omitted_observations=total-len(items),
                examined_candidates=len(candidates), examined_name_tables=len(tables),
                scope='Only reported candidates and name tables are compared. Relationships do not exclude or select candidates.')


def skeleton_candidate_report(scan, *, display=None, mesh=None, expected_nodes=None,
                              max_candidates=64, max_errors=64,
                              max_relationships=128, max_differences=32):
    """Summarize a complete bounded scan without weakening normal selection.

    Limits affect report detail only. Validity, identity grouping and selection
    use every parsed candidate, including candidates omitted from the report.
    """
    _limit(max_candidates, 'max_candidates', 256)
    _limit(max_errors, 'max_errors', 256)
    _limit(max_relationships, 'max_relationships', 2048)
    _limit(max_differences, 'max_differences', 128)
    candidates = scan['candidates']
    records = []
    for index, candidate in enumerate(candidates):
        record = dict(index=index, valid=False, compatible=False, identity=None)
        try:
            _validate(candidate)
            record['identity'] = skeleton_identity(candidate)
            record['valid'] = True
        except (ValueError, KeyError, TypeError) as error:
            record['validation_issue'] = _message(error)
        if record['valid']:
            try:
                if display is not None:
                    _display_owned(candidate, display)
                record['compatible'] = True
            except (ValueError, KeyError, TypeError) as error:
                record['display_issue'] = _message(error)
        records.append(record)

    reported = min(len(candidates), max_candidates)
    ownership_groups = _groups(records, 'ownership_sha256', reported, max_candidates)
    binding_groups = _groups(records, 'binding_sha256', reported, max_candidates)
    baseline = next((record['index'] for record in records[:reported] if record['valid']), None)
    summaries = []
    for record, candidate in zip(records[:reported], candidates[:reported]):
        summary = dict(candidate_index=record['index'], hgol_offset=candidate['hgol_offset'],
                       name_table_offset=candidate.get('name_table_offset'),
                       end_offset=candidate['end_offset'], bind_end_offset=candidate['bind_end_offset'],
                       parsed_bytes=candidate['end_offset']-candidate['hgol_offset'],
                       version=candidate['version'], byte_order=candidate['byte_order'],
                       counts=dict(joints=len(candidate['joints']),
                                   points_of_interest=len(candidate.get('points_of_interest', [])),
                                   layers=len(candidate.get('layers', [])),
                                   layer_metadata=len(candidate.get('layer_metadata', [])),
                                   pre_poi_bytes=len(candidate.get('pre_poi_bytes', [])),
                                   post_poi_bytes=len(candidate.get('post_poi_bytes', [])),
                                   opaque_payload_bytes=len(candidate.get('opaque_tail_hex', ''))//2),
                       identity=record['identity'],
                       validation=dict(valid=record['valid'], issue=record.get('validation_issue')),
                       display_compatibility=dict(checked=display is not None,
                                                  compatible=record['compatible'] if display is not None and record['valid'] else None,
                                                  issue=record.get('display_issue')),
                       decoded_section_spans=candidate.get('decoded_section_spans', []))
        if record['valid']:
            summary['component_sha256'] = _components(candidate)
            if baseline is not None:
                summary['differences_from_baseline'] = _differences(candidates[baseline], candidate, max_differences)
            if display is not None and record['compatible']:
                summary['display_compatibility']['references'] = _display_references(candidate, max_differences)
        if candidate.get('native_variant'):
            variant = candidate['native_variant']
            summary['native_variant'] = dict(index=candidate['native_variant_index'],
                group_array_offset=candidate['native_variant_group']['array_offset'],
                trailer_offset=variant['offset'],end_offset=variant['end_offset'],
                threshold=variant['threshold'],joint_map_entries=len(variant['joint_map']),
                metadata_map_entries=len(variant['metadata_map']),
                serialized_sha256=variant['serialized_sha256'])
        if candidate.get('native_variant_error'):
            summary['native_variant_issue'] = _message(candidate['native_variant_error'])
        summaries.append(summary)

    try:
        rig = select_skeleton(candidates, expected_nodes, display=display, mesh=mesh)
        selected = rig['candidate_offsets']
        selection = dict(outcome='selected', reason=rig['selection']['reason'], identity=rig['identity'],
                         candidate_offsets=selected[:max_candidates],
                         omitted_candidate_offsets=max(0, len(selected)-max_candidates))
        if rig['selection'].get('native_variant_group'):
            native = dict(rig['selection']['native_variant_group'])
            for field, limit in (('candidate_offsets',max_candidates),
                                 ('cross_layer_remaps',max_relationships)):
                entries=native[field]
                native[field]=entries[:limit]
                native[field+'_total']=len(entries)
                native['omitted_'+field]=max(0,len(entries)-limit)
            entries=native['remap_omissions']
            native['remap_omissions_total']=len(entries)
            native['omitted_remap_omissions']=max(0,len(entries)-max_candidates)
            native['remap_omissions']=[]
            for entry in entries[:max_candidates]:
                row=dict(entry)
                values=row['unmapped_variant_entries']
                row['unmapped_variant_entries']=values[:max_differences]
                row['unmapped_variant_entries_total']=len(values)
                row['omitted_unmapped_variant_entries']=max(0,len(values)-max_differences)
                native['remap_omissions'].append(row)
            selection['native_variant_group'] = native
    except (ValueError, KeyError, TypeError) as error:
        outcome = 'ambiguous' if ownership_groups['groups_total'] > 1 else 'rejected'
        selection = dict(outcome=outcome, **_message(error))
    selection.update(expected_nodes=expected_nodes, count_used_to_select=False,
                     display_compatibility_checked=display is not None,
                     candidates_considered=len(candidates))
    tables = scan['name_tables'][:max_candidates]
    errors = [dict(offset=error.get('offset'), name_table_offset=error.get('name_table_offset'),
                   **_message(error['issue'])) for error in scan['errors'][:max_errors]]
    return dict(schema='tt.skeleton-candidates.v1',
                source=dict(path=scan['source'], sha256=scan['source_sha256'], bytes=scan['source_bytes']),
                supported_hgol_versions=list(SUPPORTED_VERSIONS),
                scope='Read-only candidate diagnostics. Decoded spans describe reader consumption, not proven native resource boundaries. No native byte buffers, names or matrix values are exported.',
                limitations=[
                    'Nested and overlapping marker interpretations are retained. Only the fully validated counted HGOL 10/16 variant layouts can resolve distinct identities.',
                    'Opaque payloads remain part of identity; their meaning is unverified.',
                    'Display compatibility and joint counts cannot choose among different compatible identities.',
                    'No Blender, original-file visual or in-game validation is performed by this report.',
                ],
                scan=dict(complete=True, parse_attempts=scan['attempts'],
                          parsed_candidates=len(candidates), valid_candidates=sum(r['valid'] for r in records),
                          compatible_candidates=sum(r['compatible'] for r in records),
                          parse_errors=len(scan['errors']), name_tables=len(scan['name_tables'])),
                selection=selection, binding_groups=binding_groups, ownership_groups=ownership_groups,
                comparison_baseline_candidate=baseline,
                comparison_note='The baseline only anchors field comparisons; it is not an ownership preference.',
                candidates=summaries, omitted_candidates=len(candidates)-reported,
                name_tables=tables, omitted_name_tables=len(scan['name_tables'])-len(tables),
                parse_errors=errors, omitted_parse_errors=len(scan['errors'])-len(errors),
                relationships=_relationships(candidates[:reported], tables, max_relationships),
                limits=dict(max_candidates=max_candidates, max_errors=max_errors,
                            max_relationships=max_relationships, max_differences=max_differences))
