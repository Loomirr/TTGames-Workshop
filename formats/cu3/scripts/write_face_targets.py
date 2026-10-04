"""Patch edited vertex offsets into a separate, hash-locked native GHG copy."""
from pathlib import Path
import argparse
import json
import sys
import types
ROOT = Path(__file__).resolve().parent.parent
pkg = types.ModuleType('io_scene_lego_cu3')
pkg.__path__ = [str(ROOT / 'Addon/io_scene_lego_cu3')]
sys.modules[pkg.__name__] = pkg
from io_scene_lego_cu3.face_edit import patch_targets
from io_scene_lego_cu3.cu3 import FormatError


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('ghg', type=Path)
    ap.add_argument('--edited', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    report_path = args.output.with_suffix(args.output.suffix + '.patch.json')
    inputs = {args.ghg.resolve(), args.edited.resolve()}
    if args.output.resolve() in inputs or report_path.resolve() in inputs:
        ap.error('Output and manifest must be separate from both inputs')
    if args.output.exists() or report_path.exists():
        ap.error('Output or manifest already exists; choose a new output name')
    try:
        raw, report = patch_targets(args.ghg.read_bytes(), json.loads(args.edited.read_text()))
    except (FormatError, ValueError, KeyError, TypeError, OverflowError) as exc:
        ap.error(str(exc))
    report.update(source=str(args.ghg.resolve()), edited=str(args.edited.resolve()),
                  output=str(args.output.resolve()))
    # Exclusive creation also protects against accidentally replacing a file.
    with args.output.open('xb') as stream:
        stream.write(raw)
    with report_path.open('x') as stream:
        json.dump(report, stream, indent=2)
    print(f'Wrote {len(report["targets"])} changed part targets; {report["changed_bytes"]} bytes. '
          'Decoded validation passed. In-game testing still required.')


if __name__ == '__main__':
    main()
