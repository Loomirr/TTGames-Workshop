"""Experimental LMSH1 PC charstxt FPK append; preserves existing member bytes.

This is a private-test building block, not a verified general PAK writer. The
observed additive header checksum is checked and rebuilt; opaque metadata stays.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
package = types.ModuleType('tt_clone_fpk_readers')
package.__path__ = [str(ROOT / 'formats/cu3/Addon/io_scene_lego_cu3')]
sys.modules[package.__name__] = package
from tt_clone_fpk_readers.pak_reader import parse_pak
from tt_clone_fpk_readers.archive_paths import validate_paths

MAX_INPUT = 16 * 1024 * 1024
MAX_TEXT = 1024 * 1024


def bank_checksum(data):
    """Observed PC bank sum, excluding its own four-byte field at offset 12."""
    return (0x12345678 + sum(data[:12]) + sum(data[16:])) & 0xffffffff


def append_character_text(data, name, payload, *, donor, expected_sha256, game):
    """Add one new TXT member, preserving sorted native table order.

    Existing string/payload storage is relocated intact by one 28-byte entry.
    The new record inherits the explicit donor's opaque metadata. No existing
    member is replaced. Input/output are bytes; this function writes no files.
    """
    if game != 'lmsh1' or len(data) > MAX_INPUT:
        raise ValueError('Only bounded LMSH1 PC charstxt banks are enabled')
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError('Source SHA-256 mismatch')
    entries = parse_pak(data)
    if struct.unpack_from('<I', data, 12)[0] != bank_checksum(data):
        raise ValueError('Unverified or damaged source bank checksum')
    if not entries or len(entries) >= 65536:
        raise ValueError('Invalid source member count')
    if any(e['kind'] != 1 or e['compressed'] or not e['name'].lower().endswith('.txt')
           or not e['name'].lower().startswith('chars/') for e in entries):
        raise ValueError('Expected uncompressed character TXT members')
    names = [e['name'] for e in entries]
    if names != sorted(names, key=str.casefold):
        raise ValueError('Unverified source member order')
    normalized = validate_paths([name])[0]
    if (not normalized.startswith('chars/') or not normalized.endswith('.txt') or
            normalized != normalized.lower()):
        raise ValueError('New member must be a lowercase chars/...txt logical path')
    validate_paths(names + [normalized])
    matches = [i for i, e in enumerate(entries) if e['name'].casefold() == donor.casefold().replace('\\', '/')]
    if len(matches) != 1:
        raise ValueError('Expected exactly one existing donor member')
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_TEXT or b'\0' in payload:
        raise ValueError('Expected bounded text bytes without NUL')
    try:
        encoded_name = normalized.replace('/', '\\').encode('ascii') + b'\0'
    except UnicodeEncodeError as error:
        raise ValueError('Only ASCII member paths are supported') from error
    header = list(struct.unpack_from('<6I', data))
    table_end = 24 + 28 * len(entries)
    records = [list(struct.unpack_from('<7I', data, 24 + 28 * i)) for i in range(len(entries))]
    for record in records:
        record[0] += 28
        record[1] += 28
    new_record = records[matches[0]].copy()
    new_record[:3] = [len(data) + 28, len(data) + 28 + len(encoded_name), len(payload)]
    ordered = list(zip(names, records)) + [(normalized, new_record)]
    ordered.sort(key=lambda item: item[0].casefold())
    header[1] += 1
    header[2] = len(data) + 28 + len(encoded_name) + len(payload) + 2
    result = (struct.pack('<6I', *header) +
              b''.join(struct.pack('<7I', *record) for _, record in ordered) +
              data[table_end:] + encoded_name + payload + b'\0\0')
    result = result[:12] + struct.pack('<I', bank_checksum(result)) + result[16:]
    after = {e['name']: e for e in parse_pak(result)}
    for old in entries:
        new = after[old['name']]
        if (result[new['offset']:new['offset'] + new['size']] !=
                data[old['offset']:old['offset'] + old['size']]):
            raise ValueError('Existing member changed during append')
    added = after[normalized]
    if result[added['offset']:added['offset'] + added['size']] != payload:
        raise ValueError('New member verification failed')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Original LMSH1 PC chars/charstxt.fpk')
    parser.add_argument('text', type=Path, help='New character TXT payload')
    parser.add_argument('output', type=Path, help='Separate new FPK; existing files are refused')
    parser.add_argument('--name', required=True, help='New lowercase chars/...txt member path')
    parser.add_argument('--donor', required=True, help='Existing character TXT member for metadata')
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--game', required=True, choices=['lmsh1'])
    args = parser.parse_args()
    # Bound actual reads, including sources which grow after stat().
    with args.source.open('rb') as stream:
        data = stream.read(MAX_INPUT + 1)
    with args.text.open('rb') as stream:
        payload = stream.read(MAX_TEXT + 1)
    result = append_character_text(data, args.name, payload, donor=args.donor,
                                  expected_sha256=args.source_sha256, game=args.game)
    with args.output.open('xb') as stream:
        stream.write(result)
    print(json.dumps({'members': len(parse_pak(result)), 'bytes': len(result),
                      'sha256': hashlib.sha256(result).hexdigest(),
                      'validation': 'preserved members; native runtime test required'}))


if __name__ == '__main__':
    main()
