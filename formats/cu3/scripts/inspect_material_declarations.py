"""Inspect native material/CD declarations without loading a mesh, skeleton or Blender.

Provide an extracted, uncompressed GHG/GSC and optionally an explicit CD path.
The new JSON report contains bounded declaration metadata, not geometry, image
or archive payloads. Renderer application and visual fidelity are not tested.
The supplied CD/model pairing is recorded, not inferred or proven by this tool.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import sys
import types

package = types.ModuleType('material_declaration_inspection')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules.setdefault(package.__name__, package)
from material_declaration_inspection.native_materials import read_materials_bytes, costume_slot
from material_declaration_inspection.definitions import read_definition_bytes
from material_parameter_inspection import inspect_parameters


MAX_MODEL_BYTES = 256 * 1024 * 1024
MAX_CD_BYTES = 32 * 1024 * 1024
MAX_DECODED_MATERIALS = 4096
MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_TOTAL_CD_FIELDS = 8192
MAX_ROLE_MATCHES = 32
SUPPORTED_MESH_VERSIONS = (161, 169, 170, 175)
SURFACE_FIELDS = ('surfaceMapMethod', 'surfaceMapFormat0', 'surfaceMapFormat1',
                  'surfaceMapFormat2', 'surfaceMapFormat3', 'surfaceMapFormatVTFN')


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _snapshot(path, maximum):
    """Read an immutable, bounded snapshot; never mix path and handle stamps."""
    path = Path(path)
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= maximum:
            raise ValueError(f'{path.name}: choose a nonempty regular file of at most {maximum} bytes')
        data = stream.read(before.st_size)
        after = os.fstat(stream.fileno())
    if _stamp(before) != _stamp(after) or len(data) != before.st_size:
        raise ValueError(f'{path.name}: source changed or was truncated during inspection')
    return data, dict(name=path.name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                      read_identity=dict(device=before.st_dev, inode=before.st_ino,
                                         mtime_ns=before.st_mtime_ns, ctime_ns=before.st_ctime_ns),
                      snapshot_byte_limit=maximum)


def _mesh_header(data):
    # Same section/version gate as native_mesh.read_mesh_bytes. Inspect only
    # the tag and big-endian version; do not construct or decode MeshReader.
    candidate = None
    at = data.find(b'HSEM')
    while at >= 0:
        if at + 8 <= len(data):
            version = struct.unpack_from('>I', data, at + 4)[0]
            if version in SUPPORTED_MESH_VERSIONS:
                if candidate is not None:
                    raise ValueError('Expected one supported native MESH header; multiple candidates remain ambiguous')
                candidate = dict(offset=at, version=version, byte_order='big')
        at = data.find(b'HSEM', at + 4)
    if candidate is None:
        raise ValueError('Expected one supported native MESH header in an extracted, uncompressed GHG/GSC')
    candidate['validation'] = 'Version header only; geometry and skeleton ownership were not decoded or validated'
    return candidate


def _text(value, limit):
    if len(value) <= limit:
        return value
    return dict(prefix=value[:limit], chars=len(value), truncated=True,
                sha256=hashlib.sha256(value.encode('utf-8')).hexdigest())


def _value(value, text_limit):
    if isinstance(value, str):
        return _text(value, text_limit)
    if isinstance(value, (tuple, list)):
        # Current definition primitives contain at most a 4x4 matrix. Do not
        # acquire a future payload-array type through an unnoticed API change.
        if len(value) > 16 or any(isinstance(item, (dict, list, tuple, bytes)) for item in value):
            raise ValueError('Definition value is outside the bounded primitive declaration scope')
        return [_value(item, text_limit) for item in value]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    raise ValueError('Unsupported definition value in diagnostic report')


def _opaque_bytes(values):
    raw = bytes(values)
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                first_bytes_hex=raw[:64].hex(), first_bytes_limit=64, truncated=len(raw) > 64,
                interpretation='Opaque bytes; individual meanings are not decoded')


def _material(entry, data=None):
    fields = entry['fields']
    shader = {key: value for key, value in fields.items()
              if key not in ('uvSets', 'opaqueShaderFlags') and key not in SURFACE_FIELDS}
    flags = {key: value for key, value in entry['render_flags'].items() if key != 'opaqueModernTail'}
    row = dict(index=entry['index'], name=entry['name'], table_version=entry['table_version'],
               native_special_id=flags.get('special_id'), costume_role=costume_slot(entry),
               source_spans={key: entry[key] for key in ('offset', 'prefix_end', 'texture_end',
                             'name_offset', 'name_end', 'footer_offset', 'end_offset')},
               texture_ids=entry['texture_ids'], texture_formats=entry['texture_formats'],
               raw_uv_pairs=fields.get('uvSets', []), shader_fields=shader,
               surface_fields={key: fields[key] for key in SURFACE_FIELDS if key in fields},
               render_flags=flags)
    if 'opaqueShaderFlags' in fields:
        row['opaque_shader_flags'] = _opaque_bytes(fields['opaqueShaderFlags'])
    if 'opaqueModernTail' in entry['render_flags']:
        row['opaque_footer_tail'] = _opaque_bytes(entry['render_flags']['opaqueModernTail'])
    if data is not None:
        row['parameter_block'] = inspect_parameters(data, entry)
    return row


def _definition_report(parsed, source, materials, *, max_objects, max_fields, max_text):
    roles = {}
    for entry in materials:
        role = costume_slot(entry)
        if role is not None:
            roles.setdefault(role, []).append(entry['index'])
    objects, total_fields, emitted_fields, remaining = [], 0, 0, MAX_TOTAL_CD_FIELDS
    for index, obj in enumerate(parsed['objects']):
        total_fields += len(obj['fields'])
        if index >= max_objects:
            continue
        fields = []
        for name, value in obj['fields'].items():
            if len(fields) == max_fields or remaining == 0:
                break
            fields.append(dict(name=_text(name, max_text), value=_value(value, max_text)))
            remaining -= 1
        emitted_fields += len(fields)
        row = dict(object_index=index, class_name=_text(obj['class'], max_text),
                   offset=obj['offset'], size=obj['size'], decoded_end=obj['decoded_end'],
                   complete=obj['complete'], fields=fields, total_fields=len(obj['fields']),
                   omitted_fields=len(obj['fields']) - len(fields))
        selector = obj['fields'].get('Material')
        matches = roles.get(selector, []) if type(selector) is int else []
        if 'Material' in obj['fields']:
            row['material_selector'] = _value(selector, max_text)
            row['same_numeric_role'] = dict(material_indices=matches[:MAX_ROLE_MATCHES], total_matches=len(matches),
                                             omitted_matches=max(0, len(matches) - MAX_ROLE_MATCHES))
        objects.append(row)
    return dict(source=source, version=parsed['version'], byte_order=parsed['byte_order'],
                structure_identity=parsed['structure_identity'], unparsed_scope=parsed['unparsed_scope'],
                offset_basis='Decoded definition bytes, including decompressed content for a Deflate_v1.0 source',
                pairing='Explicit user-supplied CD/model paths; resource ownership and renderer branch are not verified',
                role_comparison='Equal decoded integer selectors only; not a material-remap implementation or rendering result',
                total_objects=len(parsed['objects']), reported_objects=len(objects),
                omitted_objects=max(0, len(parsed['objects']) - len(objects)),
                total_decoded_fields=total_fields, reported_fields=emitted_fields,
                omitted_fields=total_fields - emitted_fields, objects=objects)


def _candidate_differences(entries):
    """Retain differing decoded controls; equality is not renderer ownership."""
    differences = []
    if len(entries) < 2:
        return differences
    for group in ('fields', 'render_flags'):
        for key in sorted(set().union(*(entry[group].keys() for entry in entries))):
            values = [entry[group].get(key) for entry in entries]
            if any(value != values[0] for value in values[1:]):
                differences.append(dict(field=group+'.'+key, values=values))
    for key in ('table_version', 'texture_ids', 'texture_formats'):
        values = [entry[key] for entry in entries]
        if any(value != values[0] for value in values[1:]):
            differences.append(dict(field=key, values=values))
    return differences


def remap_comparison(parsed_definition, library, *, max_objects, max_text):
    """Compare names only; never select a renderer variant or follow CD paths."""
    library = Path(library)
    if library.suffix.casefold() not in ('.gsc', '.ghg'):
        raise ValueError('Choose an extracted GSC/GHG material library')
    data, source = _snapshot(library, MAX_MODEL_BYTES)
    marker = data.find(b'LTMU')
    if marker < 0 or marker + 12 > len(data):
        raise ValueError('Material library table header missing or truncated')
    if struct.unpack_from('>I', data, marker + 8)[0] > MAX_DECODED_MATERIALS:
        raise ValueError('Material library count exceeds inspection limit')
    table = read_materials_bytes(data)
    rows, total = [], 0
    for index, obj in enumerate(parsed_definition['objects']):
        fields = obj['fields']
        if not any(key in fields for key in ('Source Material Resource File', 'Source Material')):
            continue
        total += 1
        if len(rows) >= max_objects:
            continue
        name = fields.get('Source Material')
        matches = [entry for entry in table['materials'] if isinstance(name, str) and entry['name'] == name]
        rows.append(dict(object_index=index, complete=obj['complete'],
            declared_resource=_value(fields.get('Source Material Resource File'), max_text),
            declared_name=_value(name, max_text), source_material_type=_value(fields.get('Source Material Type'), max_text),
            costume_role=_value(fields.get('Material'), max_text),
            status='multiple_name_candidates' if len(matches) > 1 else 'single_name_candidate' if matches else 'name_not_found',
            total_candidates=len(matches), omitted_candidates=max(0, len(matches)-MAX_ROLE_MATCHES),
            candidate_differences=_candidate_differences(matches[:MAX_ROLE_MATCHES]),
            difference_scope='Reported candidates only; indices correspond to candidate order; equality does not prove shader equivalence',
            candidates=[_material(entry, data) for entry in matches[:MAX_ROLE_MATCHES]]))
    return dict(source=source, material_table_version=table['version'],
        total_declarations=total, omitted_declarations=total-len(rows), declarations=rows,
        pairing='Explicit user-selected library; declared resource ownership and active renderer are not verified',
        comparison='Exact case-sensitive material names; duplicates remain separate and no candidate is selected',
        renderer_evaluation='Not applied; texture payloads, shader semantics and visual fidelity are not evaluated')


def inspect(source, definition=None, *, max_materials=256, max_objects=256, max_fields=128, max_text=2048,
            remap_library=None):
    if remap_library is not None and definition is None:
        raise ValueError('--remap-library requires an explicit --definition')
    for value, minimum, maximum, name in ((max_materials, 1, 1024, 'max_materials'),
            (max_objects, 1, 2048, 'max_objects'), (max_fields, 1, 256, 'max_fields'), (max_text, 64, 4096, 'max_text')):
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f'{name} must be from {minimum} to {maximum}')
    source = Path(source)
    if source.suffix.casefold() not in ('.ghg', '.gsc'):
        raise ValueError('Choose an extracted GHG/GSC model; this inspector does not open DAT archives')
    if definition is not None and Path(definition).suffix.casefold() != '.cd':
        raise ValueError('Choose an explicit CD definition path')
    data, source_info = _snapshot(source, MAX_MODEL_BYTES)
    header = _mesh_header(data)
    marker = data.find(b'LTMU')
    if marker < 0 or marker + 12 > len(data):
        raise ValueError('Native material table header missing or truncated')
    if struct.unpack_from('>I', data, marker + 8)[0] > MAX_DECODED_MATERIALS:
        raise ValueError(f'Material declaration count exceeds inspection limit {MAX_DECODED_MATERIALS}')
    parsed = read_materials_bytes(data)
    entries = parsed['materials']
    report = dict(schema='tt.material-declarations.v1', status='declarations_inspected', source=source_info, mesh_header=header,
                  material_table=dict(version=parsed['version'], byte_order='big',
                      offset=parsed.get('table_offset'), end=parsed.get('table_end'),
                      layout_validation=parsed.get('layout_validation', 'Empty declared material table; no records inspected')),
                  renderer_evaluation=dict(status='not_evaluated',
                      detail='No Blender scene, texture payload, normal encoding, shader application or visual result was tested'),
                  scope='Decoded native declarations only; numeric values are retained without assigning new enum meanings',
                  role_basis='costume_role uses the existing native costume-slot gate; native_special_id retains the authored scalar',
                  total_materials=len(entries), reported_materials=min(len(entries), max_materials),
                  omitted_materials=max(0, len(entries) - max_materials),
                  materials=[_material(entry, data) for entry in entries[:max_materials]], definition=None,
                  limits=dict(model_bytes=MAX_MODEL_BYTES, cd_stored_and_decoded_bytes=MAX_CD_BYTES,
                      decoded_materials=MAX_DECODED_MATERIALS, report_bytes=MAX_REPORT_BYTES,
                      materials=max_materials, definition_objects=max_objects, fields_per_object=max_fields,
                      total_definition_fields=MAX_TOTAL_CD_FIELDS, text_chars=max_text, role_matches=MAX_ROLE_MATCHES))
    if definition is not None:
        cd_data, cd_source = _snapshot(definition, MAX_CD_BYTES)
        compressed = cd_data.startswith(b'Deflate_v1.0')
        if compressed and (len(cd_data) < 36 or not 0 < struct.unpack_from('<I', cd_data, 32)[0] <= MAX_CD_BYTES):
            raise ValueError('Definition declared decoded size exceeds inspection limit or its wrapper is truncated')
        cd_source['compression'] = 'Deflate_v1.0' if compressed else 'none'
        cd = read_definition_bytes(cd_data)
        if cd['source_sha256'] != cd_source['sha256']:
            raise ValueError('Definition digest does not identify the inspected snapshot')
        report['definition'] = _definition_report(cd, cd_source, entries,
            max_objects=max_objects, max_fields=max_fields, max_text=max_text)
        if remap_library is not None:
            report['remap_comparison'] = remap_comparison(cd, remap_library, max_objects=max_objects, max_text=max_text)
    report['declaration_lists_truncated'] = bool(report['omitted_materials'] or report['definition'] and
        (report['definition']['omitted_objects'] or report['definition']['omitted_fields']))
    comparison = report.get('remap_comparison', {})
    report['declaration_lists_truncated'] |= bool(comparison.get('omitted_declarations') or
        any(row['omitted_candidates'] for row in comparison.get('declarations', [])))
    return report


def _render(report):
    chunks, total = [], 0
    for part in json.JSONEncoder(indent=2, allow_nan=False).iterencode(report):
        total += len(part.encode('utf-8'))
        if total + 1 > MAX_REPORT_BYTES:
            raise ValueError('Diagnostic JSON exceeds report byte limit; lower --max-materials or --max-objects')
        chunks.append(part)
    return ''.join(chunks) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Extracted, uncompressed GHG/GSC; never modified')
    parser.add_argument('--definition', type=Path, help='Optional matching CD, selected explicitly by the user')
    parser.add_argument('--remap-library', type=Path, help='Optional explicit GSC/GHG replacement-material library; names compared only')
    parser.add_argument('--output', type=Path, required=True, help='New JSON report filename; existing files/links are protected')
    parser.add_argument('--max-materials', type=int, default=256, help='Material detail limit (1-1024)')
    parser.add_argument('--max-objects', type=int, default=256, help='CD object detail limit (1-2048)')
    parser.add_argument('--max-fields', type=int, default=128, help='Decoded field detail limit per CD object (1-256)')
    parser.add_argument('--max-text', type=int, default=2048, help='String detail limit before prefix/hash summary (64-4096)')
    args = parser.parse_args(argv)
    try:
        if args.output.exists() or args.output.is_symlink():
            raise ValueError('Choose a new diagnostic report filename')
        report = inspect(args.source, args.definition, max_materials=args.max_materials,
                         max_objects=args.max_objects, max_fields=args.max_fields, max_text=args.max_text,
                         remap_library=args.remap_library)
        rendered = _render(report)
        # Complete parsing and bounded serialization before creating output.
        with args.output.open('x', encoding='utf-8', newline='\n') as output:
            output.write(rendered)
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
        parser.error(str(error)[:1024])
    print(f"Report written: {args.output}; {report['reported_materials']}/{report['total_materials']} materials. "
          'Renderer application was not evaluated.')
    if report['declaration_lists_truncated']:
        print('Declaration detail limits omitted records or fields; inspect the omission counts before comparing reports.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
