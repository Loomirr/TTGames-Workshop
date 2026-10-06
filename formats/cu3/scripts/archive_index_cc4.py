"""Read-only .CC40TAD v2/-12 index reader, checked on local DCSV archives."""
from pathlib import Path
import argparse
import json
import sys
import types

# Share the bounded reader without executing Blender's package entry point.
# The standalone GUI packager follows these explicit imports.
package = types.ModuleType('io_scene_lego_cu3')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules.setdefault(package.__name__, package)
from io_scene_lego_cu3.archive_cc import index as _index


def index(path):
    return _index(path, expected_layout=(-12, 2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path, help='New index JSON filename')
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error('Choose a new output filename')
    rows = index(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(rows, stream, indent=2)
    print('CC4_INDEX', len(rows), 'CU3', sum(r['path'].upper().endswith('.CU3') for r in rows))
