"""Import all declared layer sets from a user-owned original PC character tree.

blender -b --factory-startup --python-exit-code 1 --python this.py -- input-root new-output
Invalid original declarations are reported as refusals, not silently repaired.
"""
import importlib.util
import argparse
import json
from pathlib import Path
import sys

import bpy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--addon', type=Path, help='Extracted extension ZIP to verify instead of source')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source, output = args.source.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    component = args.addon.resolve() if args.addon else Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('lsw1_definition_test', component / '__init__.py',
                                                submodule_search_locations=[str(component)])
    addon = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = addon
    spec.loader.exec_module(addon)
    from lsw1_definition_test.definition import companion, read_layer_set, LAYER_SETS
    from lsw1_definition_test.hgp import HGP
    from lsw1_definition_test.importer import import_character, snapshot_data, remove_created_data

    bpy.ops.wm.read_factory_settings(use_empty=True)
    results, refused = [], []
    for path in sorted(source.rglob('*')):
        if path.suffix.lower() != '.hgp':
            continue
        try:
            definition = companion(path, '.txt')
        except ValueError:
            continue
        h = HGP(path)
        for name in LAYER_SETS:
            before = snapshot_data()
            try:
                try:
                    layers = read_layer_set(definition, name, h.layer_count)
                    parts = h.meshes_for_layers(layers)
                except ValueError as error:
                    if 'has no layers_' not in str(error):
                        refused.append(dict(file=str(path.relative_to(source)), set=name, error=str(error)))
                    # The import must refuse too, without leaving partial scene data.
                    try:
                        import_character(bpy.context, definition, textures=False, detail='GAME_' + name.upper())
                    except ValueError:
                        assert snapshot_data() == before
                    else:
                        raise AssertionError('An invalid definition was silently accepted')
                    continue
                root = import_character(bpy.context, definition, textures=False, detail='GAME_' + name.upper(),
                                        correct_preview_pose=False)
                objects = sorted(root.children, key=lambda o: int(o.name.rsplit(' ', 1)[1]))
                assert len(objects) == len(parts)
                assert list(root['lsw1_selected_layers']) == sorted({p['layer'] for p in parts})
                assert Path(root['lsw1_definition_file']) == definition
                for obj, part in zip(objects, parts):
                    assert obj['lsw1_geometry_offset'] == hex(part['geometry'])
                    assert obj['lsw1_primitive_offset'] == hex(part['primitive'])
                    assert [tuple(poly.vertices) for poly in obj.data.polygons] == part['faces']
                    if obj.data.shape_keys:
                        assert all(k.value == 0 for k in list(obj.data.shape_keys.key_blocks)[1:])
                results.append(dict(file=str(path.relative_to(source)), set=name, layers=layers, parts=len(parts)))
            finally:
                remove_created_data(bpy.context, before)
            if len(results) % 50 == 0:
                print('DEFINITIONS', len(results), flush=True)
    assert results, 'No declared layer sets were imported'
    report = dict(blender=bpy.app.version_string, imported=results, refused=refused)
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('PASS', len(results), 'declared sets;', len(refused), 'invalid sets refused', flush=True)


if __name__ == '__main__':
    main()
