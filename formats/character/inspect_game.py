"""Inventory installed character/animation sources and probe versioned readers.

This research tool does not claim Blender model support for inventory profiles.
All requested assets go to a separate cache. No installed files are modified.
"""
import argparse
import json
from pathlib import Path
import sys
import types

CORE = Path(__file__).resolve().parents[1] / 'cu3/Addon/io_scene_lego_cu3'
package = types.ModuleType('tt_character_inspect')
package.__path__ = [str(CORE)]
sys.modules[package.__name__] = package
from tt_character_inspect.asset_index import open_assets
from tt_character_inspect.an4 import AnimationFile
from tt_character_inspect.definitions import character_definition
from tt_character_inspect.animation_catalog import catalog


def inspect(root, game, cache, character='', samples=5):
    assets = open_assets(root, game, cache)
    paths = sorted({row[1]['path'] if isinstance(row, tuple) else row.relative_to(assets.root).as_posix()
                    for rows in assets.files.values() for row in rows})
    report = dict(game=game, source=str(Path(root).resolve()),
        files={suffix:[p for p in paths if p.lower().endswith(suffix)] for suffix in ('.cd','.ghg','.gsc','.as','.an4','.pak')},
        probes=[], limitations=['Archive inventory and reader probes do not establish faithful model rendering or animation playback.'])
    candidates = [p for p in report['files']['.an4'] if not character or character.casefold() in p.casefold()]
    for name in candidates[:samples]:
        row = dict(path=name)
        try:
            source = AnimationFile(assets.find_exact(name))
            row.update(version=source.version, actors=[])
            for actor in source.actors:
                for record in actor['records']:
                    anim = record['animation']
                    item = dict(actor=actor['name'], clip=record['name'], nodes=anim.nodes, format=anim.header()['format'])
                    try:
                        anim.prepare(scene_channels=True)
                        item['sampled_finite'] = all(__import__('math').isfinite(v) for frame in (0,anim.frames//2,anim.frames-1) for node in anim.sample(frame) for v in node)
                    except ValueError as error:
                        item['unsupported'] = str(error)
                    row['actors'].append(item)
        except (ValueError, OSError) as error:
            row['unsupported'] = str(error)
        report['probes'].append(row)
    if character:
        matching = [p for p in report['files']['.cd'] if Path(p).stem.casefold() == character.casefold()]
        if len(matching) == 1:
            try:
                definition = character_definition(assets.find_exact(matching[0]))
                report['character'] = dict(path=matching[0], version=definition['version'], animations=catalog(assets, definition))
            except ValueError as error:
                report['character'] = dict(path=matching[0], unsupported=str(error))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game', choices=['LB3','LMSH1','AVENGERS','TFA','DCSV','LMSH2','HOBBIT','LOTR'])
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--character', default='')
    parser.add_argument('--samples', type=int, default=5)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output report')
    if not 0 <= args.samples <= 100:
        parser.error('--samples must be 0..100')
    result = inspect(args.root,args.game,args.cache,args.character,args.samples)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps(dict(game=args.game, counts={k:len(v) for k,v in result['files'].items()}, probes=len(result['probes'])),indent=2))
