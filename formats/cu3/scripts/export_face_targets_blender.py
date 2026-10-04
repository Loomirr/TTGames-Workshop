"""Run with Blender --background FILE.blend --python THIS.py -- [options]."""
from pathlib import Path
import argparse
import json
import sys
import types
import bpy
ROOT = Path(__file__).resolve().parent.parent
pkg = types.ModuleType('io_scene_lego_cu3')
pkg.__path__ = [str(ROOT / 'Addon/io_scene_lego_cu3')]
sys.modules[pkg.__name__] = pkg
from io_scene_lego_cu3.face_edit_blender import edited_companion
from io_scene_lego_cu3.face_edit import patch_targets


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--ghg', type=Path, required=True)
    ap.add_argument('--morph', type=Path, required=True)
    ap.add_argument('--collection', required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    original = json.loads(args.morph.read_text())
    collection = bpy.data.collections.get(args.collection)
    if not collection:
        ap.error('Editing collection is missing')
    edited = edited_companion(collection.all_objects, original)
    raw, report = patch_targets(args.ghg.read_bytes(), edited)
    paths = [args.output, args.output.with_suffix('.edited.morph.json'),
             args.output.with_suffix(args.output.suffix + '.patch.json')]
    inputs = {args.ghg.resolve(), args.morph.resolve(), Path(bpy.data.filepath).resolve()}
    if any(p.exists() or p.resolve() in inputs for p in paths):
        ap.error('Outputs must be new files, separate from all inputs')
    with paths[0].open('xb') as stream:
        stream.write(raw)
    with paths[1].open('x') as stream:
        json.dump(edited, stream, separators=(',', ':'))
    report.update(source=str(args.ghg.resolve()), blend=bpy.data.filepath,
                  collection=args.collection, output=str(args.output.resolve()))
    with paths[2].open('x') as stream:
        json.dump(report, stream, indent=2)
    print('FACE_EXPORT_VERIFIED', report['changed_bytes'], 'bytes;', len(report['targets']), 'part targets')


if __name__ == '__main__':
    main()
