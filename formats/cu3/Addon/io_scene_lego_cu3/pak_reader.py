"""Complete preflight for the observed PC 0x1234567A animation bank.

This is a read-only container reader. It does not call an external decoder,
create output, infer a different game's compression mode, or import Blender.
"""
from pathlib import Path
import os
import struct
from .archive_paths import validate_paths
from .cu3 import FormatError

MAX_PACKED = 256 * 1024 * 1024
MAX_DECODED = 256 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024
MAX_ENTRIES = 65536
DEFLATE_WRAPPER = b'Deflate_v1.0'.ljust(32, b'\0')


def read_pak(path, *, max_packed=MAX_PACKED):
    """Bound the read even if the source grows after stat()."""
    if not isinstance(max_packed, int) or not 24 <= max_packed <= MAX_PACKED:
        raise FormatError('Invalid PAK packed-byte limit')
    with Path(path).open('rb') as stream:
        before = os.fstat(stream.fileno())
        stream.seek(0, 2)
        if stream.tell() > max_packed:
            raise FormatError('PAK exceeds configured packed-byte limit')
        stream.seek(0)
        data = stream.read(max_packed + 1)
        after = os.fstat(stream.fileno())
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise FormatError('PAK changed while its data was read')
    if len(data) > max_packed:
        raise FormatError('PAK exceeds configured packed-byte limit')
    return data


def parse_pak(data, *, max_packed=MAX_PACKED, max_decoded=MAX_DECODED,
              max_total=MAX_TOTAL):
    if (not isinstance(max_packed, int) or not 24 <= max_packed <= MAX_PACKED or
            not isinstance(max_decoded, int) or not 0 <= max_decoded <= MAX_DECODED or
            not isinstance(max_total, int) or not 0 <= max_total <= MAX_TOTAL):
        raise FormatError('Invalid PAK extraction limits')
    if len(data) < 24:
        raise FormatError('Truncated PAK header')
    if len(data) > max_packed:
        raise FormatError('PAK exceeds configured packed-byte limit')
    magic, count, total, crc, reserved1, reserved2 = struct.unpack_from('<6I', data)
    table_end = 24 + count * 28
    if magic != 0x1234567A or total != len(data) or count > MAX_ENTRIES or table_end > total:
        raise FormatError('Invalid or unsupported PAK layout')
    entries, name_ranges, payload_ranges = [], [], []
    packed_total = decoded_total = 0
    for index in range(count):
        name_at, offset, size, kind, _, checksum, _ = struct.unpack_from('<7I', data, 24 + index * 28)
        if not table_end <= name_at < total or not table_end <= offset <= total or size > total - offset:
            raise FormatError(f'PAK entry {index} is outside its payload/name extent')
        end = data.find(b'\0', name_at, min(total, name_at + 4097))
        if end < 0:
            raise FormatError(f'Unterminated or overlong PAK entry name {index}')
        try:
            name = data[name_at:end].decode('ascii')
        except UnicodeDecodeError as error:
            raise FormatError(f'Unsupported PAK entry name encoding {index}') from error
        name_ranges.append((name_at, end + 1))
        if size:
            payload_ranges.append((offset, offset + size))
        prefix = data[offset:offset + min(size, 36)]
        compressed = prefix.startswith(b'Deflate_v1.0')
        decoded = size
        if compressed:
            if size < 37 or prefix[:32] != DEFLATE_WRAPPER:
                raise FormatError(f'Truncated or invalid TT deflate wrapper in PAK entry {index}')
            decoded = struct.unpack_from('<I', prefix, 32)[0]
            if not decoded:
                raise FormatError(f'Empty TT deflate output in PAK entry {index}')
        if size > max_packed or decoded > max_decoded:
            raise FormatError(f'PAK entry {index} exceeds configured packed/decoded limit')
        packed_total += size
        decoded_total += decoded
        if packed_total > max_total or decoded_total > max_total:
            raise FormatError('PAK cumulative packed/decoded size exceeds configured limit')
        entries.append(dict(name=name, offset=offset, size=size, decoded_size=decoded,
                            kind=kind, crc=checksum, compressed=compressed))
    try:
        paths = validate_paths(entry['name'] for entry in entries)
    except ValueError as error:
        raise FormatError(str(error)) from error
    for entry, name in zip(entries, paths):
        entry['name'] = name
    # Identical payload spans may be referenced by distinct member names.
    # Partial overlap, or using payload bytes as metadata, is unverified.
    ranges = sorted(set(payload_ranges))
    if any(right[0] < left[1] for left, right in zip(ranges, ranges[1:])):
        raise FormatError('Overlapping PAK member payloads')
    name_ranges.sort()
    cursor = 0
    for start, end in name_ranges:
        while cursor < len(ranges) and ranges[cursor][1] <= start:
            cursor += 1
        if cursor < len(ranges) and ranges[cursor][0] < end:
            raise FormatError('PAK member name overlaps payload bytes')
    return entries
