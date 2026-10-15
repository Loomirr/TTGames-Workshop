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
from functools import lru_cache
from tt_character_audit.native_model import load_model, selected_draws
from tt_character_audit.model_validation import validate_draw
from tt_character_audit.skeleton import attachment_locator
from tt_character_audit.dependencies import active_attachments, find_character_asset, ResourceResolver
from tt_character_audit.profiles import CHARACTER_PROFILES, validate_profile_model, inspection_profile

PROFILES = ('LMSH1', 'LB3', 'AVENGERS', 'TFA', 'DCSV', 'LMSH2', 'LOTR', 'HOBBIT')


def audit(root, game, cache, limit=0, *, contains='', layer_mode='default'):
    if limit < 0 or layer_mode not in ('default','cutscene','authored'):
        raise ValueError('Invalid character audit limit or layer mode')
    try:
        assets = open_assets(root, game, cache)
    except (ValueError, OSError) as error:
        return dict(game=game, status='asset_index_failed', discovered=0, checked=0,
                    parser_ready=0, unique_models=0, characters=[],
                    failure_counts={str(error):1}, attachment_failure_counts={},
                    diagnostic=getattr(error,'diagnostics',None),
                    limitations=['No characters were inspected because the asset index could not be opened.'])
    paths = sorted({row[1]['path'] if isinstance(row, tuple) else row.relative_to(assets.root).as_posix()
                    for name, rows in assets.files.items() if name.endswith('.cd') for row in rows})
    # Include the separate minifig families used by earlier and later games.
    paths = [p for p in paths if any(c in '/' + p.upper() for c in ('/MINIFIG', '/SMALL/', '/BIGFIG', '/BIGGERFIG', '/CREATURE')) and '/SUPER_CHAR' not in p.upper()]
    discovered = len(paths)
    paths = [p for p in paths if contains.casefold() in p.casefold()]
    suffix = inspection_profile(game)['model_suffix']
    resolver = ResourceResolver(assets, game) if game in CHARACTER_PROFILES else None
    models = set()
    records = []

    def resolve(definition, path, reference=None):
        if resolver:
            return resolver.resolve_definition_model(definition, path) if definition else resolver.resolve_model(reference)
        fields = definition['character'] if definition else {}
        reference = fields.get('Override Model File') or fields.get('Skeleton Name') or reference
        return (find_character_asset(assets, reference, suffix, '.GHG', required=False) or
                find_character_asset(assets, reference, suffix, '.GSC'))

    @lru_cache(maxsize=4)
    def model(source):
        # Bounded cache: a full roster should not retain every decoded vertex.
        models.add(str(source))
        return load_model(source)

    def check(source, definition, row, chain=()):
        if source in chain or len(chain) > 8:
            raise ValueError('Cyclic or excessively nested character attachments')
        parsed = model(source)
        if resolver:
            validate_profile_model(game, source, parsed['mesh_version'])
        draws = selected_draws(parsed, definition, layer_mode=layer_mode, highest_detail=True)
        if not draws:
            raise ValueError('Selected costume has no visible model draws')
        for _, binding, metadata in draws:
            validate_draw(parsed, binding, metadata['joint'] if metadata and not metadata['kind'] else None)
        skeleton = parsed['skeleton']
        row.update(model=source.name, joints=len(skeleton['joints']) if skeleton else 0,
                   selected_draws=len(draws), mesh_version=parsed['mesh_version'],
                   material_versions=parsed['validation']['material_versions'])
        if not definition or not skeleton:
            return
        for attachment in active_attachments(definition, layer_mode=layer_mode, renderer_suffix=suffix):
            item = dict(reference=attachment['Resource File'], issues=[], attachments=[])
            row['attachments'].append(item)
            try:
                attachment_locator(skeleton, attachment['Locator'])
                cd = find_character_asset(assets, item['reference'], extension='.CD', required=False)
                ad = character_definition(cd) if cd else None
                check(resolve(ad, cd, item['reference']), ad, item, chain + (source,))
            except (ValueError, OSError, KeyError) as error:
                item['issues'].append(str(error))

    def issues(row):
        return row['issues'] + [e for a in row['attachments'] for e in issues(a)]

    for path in paths[:limit or None]:
        row = dict(character=path, issues=[], attachments=[])
        try:
            cd = assets.find_exact(path)
            definition = character_definition(cd)
            row['definition_version'] = definition['version']
            check(resolve(definition, cd), definition, row)
        except (ValueError, OSError, KeyError) as error:
            row['issues'].append(str(error))
        row['parser_ready'] = not issues(row)
        records.append(row)
        if len(records) % 50 == 0:
            print(f'{game}: {len(records)}/{min(limit or len(paths), len(paths))} checked', flush=True)
    return dict(game=game, status='completed', discovered=discovered, matching=len(paths),
                contains=contains, layer_mode=layer_mode, checked=len(records),
                parser_ready=sum(r['parser_ready'] for r in records), unique_models=len(models),
                failure_counts=dict(Counter(e for r in records for e in r['issues'])),
                attachment_failure_counts=dict(Counter(e for r in records for a in r['attachments'] for e in issues(a))), characters=records,
                limitations=['Parser-ready does not establish Blender rendering, costume textures, animation fidelity or in-game correctness.',
                             'Uses importer model ownership, highest-detail selection, recursive attachment and locator checks. Texture companions and rendering still need Blender checks.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game', choices=PROFILES)
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--contains', default='', help='Case-insensitive logical character path filter')
    parser.add_argument('--layer-mode', choices=('default','cutscene','authored'), default='default')
    args = parser.parse_args()
    if args.output.exists() or args.limit < 0:
        parser.error('Choose a new output and a nonnegative limit (0 means every character)')
    result = audit(args.root, args.game, args.cache, args.limit, contains=args.contains, layer_mode=args.layer_mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('characters','failure_counts')}, indent=2))
    if result['status'] != 'completed':sys.exit(2)
