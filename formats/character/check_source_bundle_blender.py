"""Original-file P2 checks. Run in a fresh background Blender, never an edited scene.

Example (supply your own paths and supported specimen):
blender --background --factory-startup --python check_source_bundle_blender.py --
  --addon-directory extracted-addon --game LMSH1 --game-root game
  --cache-root cache --source extracted-character.CD --output-root new-check-folder

The output root must be new and outside the game/cache. This checks byte-identical
no-op export/reimport, real Blender instance conflicts and a decoded native UV
edit. It does not perform in-game or visual validation and distributes no assets.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy


parser = argparse.ArgumentParser()
parser.add_argument('--addon-directory', type=Path, required=True,
                    help='Directory containing the built io_scene_tt_character package')
parser.add_argument('--game', choices=('LMSH1', 'LB3', 'HOBBIT', 'AVENGERS'), required=True)
parser.add_argument('--game-root', type=Path, required=True)
parser.add_argument('--cache-root', type=Path, required=True)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output-root', type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
args.output_root = args.output_root.resolve()
if any(args.output_root.is_relative_to(path.resolve()) for path in (args.game_root, args.cache_root)):
    parser.error('Choose output outside the game and source/cache tree')
args.output_root.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(args.addon_directory.resolve()))
import io_scene_tt_character as addon
addon.register()
from io_scene_tt_character.importer import import_character, snapshot, rollback
from io_scene_tt_character.exporter import export_sources
from io_scene_tt_character.source_bundle import canonical_source
from io_scene_tt_character._core.asset_index import open_assets
from io_scene_tt_character._core.cu3 import FormatError
from io_scene_tt_character._core.native_mesh import read_mesh_bytes


rig, _ = import_character(bpy.context, args.source, args.game_root, args.game, cache=args.cache_root)
records = json.loads(rig['tt_native_source_provenance'])['records']
baseline_folder = args.output_root / 'baseline'
baseline = export_sources(rig, baseline_folder)
for entry in baseline['files']:
    source = next(Path(path) for path, record in records.items()
                  if record['export'] and record['logical_path'] == entry['path'])
    assert (baseline_folder / entry['path']).read_bytes() == source.read_bytes(), entry['path']
assert all(item['changed_bytes'] == 0 for item in baseline['vertex_patches'].values())

# Reimport the copied fixture, then compare another no-op bundle byte for byte.
definition = rig.get('tt_native_definition') or rig['tt_native_source']
logical = records[str(Path(definition).resolve())]['logical_path']
before = snapshot()
try:
    loose = open_assets(baseline_folder, args.game)
    copied, _ = import_character(bpy.context, baseline_folder / logical, baseline_folder,
                                args.game, assets=loose)
    roundtrip_folder = args.output_root / 'roundtrip'
    roundtrip = export_sources(copied, roundtrip_folder)
    for entry in roundtrip['files']:
        assert (roundtrip_folder / entry['path']).read_bytes() == (baseline_folder / entry['path']).read_bytes()
finally:
    rollback(before)

# Duplicate this native model's direct meshes. Independent datablocks let one
# instance change without changing its peer; native rest/baseline data is retained.
meshes = [obj for obj in rig.children if obj.type == 'MESH' and obj.get('tt_vertex_transform')]
assert meshes, 'Choose a specimen with editable native body meshes'
duplicate = rig.copy()
if rig.data is not None:
    duplicate.data = rig.data.copy()
duplicate.name = rig.name + '_P2_duplicate'
bpy.context.collection.objects.link(duplicate)
duplicate.parent = rig
duplicates = []
for original in meshes:
    obj = original.copy()
    obj.data = original.data.copy()
    bpy.context.collection.objects.link(obj)
    obj.parent = duplicate
    for modifier in obj.modifiers:
        if modifier.type == 'ARMATURE' and modifier.object == rig:
            modifier.object = duplicate
    duplicates.append(obj)
bpy.context.view_layer.update()
duplicate_noop = export_sources(rig, args.output_root / 'duplicate-noop')
assert len(duplicate_noop['files']) == len(baseline['files'])
source_path = Path(rig['tt_native_source']).resolve()
source_key = str(source_path)
assert len(duplicate_noop['source_instances'][str(canonical_source(source_path))]['instances']) == 2

# Choose a native UV that can change without topology/vertex splits. Every
# display copy of that part receives the same loop coordinates within an actor.
choice = next(((obj, field, obj.data.uv_layers.get('Source ' + field + ' 0'))
               for obj in meshes for field in ('uv', 'uv2', 'uv3')
               if obj.data.loops and obj.data.uv_layers.get('Source ' + field + ' 0')), None)
assert choice, 'Choose a specimen with an editable Source UV layer'
mesh, field, layer = choice
part_id = mesh['source_part']
vertex = mesh.data.loops[0].vertex_index
old_pair = tuple(layer.data[0].uv)
new_pair = (old_pair[0] + .25, old_pair[1] + .125)


def set_uv(objects, pair):
    for obj in objects:
        if obj['source_part'] != part_id:
            continue
        uv = obj.data.uv_layers.get('Source ' + field + ' 0')
        assert uv is not None
        for loop in obj.data.loops:
            if loop.vertex_index == vertex:
                uv.data[loop.index].uv = pair
        obj.data.update()
    bpy.context.view_layer.update()


def rejects(label):
    folder = args.output_root / label
    try:
        export_sources(rig, folder)
    except FormatError as error:
        assert 'Conflicting native source instances' in str(error), error
    else:
        raise AssertionError('Inconsistent source instances were accepted: ' + label)
    assert not folder.exists()
    assert not list(args.output_root.glob('.' + label + '.tt-stage-*'))


try:
    set_uv(meshes, new_pair)
    rejects('edited-original-unchanged-copy')
    set_uv(meshes, old_pair)
    set_uv(duplicates, new_pair)
    rejects('unchanged-original-edited-copy')
    set_uv(meshes, (new_pair[0] + .25, new_pair[1]))
    rejects('divergent-edits')
    set_uv(meshes, new_pair)
    edited_folder = args.output_root / 'identical-edits'
    edited = export_sources(rig, edited_folder)
    output = (edited_folder / records[source_key]['logical_path']).read_bytes()
    source = source_path.read_bytes()
    old = read_mesh_bytes(source)
    new = read_mesh_bytes(output)
    old_part = next(part for part in old['parts'] if part['index'] == part_id)
    new_part = next(part for part in new['parts'] if part['index'] == part_id)
    assert new_part['vertices'][vertex][field] != old_part['vertices'][vertex][field]
    assert all(abs(a - b) < .01 for a, b in zip(new_part['vertices'][vertex][field][:2],
                                             (new_pair[0], 1 - new_pair[1])))
    assert new_part['triangles'] == old_part['triangles']
    assert len(output) == len(source)
    assert hashlib.sha256(source).hexdigest() == records[source_key]['sha256']
    assert len(edited['files']) == len(baseline['files'])
finally:
    set_uv(meshes, old_pair)
    set_uv(duplicates, old_pair)

result = dict(game=args.game, source=str(source_path), native_files=len(baseline['files']),
              checks=['byte-identical no-op', 'export/reimport/no-op', 'identical instances',
                      'edited/unchanged conflict in both orders', 'divergent edits',
                      'identical native UV edit decoded'],
              limitations=['No in-game or visual validation'])
(args.output_root / 'P2-check-results.json').write_text(json.dumps(result, indent=2) + '\n')
print('SOURCE_BUNDLE_P2_CHECK_PASSED', json.dumps(result), flush=True)
