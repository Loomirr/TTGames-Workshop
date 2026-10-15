"""Original-file edited exports. Run in a fresh factory-startup Blender.

blender -b --factory-startup --python check_edited_blender.py -- \
  cases.json new-output-folder --addon-directory extracted-addon

Cases use check_blender.py's source/assets/game fields. Each case tests actual
Blender edits, decoded native bytes and loose reimport. Output must be new.
This is not an in-game or visual fidelity check and contains no game assets.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import struct
import traceback
from zipfile import ZipFile

import bpy
from mathutils import Matrix, Vector


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('cases', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--addon-directory', type=Path)
    parser.add_argument('--cache-directory', type=Path,
                        help='Optional existing extraction cache, separate from output')
    parser.add_argument('--features', default='uv,color,position,normal,weights,face',
                        help='Comma-separated supported edit classes to check')
    return parser.parse_args(sys.argv[sys.argv.index('--') + 1:])


def main():
    args = arguments()
    features = args.features.split(',')
    if not features or any(feature not in ('uv', 'color', 'position', 'normal', 'weights', 'face') for feature in features):
        raise ValueError('Unknown edit class')
    output = args.output.resolve()
    cache = args.cache_directory.resolve() if args.cache_directory else output / 'cache'
    if output.is_relative_to(cache):
        raise ValueError('Output must be outside the extraction cache')
    cases = json.loads(args.cases.read_text(encoding='utf-8'))
    for case in cases:
        if any(output.is_relative_to(Path(case[name]).resolve()) for name in ('source', 'assets')):
            raise ValueError('Output must be outside source and game folders')
    output.mkdir(parents=True, exist_ok=False)
    if args.addon_directory:
        bundle = args.addon_directory.resolve()
    else:
        root = Path(__file__).resolve().parents[2]
        packages = list((root / 'builds/blender').glob('TT_Character_Importer_*.zip'))
        if len(packages) != 1:
            raise ValueError('Build exactly one current character addon')
        bundle = output / 'addon'
        with ZipFile(packages[0]) as archive:
            archive.extractall(bundle)
    sys.path.insert(0, str(bundle))
    import io_scene_tt_character as addon
    addon.register()
    from io_scene_tt_character.importer import import_character, snapshot, rollback
    from io_scene_tt_character.exporter import export_sources
    from io_scene_tt_character._core.native_model import load_model
    from io_scene_tt_character._core.native_mesh import read_mesh_bytes
    from io_scene_tt_character._core.asset_index import open_assets
    from io_scene_tt_character._core.cu3 import FormatError

    results = []
    for case in cases:
        before_case = snapshot()
        label = case['game'] + '_' + Path(case['source']).stem
        result = dict(name=label, checks=[], failures=[], limitations=[])
        results.append(result)
        try:
            print('EDITED_IMPORT', label, flush=True)
            rig, report = import_character(bpy.context, Path(case['source']), Path(case['assets']),
                                           case['game'], cache=cache)
            result['import_issues'] = report['issues']
            records = json.loads(rig['tt_native_source_provenance'])['records']
            models = [(obj, load_model(Path(obj['tt_native_source'])))
                      for obj in [rig] + list(rig.children_recursive) if obj.get('tt_native_source')]
            result['rejected_edits'] = negative_checks(rig, output / label, export_sources, FormatError)
            # Keep independent mesh copies for every edit. Restoring the original
            # datablocks restores imported custom normals and targets exactly.
            originals = {obj: obj.data for obj in rig.children_recursive if obj.type == 'MESH'}
            for feature in features:
                edited_data = []
                for obj, data in originals.items():
                    obj.data = data.copy()
                    edited_data.append(obj.data)
                old_groups = None
                try:
                    choice = choose(models, feature)
                    if choice is None:
                        result['limitations'].append(feature + ': no eligible imported part in this specimen')
                        continue
                    owner, model, part, objects, vertex = choice
                    old_groups = edit(objects, model, part, feature, vertex)
                    bpy.context.view_layer.update()
                    source = Path(owner['tt_native_source']).resolve()
                    logical = records[str(source)]['logical_path']
                    folder = output / label / feature
                    print('EDITED_WRITE', label, feature, flush=True)
                    exported = export_sources(rig, folder)
                    raw = (folder / logical).read_bytes()
                    decoded = read_mesh_bytes(raw)
                    current = decoded['parts'][part['index']]
                    if feature == 'face':
                        assert current['morphs'] != part['morphs'], 'Target edit was not encoded'
                    else:
                        assert current['vertices'][vertex][feature] != part['vertices'][vertex][feature], 'Edit was not encoded'
                    assert len(raw) == source.stat().st_size
                    assert current['triangles'] == part['triangles']
                    assert current['palette'] == part['palette']
                    assert hashlib.sha256(source.read_bytes()).hexdigest() == records[str(source)]['sha256']
                    # Reimport the exported CD, including every copied companion.
                    imported_source = Path(rig.get('tt_character_definition') or rig['tt_native_source']).resolve()
                    source_logical = records[str(imported_source)]['logical_path']
                    before_copy = snapshot()
                    try:
                        loose = open_assets(folder, case['game'])
                        copied, copied_report = import_character(bpy.context, folder / source_logical,
                                                                folder, case['game'], assets=loose)
                        assert len([o for o in copied.children_recursive if o.type == 'MESH']) == len(originals)
                        # Optional attachments already unsupported at import are
                        # omitted from the source ledger. Reimport must not lose
                        # any additional attachment; retain original omissions.
                        original_omissions = {i.split(':', 1)[0] for i in report['issues'] if i.startswith('Attachment ')}
                        copied_omissions = {i.split(':', 1)[0] for i in copied_report['issues'] if i.startswith('Attachment ')}
                        assert copied_omissions == original_omissions, copied_report['issues']
                    finally:
                        rollback(before_copy)
                    manifests = exported['face_patches'] if feature == 'face' else exported['vertex_patches']
                    result['checks'].append(dict(feature=feature, source=source.name, part=part['index'],
                                                  changed_bytes=sum(a != b for a, b in zip(source.read_bytes(), raw)),
                                                  reimport=True, manifest_count=len(manifests)))
                except Exception as error:
                    result['failures'].append(dict(feature=feature, error=str(error), traceback=traceback.format_exc()))
                finally:
                    if old_groups is not None:
                        for obj, groups in old_groups:
                            for group in list(obj.vertex_groups):
                                obj.vertex_groups.remove(group)
                            for name, weights in groups:
                                group = obj.vertex_groups.new(name=name)
                                for index, weight in weights:
                                    group.add([index], weight, 'REPLACE')
                    for obj, data in originals.items():
                        obj.data = data
                    for data in edited_data:
                        if data.users == 0:
                            bpy.data.meshes.remove(data)
            # Viewing copies add facial clipping/depth modifiers, preserve the
            # native meshes and should not be mistaken for new source geometry.
            previous_scene = bpy.context.window.scene
            preview_scene = None
            try:
                from io_scene_tt_character.preview import create_preview
                create_preview(bpy.context, rig)
                preview_scene = bpy.context.window.scene
                preview_rig = next(obj for obj in preview_scene.objects if obj.get('tt_character_assets_root'))
                preview_folder = output / label / 'live-preview'
                print('EDITED_WRITE', label, 'live-preview', flush=True)
                preview_export = export_sources(preview_rig, preview_folder)
                assert preview_export['assembly_inventory']['checked']
                for entry in preview_export['files']:
                    source = next(Path(path) for path, record in records.items() if record['logical_path'] == entry['path'])
                    assert (preview_folder / entry['path']).read_bytes() == source.read_bytes(), entry['path']
                result['live_preview_noop'] = True
            except Exception as error:
                result['failures'].append(dict(feature='live-preview', error=str(error), traceback=traceback.format_exc()))
            finally:
                bpy.context.window.scene = previous_scene
                if preview_scene:
                    bpy.data.scenes.remove(preview_scene)
        except Exception as error:
            result['failures'].append(dict(feature='import', error=str(error), traceback=traceback.format_exc()))
        finally:
            rollback(before_case)
            (output / 'edited-validation.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
            print('EDITED_CASE', label, 'passed', len(result['checks']), 'failures', len(result['failures']), flush=True)
    failures = [entry for result in results for entry in result['failures']]
    if failures:
        raise AssertionError(str(len(failures)) + ' edited export checks failed; see edited-validation.json')
    print('EDITED_EXPORT_CHECK_PASSED', len(results), flush=True)


def negative_checks(rig, output, export_sources, error_type):
    """Each unsupported edit must fail before publishing any output."""
    tested = []
    meshes = [obj for obj in rig.children_recursive if obj.type == 'MESH']
    mesh = meshes[0]

    def rejects(label, message):
        destination = output / ('rejected-' + label)
        try:
            export_sources(rig, destination)
        except error_type as error:
            assert message in str(error), str(error)
        else:
            raise AssertionError('Unsupported edit accepted: ' + label)
        assert not destination.exists()
        assert not list(output.glob('.rejected-' + label + '.tt-stage-*'))
        tested.append(label)

    parent = mesh.parent
    try:
        mesh.parent = None
        rejects('detached-mesh', 'meshes were added, removed')
    finally:
        mesh.parent = parent
    extra = mesh.copy()
    bpy.context.scene.collection.objects.link(extra)
    try:
        extra.parent = parent
        rejects('duplicate-draw', 'duplicated')
    finally:
        bpy.data.objects.remove(extra, do_unlink=True)
    data = bpy.data.meshes.new('Unsupported extra geometry')
    extra = bpy.data.objects.new('Unsupported extra geometry', data)
    bpy.context.scene.collection.objects.link(extra)
    try:
        extra.parent = rig
        rejects('new-mesh', 'New or unbound mesh')
    finally:
        bpy.data.objects.remove(extra, do_unlink=True)
        bpy.data.meshes.remove(data)
    attachment = next((obj for obj in rig.children_recursive if obj.get('tt_native_source')), None)
    if attachment is not None:
        parent = attachment.parent
        try:
            attachment.parent = None
            rejects('detached-attachment', 'attachment was removed or detached')
        finally:
            attachment.parent = parent
    material = next((m for obj in meshes for m in obj.data.materials if m and m.use_nodes), None)
    if material is not None:
        before = tuple(material.diffuse_color)
        try:
            material.diffuse_color = (0, 1, 0, .25)
            rejects('material-edit', 'Material edits cannot yet be encoded')
        finally:
            material.diffuse_color = before
    before_data = mesh.data
    changed = before_data.copy()
    try:
        mesh.data = changed
        changed.clear_geometry()
        rejects('topology-edit', 'topology or vertex order changed')
    finally:
        mesh.data = before_data
        bpy.data.meshes.remove(changed)
    return tested


def choose(models, feature):
    for owner, model in models:
        by_part = {}
        for obj in owner.children:
            if obj.type == 'MESH' and obj.get('tt_vertex_transform'):
                by_part.setdefault(obj['source_part'], []).append(obj)
        for part_id, objects in by_part.items():
            part = model['parts'][part_id]
            if not part['vertices'] or not objects[0].data.loops:
                continue
            vertex = objects[0].data.loops[0].vertex_index
            native = part['vertices'][vertex]
            if feature == 'face':
                if not part['morphs'] or not part['morphs']['targets'] or len(objects) != 1:
                    continue
                editable = face_vertex(model, part)
                if editable is None:
                    continue
                vertex = editable
            elif feature == 'position':
                if part['morphs']:
                    continue
                bounds = [(min(v['position'][i] for v in part['vertices']), max(v['position'][i] for v in part['vertices'])) for i in range(3)]
                if not any(hi - lo > .01 for lo, hi in bounds):
                    continue
            elif feature == 'normal':
                if 'normal' not in native or 'TT_NativeNormalBaseline' not in objects[0].data.attributes:
                    continue
            elif feature == 'weights':
                if not model['skeleton'] or len(part['palette']) < 2 or any(o['tt_native_rigid_joint'] >= 0 for o in objects):
                    continue
                if sum(w for ix, w in zip(native['indices'], native['packed_weights']) if ix != 255) != 255:
                    continue
            elif feature not in native:
                continue
            return owner, model, part, objects, vertex


def face_vertex(model, part):
    """Choose a target coordinate that does not require native run splitting."""
    raw = Path(model['source']).read_bytes()
    for target in part['morphs']['targets']:
        if target['encoding'] == 'dense_be_vec3':
            return target['id'], 0
        size_at = target['record_offset'] + (8 if model['mesh_version'] == 175 else 17)
        size = struct.unpack_from('>I', raw, size_at)[0]
        index = 0
        for at in range(size_at + 4, size_at + 4 + size, 16):
            count = struct.unpack_from('>I', raw, at)[0]
            if count == 1:
                return target['id'], index
            index += count
    return None


def edit(objects, model, part, feature, vertex):
    native = part['vertices'][vertex] if feature != 'face' else None
    saved_groups = None
    if feature == 'weights':
        saved_groups = []
        for obj in objects:
            saved_groups.append((obj, [(g.name, [(v.index, ref.weight) for v in obj.data.vertices
                                                 for ref in v.groups if ref.group == g.index]) for g in obj.vertex_groups]))
    for obj in objects:
        if feature == 'uv':
            layer = obj.data.uv_layers['Source uv 0']
            for loop in obj.data.loops:
                if loop.vertex_index == vertex:
                    layer.data[loop.index].uv.x += .125
        elif feature == 'color':
            color = obj.data.color_attributes['SourceColor'].data[vertex]
            value = list(color.color_srgb)
            value[0] = 0 if value[0] > .5 else 1
            color.color_srgb = value
        elif feature == 'position':
            old = Vector(native['position'][:3])
            center = Vector(tuple((min(v['position'][i] for v in part['vertices']) + max(v['position'][i] for v in part['vertices'])) / 2 for i in range(3)))
            obj.data.vertices[vertex].co = Matrix(json.loads(obj['tt_vertex_transform'])) @ old.lerp(center, .05)
        elif feature == 'normal':
            normals = [n.vector.copy() for n in obj.data.corner_normals]
            base = next(normals[l.index] for l in obj.data.loops if l.vertex_index == vertex)
            new = (base + Vector((.07, -.03, .05))).normalized()
            for loop in obj.data.loops:
                if loop.vertex_index == vertex:
                    normals[loop.index] = new
            obj.data.normals_split_custom_set(normals)
        elif feature == 'weights':
            for group in obj.vertex_groups:
                group.remove([vertex])
            old = dict(native['weights'])
            joint = next((j for j in part['palette'] if old.get(j, 0) != 1), part['palette'][0])
            name = model['skeleton']['joints'][joint]['name']
            group = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
            group.add([vertex], 1, 'REPLACE')
        elif feature == 'face':
            target, index = vertex
            key = obj.data.shape_keys.key_blocks[f'TT_Target_{target:03d}']
            key.data[index].co.x += .001
        obj.data.update()
    return saved_groups


if __name__ == '__main__':
    main()
