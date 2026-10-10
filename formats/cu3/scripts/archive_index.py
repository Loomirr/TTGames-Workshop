"""Read-only observed parent-index DAT inventory and bounded extraction.

Default -6 is the validated LB3 layout. Explicit -5 covers the observed
Hobbit/LEGO Movie parent layout, not every archive whose first word is -5.
The separate LMSH1 tree/hash reader remains separate. Unknown versions fail.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import struct
import sys
import types

package = types.ModuleType('io_scene_lego_cu3')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3')]
sys.modules.setdefault(package.__name__, package)
from io_scene_lego_cu3.archive_assets import index_v6, MAX_ENTRY_BYTES, MAX_TOTAL_BYTES
from io_scene_lego_cu3.archive_compression import decode_entry
from io_scene_lego_cu3.archive_paths import preflight_destination, safe_path
from io_scene_lego_cu3.bundle_output import publish_bundle
from io_scene_lego_cu3.cu3 import FormatError


def index(path, *, version_expected=-6):
    return index_v6(path, version_expected=version_expected)


def _read_entry(path, entry):
    if any(not isinstance(entry.get(key), int) or entry[key] < 0
           for key in ('offset', 'packed_size', 'size', 'flags')):
        raise FormatError('Invalid DAT entry bounds or mode')
    if max(entry['packed_size'], entry['size']) > MAX_ENTRY_BYTES:
        raise FormatError('Requested DAT entry exceeds the 256 MiB limit')
    if entry['flags'] not in (0, 2):
        raise FormatError('Unverified DAT storage mode; LOTR mode 3 is unsupported')
    with Path(path).open('rb') as stream:
        before = os.fstat(stream.fileno())
        header = stream.read(8)
        if len(header) != 8:
            raise FormatError('Truncated DAT header')
        index_offset, index_size = struct.unpack('<II', header)
        if index_offset & 0x80000000:
            index_offset = ((index_offset ^ 0xffffffff) << 8) + 256
        start, end = entry['offset'], entry['offset'] + entry['packed_size']
        if (start < 8 or end > before.st_size or
                start < index_offset + index_size and end > index_offset):
            raise FormatError('DAT entry exceeds its payload region')
        stream.seek(start)
        packed = stream.read(entry['packed_size'])
        after = os.fstat(stream.fileno())
    if len(packed) != entry['packed_size'] or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise FormatError('DAT source changed or payload is truncated')
    return decode_entry(packed, entry['size'], storage_mode=entry['flags'])


def extract(path, entry, dest, *, version_expected=-6):
    """Extract one validated entry exclusively, preserving existing files."""
    name = safe_path(entry['path'])
    _, targets = preflight_destination(Path(dest), [name])
    if entry not in index(path, version_expected=version_expected):
        raise FormatError('DAT entry does not match the validated source index')
    data = _read_entry(path, entry)
    target = targets[0]
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        if stream.write(data) != len(data):
            raise OSError('Short DAT output write')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path, help='New inventory/extraction folder')
    parser.add_argument('--extract-cutscenes', action='store_true')
    parser.add_argument('--index-version', type=int, choices=(-6, -5), default=-6,
                        help='Explicit native parent-index version: -6 LB3 (default), -5 observed Hobbit/LEGO Movie; not LMSH1 tree indexes')
    args = parser.parse_args()
    try:
        entries = index(args.archive, version_expected=args.index_version)
    except (ValueError, OSError, struct.error) as error:
        parser.error(str(error) + '; this reader uses parent indexes (-6 LB3 / -5 Hobbit), not LMSH1 tree indexes')
    selected = [entry for entry in entries if args.extract_cutscenes and (
        entry['path'].upper().endswith('.CU3') or
        entry['path'].upper().startswith('CUT/') and entry['path'].upper().endswith(('.TXT', '.SUB', '.LED')))]
    if (sum(entry['packed_size'] for entry in selected) > MAX_TOTAL_BYTES or
            sum(entry['size'] for entry in selected) > MAX_TOTAL_BYTES):
        parser.error('Cumulative extraction exceeds the 1 GiB limit; extract smaller selections')
    if any(max(entry['packed_size'], entry['size']) > MAX_ENTRY_BYTES or entry['flags'] not in (0, 2)
           for entry in selected):
        parser.error('Selection includes an oversized or unsupported storage-mode entry')
    index_name = args.archive.stem + '-index.json'
    names = [index_name] + ['Extracted/' + entry['path'] for entry in selected]
    preflight_destination(args.output, names + ['archive-manifest.json'], require_absent=True)
    report = dict(schema='tt-dat-extraction-v1', source=str(args.archive.resolve()),
                  index_version=args.index_version, layout='little-endian parent/name/path-hash tables',
                  indexed_files=len(entries), extracted_files=len(selected), entries=[])

    def payloads():
        yield index_name, json.dumps(entries, indent=2).encode('utf-8')
        for entry in selected:
            decoded = _read_entry(args.archive, entry)
            report['entries'].append(dict(path=entry['path'], bytes=len(decoded),
                                          sha256=hashlib.sha256(decoded).hexdigest()))
            yield 'Extracted/' + entry['path'], decoded

    publish_bundle(args.output, payloads(), report, expected_paths=names, manifest_name='archive-manifest.json')
    print(args.archive.name, 'entries', len(entries), 'extracted', len(selected), flush=True)


if __name__ == '__main__':
    main()
