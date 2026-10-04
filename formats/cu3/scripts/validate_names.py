"""Manually check name relocation on supplied files without writing game data."""
import argparse
import json
from pathlib import Path
from cu3_name_editor import Cutscene, FormatError, inventory, rewrite_names


def verify(path):
    cut = Cutscene(path)
    if not cut.actors:
        return dict(file=path.name, status='skipped', reason='No actor tree')
    assert rewrite_names(cut)[0] == path.read_bytes(), 'No-op changed bytes'
    entries = inventory(cut)
    actor = next((a for a in cut.actors if a['parent'] is None), cut.actors[0])
    name = 'Instance_Character_With_A_Much_Longer_Name_For_Testing'
    objects = {entries['objects'][0]['index']: 'Instance_Object_With_A_Much_Longer_Name_For_Testing'} if entries['objects'] else {}
    data, report = rewrite_names(cut, {actor['index']: name}, objects)
    changed = Cutscene(path, data=data)
    assert changed.actors[actor['index']]['name'] == name
    assert report['preserved_original_animation_blob']
    again, _ = rewrite_names(changed, {actor['index']: name + '_Again'})
    assert Cutscene(path, data=again).actors[actor['index']]['name'].endswith('_Again')
    record = next((a for a in cut.actors if a['records']), None)
    if record:
        ri = record['records'][0]['index']
        data, _ = rewrite_names(cut, record_names={(record['index'], ri): 'Longer_Animation_Record_Name_For_Testing'})
        assert Cutscene(path, data=data).actors[record['index']]['records'][0]['name'] == 'Longer_Animation_Record_Name_For_Testing'
    duplicate = next((a for a in cut.actors if sum(b['name'] == a['name'] for b in cut.actors) > 1), None)
    if duplicate:
        data, _ = rewrite_names(cut, {duplicate['index']: name})
        changed = Cutscene(path, data=data)
        for before, after in zip(cut.actors, changed.actors):
            if before['index'] != duplicate['index']:
                assert before['name'] == after['name'], 'Shared string changed another actor'
    for invalid in ('', 'Embedded\0Nul', 'NonASCII_\u2603', 'x' * 256):
        try:
            rewrite_names(cut, {actor['index']: invalid})
        except FormatError:
            continue
        raise AssertionError('Invalid name accepted')
    return dict(file=path.name, status='passed', version=cut.version, actors=len(cut.actors),
                objects_tested=len(objects), growth_bytes=report['growth_bytes'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    args = parser.parse_args()
    paths = [args.input] if args.input.is_file() else sorted(p for p in args.input.rglob('*') if p.suffix.lower() == '.cu3')
    if not paths:
        parser.error('No CU3 files found')
    rows = []
    for path in paths:
        try:
            rows.append(verify(path))
        except (ValueError, OSError, AssertionError, RecursionError) as error:
            rows.append(dict(file=path.name, status='rejected', reason=str(error)))
    print(json.dumps(rows, indent=2))
    if any(row['status'] == 'rejected' for row in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
