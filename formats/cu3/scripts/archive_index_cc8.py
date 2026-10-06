"""Read the observed TFA .CC40TAD v2/-8 archive index without game runtimes."""
from pathlib import Path
import argparse
import json
import sys
import types

package = types.ModuleType('io_scene_lego_cu3')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules.setdefault(package.__name__, package)
from io_scene_lego_cu3.archive_cc import index as _index, parse_index as _parse_index, path_hash


def parse_index(data, archive_limit=None):
    return _parse_index(data, archive_limit, expected_layout=(-8, 2))


def index(path):
    return _index(path, expected_layout=(-8, 2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error('Choose a new output filename')
    rows = index(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(rows, stream, indent=2)
    print(f'{len(rows)} verified file entries; {sum(r["path"].upper().endswith(".CU3") for r in rows)} CU3 files')
