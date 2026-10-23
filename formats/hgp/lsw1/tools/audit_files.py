"""Inventory an LSW1 PC extraction without treating untested files as supported.

python audit_files.py input-folder new-report.json
Reports every discovered file; HGP checks cover every stored layer, not only AUTO.
ANI/BSA record checks are distinct from playback and rig/shape ownership.
This is a reader audit, not Blender, export or in-game validation.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import struct
from pathlib import Path


spec = importlib.util.spec_from_file_location('lsw1_audit_reader', Path(__file__).resolve().parents[1] / 'hgp.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
animation_spec = importlib.util.spec_from_file_location('lsw1_animation_records',
                                                       Path(__file__).with_name('animation_records.py'))
animation_reader = importlib.util.module_from_spec(animation_spec)
animation_spec.loader.exec_module(animation_reader)


def audit(root, max_hgp_bytes=64 * 1024 * 1024):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Choose an extracted LSW1 PC folder')
    if max_hgp_bytes <= 0:
        raise ValueError('The HGP size limit must be positive')
    rows = []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        row = {'file': path.relative_to(root).as_posix(),
               'extension': path.suffix.lower() or '(none)', 'status': 'not_examined'}
        rows.append(row)
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            row['status'] = 'excluded_link'
            continue
        row['bytes'] = path.stat().st_size
        if path.suffix.lower() in ('.ani', '.bsa'):
            try:
                with path.open('rb') as stream:
                    data = stream.read(animation_reader.AnimationRecords.MAX_BYTES + 1)
                clip = animation_reader.AnimationRecords(data, path.suffix[1:].upper())
                row.update(status='record_pass', animation=clip.summary())
            except (OSError, ValueError) as error:
                row.update(status='reader_rejected', error=f'{type(error).__name__}: {error}')
            continue
        if path.suffix.lower() != '.hgp':
            continue
        if row['bytes'] > max_hgp_bytes:
            row.update(status='size_limit', error='HGP exceeds the configured audit limit')
            continue
        try:
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            row['sha256'] = before
            model = reader.HGP(path)
            layers = []
            for index, name in enumerate(model.layers):
                parts = model.layer_meshes(index)
                layers.append({'index': index, 'name': name, 'parts': len(parts),
                               'vertices': sum(len(p['vertices']) for p in parts),
                               'triangles': sum(len(p['faces']) for p in parts),
                               'vertex_types': sorted({p['vertex_type'] for p in parts}),
                               'unhandled_field_0x0c': model.u32(model.lods_at + index * 20 + 12)})
            materials = model.materials()
            texture_count = sum(1 for _ in model.textures())
            assert hashlib.sha256(path.read_bytes()).hexdigest() == before, 'Input changed during audit'
            row.update(status='reader_pass', name_offset=model.header[1], bones=model.count,
                       layers=layers, materials=len(materials), textures=texture_count,
                       material_flags=sorted({m['attributes'] for m in materials}),
                       unhandled_layer_fields=sum(bool(layer['unhandled_field_0x0c']) for layer in layers))
        except (ValueError, OSError, IndexError, AssertionError, struct.error) as error:
            row.update(status='reader_rejected', error=f'{type(error).__name__}: {error}')
    return {'game': 'LSW1', 'platform': 'PC', 'complete': False,
            'scope': 'Files present in the supplied extraction only; completeness of the extraction is unverified.',
            'evidence': 'Reader checks only. No Blender appearance, playback, editing, export or in-game result.',
            'counts': dict(Counter(row['status'] for row in rows)),
            'extensions': dict(sorted(Counter(row['extension'] for row in rows).items())),
            'files': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.input.resolve()):
        parser.error('Put the report outside the input folder')
    if args.output.exists():
        parser.error('Choose a new report filename')
    result = audit(args.input)
    with args.output.open('x', encoding='utf-8') as target:
        json.dump(result, target, indent=2)
        target.write('\n')
    print(json.dumps({'counts': result['counts'], 'extensions': result['extensions']}))


if __name__ == '__main__':
    main()
