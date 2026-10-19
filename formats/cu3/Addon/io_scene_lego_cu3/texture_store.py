"""Read the observed PC TXTS 1/12/14 texture inventory and embedded DDS blocks.

Keep all inventory indices, including float/VTF entries. Dropping an unsupported
image would shift every later material reference. Other layouts are rejected.
"""
from pathlib import Path
from .cu3 import Reader, FormatError
from .dds import read_dds, next_dds_header


def read_texture_store(path):
    data = Path(path).read_bytes()
    r = Reader(data)
    envelope = data.find(b'TSXT')
    at = data.find(b'TSXT', envelope+4) if envelope >= 0 else -1
    if at < 0:
        raise FormatError('Missing typed TXTS texture inventory')
    version = r.get('I', at+4)
    if version not in (0, 1, 12, 14):
        raise FormatError(f'Unsupported TXTS version {version}')
    # The conversion-metadata string is length-prefixed and may be empty.
    # Do not search later texture names/payloads for a coincidental CONVDATE.
    length = r.get('I', at+8) if version else 0
    marker = at+12
    empty_c_string = version == 14 and length == 1 and data[marker:marker+1] == b'\0'
    if length and not empty_c_string and (not 8 <= length <= 65536 or data[marker:marker+8] != b'CONVDATE'):
        raise FormatError('Unsupported texture conversion metadata')
    cursor = marker+length if version else at+8
    if data[cursor:cursor+4] != b'ROTV':
        raise FormatError('Invalid texture inventory boundary')
    count = r.get('I', cursor+4)
    if not 0 <= count <= 65536:
        raise FormatError('Invalid texture inventory count')
    cursor += 8
    entries = []
    for index in range(count):
        digest = r.get('16s', cursor).hex()
        cursor += 16
        length = r.get('I', cursor) if version in (0, 1) else r.get('H', cursor+3)
        cursor += 4 if version in (0, 1) else 5
        if not 0 <= length <= 65535:
            raise FormatError('Invalid texture name length')
        name = r.string(cursor, cursor+length) if length else ''
        cursor += length
        kind = r.get('I', cursor) >> 8 if version in (0, 1) else r.get('B', cursor)
        cursor += 4 if version in (0, 1) else 1
        entry = dict(index=index, name=name, kind=kind, hash=digest)
        if version == 14:
            format_id = r.get('I', cursor)
            cursor += 4
            entry['format_id'] = format_id
            if format_id != 255:
                platforms = r.get('H', cursor)
                cursor += 2
                if platforms > 64:
                    raise FormatError('Unreasonable TXTS opaque-reference count')
                entry['opaque_refs'] = list(r.get(f'{platforms}H', cursor)) if platforms > 1 else [r.get('H', cursor)] if platforms else []
                cursor += platforms*2
        entries.append(entry)
    # DDS headers size the mip/face/array payloads. Never scan inside pixels
    # for the next image: a perfectly valid header can occur in pixel data.
    # Native inter-image trailers remain opaque and are kept out of DDS bytes.
    populated = [entry for entry in entries if entry['name']]
    first = next_dds_header(data, cursor)
    if first is not None and first != cursor and version == 14 and populated and populated[0]['format_id'] == 255:
        # Observed named cube payload preamble; require the same inventory name.
        name_length = r.get('H', cursor)
        if not 0 < name_length <= 65535 or r.string(cursor+2, cursor+2+name_length) != populated[0]['name']:
            raise FormatError('TXTS named payload disagrees with inventory')
        cursor += 2+name_length
        if r.get('B', cursor) != 5:
            raise FormatError('Unsupported TXTS named payload kind')
        cursor += 1
    if (populated and first != cursor) or (not populated and first is not None):
        raise FormatError('DDS boundaries disagree with texture inventory')
    at = first
    for entry in populated:
        if at is None:
            raise FormatError('DDS boundaries disagree with texture inventory')
        try:
            dds = read_dds(data, at)
        except FormatError as error:
            raise FormatError(f'Texture {entry["index"]} ({entry["name"]}): {error}') from error
        following = next_dds_header(data, dds['end'])
        trailer_end = len(data) if following is None else following
        entry.update(offset=at, end=dds['end'], width=dds['width'], height=dds['height'],
                     dds=dds, trailer_offset=dds['end'], trailer_end=trailer_end)
        at = following
    if at is not None:
        raise FormatError('DDS boundaries disagree with texture inventory: extra payload')
    return dict(version=version, entries=entries, data=data,
                payload_validation='DDS header-sized spans; enclosing native trailers remain opaque')


def read_embedded_texture_store(path):
    """LEGO Batman 2 models keep their textures inside the model (no companion).

    The HGXT list (versions 9 and 10) names each texture; entries without a
    name have no image. The named entries' DDS images follow, contiguous and
    in list order. Version 9 entries also record each image's size, which must
    match its DDS header. Indices keep unnamed entries, as material IDs do.
    """
    data = Path(path).read_bytes()
    r = Reader(data)
    at = data.find(b'HGXT')
    if at < 0 or data.find(b'HGXT', at+4) >= 0:
        raise FormatError('Expected one embedded HGXT texture list')
    version = r.get('I', at+4)
    if version not in (9, 10) or data[at+8:at+12] != b'ROTV':
        raise FormatError(f'Unsupported embedded texture list version {version}')
    count = r.get('I', at+12)
    if count > 65536:
        raise FormatError('Invalid embedded texture count')
    cursor = at+16+4*count
    if data[cursor:cursor+4] != b'ROTV' or r.get('I', cursor+4) != count:
        raise FormatError('Embedded texture lists disagree')
    cursor += 8
    entries = []
    for index in range(count):
        digest = r.get('16s', cursor).hex()
        size = r.get('2I', cursor+16) if version == 9 else None
        length_at = cursor+53 if version == 9 else cursor+16
        length = r.get('I', length_at)
        if length > 65535 or (length and data[length_at+4+length-1:length_at+4+length] != b'\0'):
            raise FormatError('Invalid embedded texture name')
        name = r.string(length_at+4, length_at+4+length) if length > 1 else ''
        entries.append(dict(index=index, name=name, kind=None, hash=digest, size=size))
        cursor = length_at+4+length+(14 if version == 9 else 4)
    populated = [entry for entry in entries if entry['name']]
    image = next_dds_header(data, cursor) if populated else None
    for number, entry in enumerate(populated):
        if image is None:
            raise FormatError('Embedded DDS images disagree with the texture list')
        try:
            dds = read_dds(data, image)
        except FormatError as error:
            raise FormatError(f'Texture {entry["index"]} ({entry["name"]}): {error}') from error
        if entry['size'] is not None and tuple(entry['size']) != (dds['width'], dds['height']):
            raise FormatError(f'Texture {entry["index"]} size disagrees with its DDS header')
        entry.update(offset=image, end=dds['end'], width=dds['width'], height=dds['height'], dds=dds)
        image = dds['end'] if number+1 < len(populated) else None
        if image is not None and data[image:image+4] != b'DDS ':
            raise FormatError('Embedded DDS images are not contiguous')
    return dict(version=version, entries=entries, data=data, embedded=True,
                payload_validation='HGXT names in list order; contiguous DDS header-sized spans')
