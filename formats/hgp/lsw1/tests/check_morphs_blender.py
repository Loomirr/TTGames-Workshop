"""Verify original PC morphs in Blender against raw source-buffer deltas.

blender -b --factory-startup --python-exit-code 1 --python this.py -- input-folder new-output
Recursively reads HGPs, imports all layers of files containing morphs, checks
zeroed Basis, empty slots, topology and evaluated deformation. No assets bundled.
"""
import importlib.util
import json
from pathlib import Path
import struct
import sys

import bpy
from mathutils import Vector


def main():
    source, output = [Path(p).resolve() for p in sys.argv[sys.argv.index('--') + 1:]]
    output.mkdir(parents=True, exist_ok=False)
    component = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('lsw1_morph_test', component / '__init__.py',
                                                submodule_search_locations=[str(component)])
    addon = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = addon
    spec.loader.exec_module(addon)
    from lsw1_morph_test.hgp import HGP
    from lsw1_morph_test.importer import import_character, snapshot_data, remove_created_data

    bpy.ops.wm.read_factory_settings(use_empty=True)
    reports = []
    files = sorted(p for p in source.rglob('*') if p.suffix.lower() == '.hgp')
    assert files, 'No original HGP inputs found'
    layers_checked = 0
    for path in files:
        h = HGP(path)
        layers = [h.layer_meshes(i) for i in range(h.layer_count)]
        layers_checked += len(layers)
        if not any(p['morph'] for layer in layers for p in layer):
            continue
        # Import every nonempty layer, retaining the importer's own deduplication.
        parts = {}
        for layer in layers:
            for p in layer:
                parts[(p['geometry'], p['primitive'], p['rigid_bone'])] = p
        before = snapshot_data()
        keys_before = len(bpy.data.shape_keys)
        root = import_character(bpy.context, path, textures=False, detail=0,
                                variant_layers=range(1, h.layer_count), correct_preview_pose=False)
        bpy.context.view_layer.update()
        meshes = [o for o in root.children if o.type == 'MESH']
        assert len(meshes) == len(parts), path
        totals = dict(file=str(path.relative_to(source)), parts=0, targets=0, empty=0, evaluated=0)
        # Different primitives can share one geometry. Import order is irrelevant.
        for obj in meshes:
            candidates = [p for p in parts.values() if hex(p['geometry']) == obj['lsw1_geometry_offset']]
            # Source primitive metadata avoids count/order heuristics.
            p = next(p for p in candidates if hex(p['primitive']) == obj['lsw1_primitive_offset'])
            keys = obj.data.shape_keys
            if not p['morph']:
                assert keys is None
                continue
            totals['parts'] += 1
            assert [tuple(poly.vertices) for poly in obj.data.polygons] == p['faces']
            assert p['rigid_bone'] is None, 'New rigid morph needs separate transform evidence'
            basis = keys.key_blocks[0]
            assert basis.name == 'Basis'
            for vertex, key_vertex, native in zip(obj.data.vertices, basis.data, p['vertices']):
                expected = Vector((native[0], native[2], native[1]))
                assert (vertex.co - expected).length < 1e-7
                assert (key_vertex.co - vertex.co).length == 0
            record = h.u32(p['geometry'] + 0x3c)
            count, table, ids_at, _, unknown = struct.unpack_from('<5I', h.body, record)
            assert len(keys.key_blocks) == count + 1
            assert obj['lsw1_morph_unknown_word'] == unknown
            best = None
            for i, key in enumerate(list(keys.key_blocks)[1:]):
                totals['targets'] += 1
                target_id = h.u32(ids_at + i * 4)
                pointer = h.u32(table + i * 4)
                assert key.name == f'morph {target_id}' and key.value == 0
                if not pointer:
                    totals['empty'] += 1
                for vi, source_i in enumerate(p['source_vertex_indices']):
                    dx, dy, dz = struct.unpack_from('<3f', h.body, pointer + source_i * 12) if pointer else (0, 0, 0)
                    expected = basis.data[vi].co + Vector((dx, dz, dy))
                    assert (key.data[vi].co - expected).length < 1e-7, (path, obj.name, i, vi)
                    if Vector((dx, dy, dz)).length > 1e-6:
                        best = key
            # Exercise actual depsgraph evaluation through the native armature.
            if best:
                best.value = 1
                bpy.context.view_layer.update()
                evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
                try:
                    assert max((v.co - k.co).length for v, k in zip(evaluated.vertices, best.data)) < 2e-5
                    totals['evaluated'] += 1
                finally:
                    obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
                best.value = 0
        reports.append(totals)
        remove_created_data(bpy.context, before)
        assert len(bpy.data.shape_keys) == keys_before, 'Orphaned morph data after cleanup'
        print('MORPHS', totals, flush=True)
    result = dict(blender=bpy.app.version_string, files_decoded=len(files), layers_decoded=layers_checked,
                  morph_files=len(reports), reports=reports)
    (output / 'report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('PASS', result['files_decoded'], 'files;', result['morph_files'], 'with morphs', flush=True)


if __name__ == '__main__':
    main()
