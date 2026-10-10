"""Check every declared character's native model dependencies, without Blender.

This is a parser/preflight audit, not a visual or in-game fidelity test.
Requested assets are read into a separate cache; installed files stay intact.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import types

CORE = Path(__file__).resolve().parents[1] / 'cu3/Addon/io_scene_lego_cu3'
package = types.ModuleType('tt_character_audit')
package.__path__ = [str(CORE)]
sys.modules[package.__name__] = package
from tt_character_audit.asset_index import open_assets
from tt_character_audit.definitions import character_definition
from tt_character_audit.native_mesh import read_mesh
from tt_character_audit.native_display import read_display
from tt_character_audit.native_materials import read_materials
from tt_character_audit.skeleton import read_skeleton
from tt_character_audit.native_layers import selected_layer_metadata
from tt_character_audit.dependencies import active_attachments, find_character_asset

PROFILES = ('LMSH1', 'LB3', 'AVENGERS', 'TFA', 'DCSV', 'LMSH2', 'LOTR', 'HOBBIT')


def audit(root, game, cache, limit=0):
    assets = open_assets(root, game, cache)
    paths = sorted({row[1]['path'] if isinstance(row, tuple) else row.relative_to(assets.root).as_posix()
                    for name, rows in assets.files.items() if name.endswith('.cd') for row in rows})
    # Include the separate minifig families used by earlier and later games.
    paths = [p for p in paths if any(c in '/' + p.upper() for c in ('/MINIFIG', '/SMALL/', '/BIGFIG', '/BIGGERFIG', '/CREATURE')) and '/SUPER_CHAR' not in p.upper()]
    suffix = '_NXG' if game in ('LMSH1', 'LOTR', 'HOBBIT') else '_DX11'
    models = {}
    records = []

    def model(reference):
        source = (find_character_asset(assets, reference, suffix, '.GHG', required=False) or
                  find_character_asset(assets, reference, suffix, '.GSC'))
        key = str(source)
        if key not in models:
            value = {}
            for stage, reader in [('mesh', lambda: read_mesh(source)),
                                  ('skeleton', lambda: read_skeleton(source) if source.suffix.lower() == '.ghg' else None),
                                  ('materials', lambda: read_materials(source))]:
                try:
                    value[stage] = reader()
                except (ValueError, OSError, KeyError) as error:
                    value[stage + '_error'] = str(error)
            if 'mesh' in value:
                try:
                    value['display'] = read_display(source, len(value['mesh']['parts']))
                except (ValueError, OSError) as error:
                    value['display_error'] = str(error)
            models[key] = value
        return source, models[key]

    for path in paths[:limit or None]:
        row = dict(character=path, issues=[], attachments=[])
        try:
            definition = character_definition(assets.find_exact(path))
            row['definition_version'] = definition['version']
            fields = definition['character']
            source, parsed = model(fields.get('Override Model File') or fields['Skeleton Name'])
            row['model'] = source.name
            row['issues'].extend(f'{k}: {v}' for k, v in parsed.items() if k.endswith('_error'))
            if all(k in parsed for k in ('mesh', 'display', 'skeleton', 'materials')):
                skeleton = parsed['skeleton']
                selected = selected_layer_metadata(skeleton, parsed['display'], definition, layer_mode='default') if skeleton else []
                draws = [(m, b) for m in selected for b in parsed['display']['specials'][m['special']]['parts']]
                if skeleton:
                    if not draws:
                        raise ValueError('Default costume has no visible model draws')
                    for metadata, binding in draws:
                        part = parsed['mesh']['parts'][binding['part']]
                        if not metadata['kind'] and metadata['joint'] >= len(skeleton['joints']):
                            raise ValueError('Rigid joint index outside skeleton')
                        if metadata['kind'] and any(not v.get('weights') or any(j >= len(skeleton['joints']) for j, w in v['weights']) for v in part['vertices']):
                            raise ValueError('Unresolved native skin palette')
                        if binding['material'] >= len(parsed['materials']['materials']):
                            raise ValueError('Draw material outside table')
                    row['joints'] = len(skeleton['joints'])
                    row['selected_draws'] = len(draws)
            for attachment in active_attachments(definition, layer_mode='default', renderer_suffix=suffix):
                item = {'reference': attachment['Resource File']}
                try:
                    cd = find_character_asset(assets, item['reference'], extension='.CD', required=False)
                    ad = character_definition(cd) if cd else None
                    ref = (ad['character'].get('Override Model File') or ad['character']['Skeleton Name']) if ad else item['reference']
                    ap, am = model(ref)
                    item.update(model=ap.name, issues=[f'{k}: {v}' for k, v in am.items() if k.endswith('_error')])
                except (ValueError, OSError, KeyError) as error:
                    item['issues'] = [str(error)]
                row['attachments'].append(item)
        except (ValueError, OSError, KeyError) as error:
            row['issues'].append(str(error))
        row['parser_ready'] = not row['issues'] and not any(a.get('issues') for a in row['attachments'])
        records.append(row)
        if len(records) % 50 == 0:
            print(f'{game}: {len(records)}/{min(limit or len(paths), len(paths))} checked', flush=True)
    return dict(game=game, discovered=len(paths), checked=len(records),
                parser_ready=sum(r['parser_ready'] for r in records), unique_models=len(models),
                failure_counts=dict(Counter(e for r in records for e in r['issues'])),
                attachment_failure_counts=dict(Counter(e for r in records for a in r['attachments'] for e in a.get('issues',[]))), characters=records,
                limitations=['Parser-ready does not establish Blender rendering, costume textures, animation fidelity or in-game correctness.',
                             'Attachment models are probed; recursive attachment configuration and texture companions need Blender checks.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game', choices=PROFILES)
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    if args.output.exists() or args.limit < 0:
        parser.error('Choose a new output and a nonnegative limit (0 means every character)')
    result = audit(args.root, args.game, args.cache, args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('characters','failure_counts')}, indent=2))
