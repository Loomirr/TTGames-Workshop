"""Constrained loose LMSH1 definition edits; no DAT writes or block relocation."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
package = types.ModuleType('tt_clone_readers')
package.__path__ = [str(ROOT / 'formats/cu3/Addon/io_scene_lego_cu3')]
sys.modules[package.__name__] = package
from tt_clone_readers.definitions import read_definition_bytes

MAX_INPUT = 16 * 1024 * 1024


def patch_definition(data, edits, *, expected_sha256, game):
    """Patch explicit decoded string fields without moving any native byte.

    Each edit has object_offset, class, field, expected and replacement keys.
    Object offsets refer to the uncompressed source snapshot. Unknown payloads
    remain byte-identical; compressed definitions are deliberately refused.
    """
    if game != 'lmsh1':
        raise ValueError('Only the observed LMSH1 PC definition profile is enabled')
    if len(data) > MAX_INPUT:
        raise ValueError('Definition exceeds 16 MiB limit')
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError('Source SHA-256 mismatch')
    if data.startswith(b'Deflate_v1.0'):
        raise ValueError('Compressed definition writing is not supported')
    decoded = read_definition_bytes(data)
    if decoded['version'] != 25:
        raise ValueError('Only StreamInfo 25 is enabled for this writer')
    if not isinstance(edits, list) or not edits:
        raise ValueError('Provide a nonempty list of explicit field edits')
    output = bytearray(data)
    touched = set()
    for edit in edits:
        matches = [o for o in decoded['objects'] if o['offset'] == edit['object_offset']
                   and o['class'] == edit['class']]
        if len(matches) != 1:
            raise ValueError('Expected exactly one object with the specified offset and class')
        obj = matches[0]
        name = edit['field']
        span = obj['field_spans'].get(name)
        if not span or span['type'] != 5:
            raise ValueError('Only fully decoded string fields can be edited')
        if obj['fields'][name] != edit['expected']:
            raise ValueError('Expected field value does not match source')
        replacement = edit['replacement']
        if not isinstance(replacement, str) or '\0' in replacement:
            raise ValueError('Replacement must be a string without NUL characters')
        try:
            raw = replacement.encode('ascii') + b'\0'
        except UnicodeEncodeError as error:
            raise ValueError('Only ASCII strings are supported') from error
        start, end = span['offset'], span['end']
        if len(raw) + 4 != end - start:
            raise ValueError('Replacement must retain the exact encoded string length')
        if any(i in touched for i in range(start, end)):
            raise ValueError('Duplicate or overlapping field edits')
        touched.update(range(start, end))
        output[start:end] = struct.pack('<I', len(raw)) + raw
    result = bytes(output)
    after = read_definition_bytes(result)
    for edit in edits:
        obj = next(o for o in after['objects'] if o['offset'] == edit['object_offset'])
        if obj['fields'][edit['field']] != edit['replacement']:
            raise ValueError('Edited definition failed decoded verification')
    if len(result) != len(data) or any(a != b and i not in touched
                                    for i, (a, b) in enumerate(zip(data, result))):
        raise ValueError('Unexpected change outside declared field extents')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('plan', type=Path, help='JSON: game, source_sha256, edits')
    parser.add_argument('output', type=Path, help='New loose file; existing paths are refused')
    args = parser.parse_args()
    if args.source.stat().st_size > MAX_INPUT:
        parser.error('Definition exceeds 16 MiB limit')
    data = args.source.read_bytes()
    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    result = patch_definition(data, plan['edits'], expected_sha256=plan['source_sha256'], game=plan['game'])
    # Exclusive creation avoids overwriting a game asset, source or earlier proof.
    with args.output.open('xb') as stream:
        stream.write(result)
    print(json.dumps({'bytes':len(result), 'sha256':hashlib.sha256(result).hexdigest(),
                      'edits':len(plan['edits']), 'validation':'decoded; not in-game'}))


if __name__ == '__main__':
    main()
