"""Read the observed PC TXTS 1/12 texture inventory and embedded DDS blocks.

Keep all inventory indices, including float/VTF entries. Dropping an unsupported
image would shift every later material reference. Other layouts are rejected.
"""
from pathlib import Path
from .cu3 import Reader, FormatError


def read_texture_store(path):
    data = Path(path).read_bytes()
    r = Reader(data)
    envelope = data.find(b'TSXT')
    at = data.find(b'TSXT', envelope+4) if envelope >= 0 else -1
    if at < 0:
        raise FormatError('Missing typed TXTS texture inventory')
    version = r.get('I', at+4)
    if version not in (1, 12):
        raise FormatError(f'Unsupported TXTS version {version}')
    marker = data.find(b'CONVDATE', at+8)
    if marker < 4:
        raise FormatError('Missing texture conversion metadata')
    length = r.get('I', marker-4)
    cursor = marker+length
    if not 8 <= length <= 65536 or data[cursor:cursor+4] != b'ROTV':
        raise FormatError('Invalid texture inventory boundary')
    count = r.get('I', cursor+4)
    if not 0 <= count <= 65536:
        raise FormatError('Invalid texture inventory count')
    cursor += 8
    entries = []
    for index in range(count):
        digest = r.get('16s', cursor).hex()
        cursor += 16
        length = r.get('I', cursor) if version == 1 else r.get('H', cursor+3)
        cursor += 4 if version == 1 else 5
        if not 0 <= length <= 65535:
            raise FormatError('Invalid texture name length')
        name = r.string(cursor, cursor+length) if length else ''
        cursor += length
        kind = r.get('I', cursor) >> 8 if version == 1 else r.get('B', cursor)
        cursor += 4 if version == 1 else 1
        entries.append(dict(index=index, name=name, kind=kind, hash=digest))
    # These observed stores concatenate DDS payloads with native trailers.
    # Validate each header and the complete inventory before exposing blocks.
    starts = []
    at = data.find(b'DDS ', cursor)
    while at >= 0:
        if at+128 <= len(data) and r.get('I', at+4, '<') == 124 and r.get('I', at+76, '<') == 32:
            starts.append(at)
        at = data.find(b'DDS ', at+4)
    populated = [entry for entry in entries if entry['name']]
    if len(starts) != len(populated) or (starts and starts[0] != cursor):
        raise FormatError('DDS boundaries disagree with texture inventory')
    for entry, start, end in zip(populated, starts, starts[1:]+[len(data)]):
        height, width = r.get('2I', start+12, '<')
        if not 0 < width <= 65536 or not 0 < height <= 65536:
            raise FormatError('Invalid DDS image dimensions')
        entry.update(offset=start, end=end, width=width, height=height)
    return dict(version=version, entries=entries, data=data)
