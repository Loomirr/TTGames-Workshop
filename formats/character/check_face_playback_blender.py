"""Check original-file facial playback against native BSA values in Blender.

Requires user-owned inputs. Example:
blender --background --factory-startup --python-exit-code 1 --python
formats/character/check_face_playback_blender.py -- --addon extracted-addon-folder
--cases cases.json --output new-results-folder

cases.json is a list of objects with game, root, character, and optional set/clip.
clip defaults to Idle; set is an exact animation-set name when supplied. A row
with no matching facial tracks is reported as unavailable, not counted as a pass.
This checks playback values and mesh movement, not shader fidelity or export.
"""
import argparse
import json
from pathlib import Path
import sys
import traceback

import bpy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addon', type=Path, required=True)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.addon.resolve()))
    import io_scene_tt_character as addon
    addon.register()
    from io_scene_tt_character.importer import import_character, import_catalog_entry
    from io_scene_tt_character._core.asset_index import open_assets
    from io_scene_tt_character._core.animation_bank import AnimationBank
    from io_scene_tt_character._core.an4 import AnimationFile

    results = []
    for case in json.loads(args.cases.read_text(encoding='utf-8')):
        row = {'game': case['game'], 'character': case['character']}
        try:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            assets = open_assets(Path(case['root']), case['game'], args.output/'cache')
            rig, imported = import_character(bpy.context,
                assets.find(case['character'], extension='.CD'), assets.root,
                case['game'], assets=assets)
            row['import_issues'] = imported['issues']
            entries = [json.loads(item.payload) for item in rig.tt_animation_assets]
            wanted = case.get('clip', 'Idle').casefold()
            entries = [entry for entry in entries if entry.get('source') and
                       entry['name'].casefold() == wanted and
                       (not case.get('set') or entry['set'] == case['set'])]
            entries.sort(key=lambda entry: (case['character'].casefold() not in entry['set'].casefold(),
                                           not entry['active'], entry['set']))
            if not entries:
                raise ValueError('No matching declared animation entry')
            entry = entries[0]
            report = import_catalog_entry(bpy.context, rig, entry)
            row.update(set=entry['set'], clip=entry['clip'], animation_report=report)
            if not report['imported']:
                raise ValueError('The selected body clip did not import')
            clip = rig.tt_clips[rig.tt_clip_index]
            tracks = json.loads(clip.action.get('tt_facial_actions', '[]'))
            row['facial_tracks'] = len(tracks)
            summary = report['clips'][0]['facial_playback']
            assert summary['mesh_tracks'] == len(tracks)
            assert json.loads(clip.action['tt_facial_playback']) == summary
            assert clip.action['tt_animation_report'] in bpy.data.texts
            if case.get('expected_face_status'):
                assert summary['status'] == case['expected_face_status'], summary
            if not tracks:
                row['status'] = 'facial playback unavailable for selected clip'
            else:
                data = AnimationBank(entry['source']).read(entry['member']) if entry['member'] else None
                source = AnimationFile(entry['source'], data=data)
                checked, moving = 0, 0
                maximum_error = 0.0
                for track in tracks:
                    obj = bpy.data.objects[track['object']]
                    owner = json.loads(obj.parent.animation_data.action['tt_animation_ownership'])
                    actor = next(a for a in source.actors if a['index'] == owner['actor_index'])
                    morph = source.morph_animation(actor)
                    keys = [key for key in obj.data.shape_keys.key_blocks if key.name.startswith('TT_Target_')]
                    first_values = first_vertices = None
                    has_motion = False
                    for frame in range(1, clip.frames+1):
                        bpy.context.scene.frame_set(frame)
                        expected = morph.sample(frame-1)[0]
                        values = tuple(key.value for key in keys)
                        for key in keys:
                            error = abs(key.value - expected[int(key.name.rsplit('_', 1)[1])])
                            maximum_error = max(maximum_error, error)
                            if error > 1e-5:
                                raise AssertionError(f'{obj.name}: frame {frame}, {key.name}, error {error}')
                            checked += 1
                        # Deformed geometry is checked only when the shape-key values change.
                        if first_values is None or values != first_values and not has_motion:
                            evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                            vertices = tuple(tuple(v.co) for v in evaluated.data.vertices)
                            if first_values is None:
                                first_values, first_vertices = values, vertices
                            else:
                                has_motion = any(abs(a-b) > 1e-7 for v, w in zip(vertices, first_vertices)
                                                 for a, b in zip(v, w))
                    moving += int(has_motion)
                row.update(status='native facial values match Blender playback',
                           sampled_values=checked, maximum_error=maximum_error,
                           meshes_with_evaluated_motion=moving)
        except Exception as error:
            row.update(status='failed', error=str(error))
            traceback.print_exc()
        results.append(row)
        (args.output/'results.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
        print('FACE_PLAYBACK_CASE', json.dumps(row), flush=True)
    (args.output/'results.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
    if any(row['status'] == 'failed' for row in results):
        raise RuntimeError('One or more original-file facial playback checks failed')


if __name__ == '__main__':
    main()
