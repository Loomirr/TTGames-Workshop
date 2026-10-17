"""Original-file check of the 'Mirror to game handedness' import option.

User-supplied game files stay outside Git. Run against an extracted addon ZIP:
blender -b --factory-startup --python formats/character/check_game_handedness_blender.py -- \
  --addon-directory <extracted zip> --game-root <game> --game LB3 --cache-root <cache> --output-root <new folder> \
  --character B66ROBIN

Checks, for one character imported without and with the option:
- without it, Left* bones lie at +X while the character faces +Y (mirrored relative to the game);
- with it, the character object is mirrored on X and Left* bones lie at -X;
- exporting both imports writes byte-identical files (native data is unchanged).
"""
import argparse, hashlib, sys
from pathlib import Path
import bpy

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--addon-directory', required=True, type=Path)
p.add_argument('--game-root', required=True, type=Path)
p.add_argument('--game', default='LB3')
p.add_argument('--cache-root', required=True, type=Path)
p.add_argument('--output-root', required=True, type=Path)
p.add_argument('--character', default='B66ROBIN')
args = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
args.output_root = args.output_root.resolve()
if any(args.output_root.is_relative_to(root.resolve()) for root in (args.game_root, args.cache_root)):
    p.error('Choose an output root outside the game and source/cache tree')
args.output_root.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(args.addon_directory))
import io_scene_tt_character as addon
addon.register()
from io_scene_tt_character.importer import import_character
from io_scene_tt_character.exporter import export_sources
from io_scene_tt_character._core.asset_index import open_assets

assets = open_assets(args.game_root, args.game, args.cache_root)
cd = assets.find(args.character, extension='.CD')


def digest(folder):
    h = hashlib.sha256()
    for path in sorted(folder.rglob('*')):
        if path.is_file():
            h.update(path.relative_to(folder).as_posix().encode()); h.update(path.read_bytes())
    return h.hexdigest()


results = {}
for mirrored in (False, True):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rig, _ = import_character(bpy.context, cd, args.game_root, args.game, cache=args.cache_root, assets=assets,
                              game_handedness=mirrored)
    left = [(rig.matrix_world @ bone.head).x for bone in rig.pose.bones if bone.name.startswith('Left')]
    if not left:
        raise AssertionError('No Left* bones to check')
    side = sum(left) / len(left)
    if (side < 0) != mirrored:
        raise AssertionError(f'Left bones at mean x {side:.4f} with game_handedness={mirrored}')
    if bool(rig.get('tt_game_handedness')) != mirrored or (rig.scale.x < 0) != mirrored:
        raise AssertionError('Mirror flag or object scale does not match the option')
    folder = args.output_root / ('mirrored' if mirrored else 'native')
    export_sources(rig, folder)
    results[mirrored] = digest(folder)
if results[False] != results[True]:
    raise AssertionError('Export differs when the import is mirrored')
print('Game handedness check passed:', args.character, results[True][:16])
