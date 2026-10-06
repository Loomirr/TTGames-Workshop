"""Preflight and extract observed TT 0x1234567A PAKs into new folders.

Uses Workshop's existing bounded TT Deflate_v1.0 reader. QuickBMS is no longer
invoked. This does not enable LOTR DAT mode 3 or any unverified compression.
"""
import argparse
import hashlib
from pathlib import Path
import sys
import types

package = types.ModuleType('io_scene_lego_cu3')
package.__path__ = [str(Path(__file__).resolve().parents[2] / 'cu3/Addon/io_scene_lego_cu3')]
sys.modules.setdefault(package.__name__, package)
from io_scene_lego_cu3.archive_paths import preflight_destination, validate_paths
from io_scene_lego_cu3.bundle_output import publish_bundle
from io_scene_lego_cu3.cu3 import FormatError
from io_scene_lego_cu3.pak_reader import read_pak, parse_pak, MAX_PACKED, MAX_DECODED, MAX_TOTAL
from io_scene_lego_cu3.tt_deflate import decompress


def unpack(source, destination, quickbms=None, bms=None, *, max_packed=MAX_PACKED,
           max_decoded=MAX_DECODED, max_total=MAX_TOTAL):
    """Return a verified manifest after non-replacing bundle publication.

    Legacy quickbms/bms arguments remain accepted for old Python callers;
    they are deliberately unused. All decoding now uses the native reader.
    """
    source, destination = Path(source), Path(destination)
    data = read_pak(source, max_packed=max_packed)
    entries = parse_pak(data, max_packed=max_packed, max_decoded=max_decoded,
                        max_total=max_total)
    names = [entry['name'] for entry in entries]
    destination, _ = preflight_destination(destination, names + ['pak-manifest.json'], require_absent=True)
    records = []
    report = dict(schema='tt-pak-extraction-v1', source=str(source.resolve()),
                  source_sha256=hashlib.sha256(data).hexdigest(),
                  destination=str(destination), count=len(entries), entries=records,
                  limits=dict(packed_bytes=max_packed, decoded_member_bytes=max_decoded,
                              cumulative_bytes=max_total),
                  decoder='Workshop TT Deflate_v1.0 (no external backend)')

    def payloads():
        decoded_total = 0
        for entry in entries:
            payload = data[entry['offset']:entry['offset'] + entry['size']]
            if entry['compressed']:
                payload = decompress(payload, max_output=min(entry['decoded_size'], max_total - decoded_total),
                                     max_packed=max_packed)
                if payload.startswith(b'Deflate_v1.0'):
                    raise FormatError('Nested TT deflate member framing is not verified')
            if len(payload) != entry['decoded_size']:
                raise FormatError('PAK member decoded size mismatch: ' + entry['name'])
            decoded_total += len(payload)
            if decoded_total > max_total:
                raise FormatError('PAK cumulative decoded size exceeds configured limit')
            records.append(dict(name=entry['name'], offset=entry['offset'], stored_bytes=entry['size'],
                                extracted_bytes=len(payload),
                                compression='TT Deflate_v1.0' if entry['compressed'] else None,
                                kind=entry['kind'], crc=f"{entry['crc']:08x}",
                                sha256=hashlib.sha256(payload).hexdigest()))
            yield entry['name'], payload

    return publish_bundle(destination, payloads(), report, manifest_name='pak-manifest.json',
                          expected_paths=names)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='PAK file or tree of extracted files')
    parser.add_argument('destination', type=Path, help='New extraction parent folder')
    parser.add_argument('--quickbms', type=Path, help='Deprecated compatibility argument; no external tool is invoked')
    parser.add_argument('--bms', type=Path, help='Deprecated compatibility argument; no external script is invoked')
    args = parser.parse_args()
    if not args.source.is_file() and not args.source.is_dir():
        parser.error('Source must be a PAK file or existing directory')
    sources = [args.source] if args.source.is_file() else sorted(
        path for path in args.source.rglob('*') if path.is_file() and path.suffix.casefold() == '.pak')
    relative = [Path(path.stem) if args.source.is_file() else path.relative_to(args.source).with_suffix('')
                for path in sources]
    # Check the complete batch's names and metadata before the first output.
    # Per-PAK publication is transactional; the batch is not one transaction.
    validate_paths([path.as_posix() for path in relative])
    preflight_destination(args.destination, [], require_absent=True)
    packed_total = decoded_total = 0
    output_names = []
    for source, folder in zip(sources, relative):
        raw = read_pak(source)
        entries = parse_pak(raw)
        packed_total += len(raw)
        decoded_total += sum(entry['decoded_size'] for entry in entries)
        if packed_total > MAX_TOTAL or decoded_total > MAX_TOTAL:
            parser.error('Batch cumulative packed/decoded size exceeds the 1 GiB limit; extract smaller batches')
        output_names.extend(folder.as_posix() + '/' + entry['name'] for entry in entries)
        output_names.append(folder.as_posix() + '/pak-manifest.json')
    preflight_destination(args.destination, output_names, require_absent=True)
    count = 0
    for source, folder in zip(sources, relative):
        manifest = unpack(source, args.destination / folder, args.quickbms, args.bms)
        count += manifest['count']
        print(f"{source.name}: {manifest['count']} members")
    print(f'Total: {count} members in {len(sources)} PAKs; each folder contains pak-manifest.json')


if __name__ == '__main__':
    main()
