"""Bounded primitive fields from observed self-describing character files.

Class names and embedded schemas choose interpretation. Nested resource fields
remain unparsed; decoded byte extents and completeness are recorded explicitly.
"""
from pathlib import Path
import re
import struct
import math
import hashlib
from .cu3 import Reader, FormatError
from .tt_deflate import decompress

FORMATS = {0:'B', 1:'h', 2:'i', 3:'q', 4:'f', 6:'3f', 8:'3f',
           9:'4f', 10:'16f', 17:'3e', 18:'B'}


def read_definition(path):
    data = Path(path).read_bytes()
    source_sha256 = hashlib.sha256(data).hexdigest()
    if data.startswith(b'Deflate_v1.0'):
        data = decompress(data)
    r = Reader(data)
    def get(fmt, at, limit):
        if at < 0 or at + struct.calcsize('<' + fmt) > limit:
            raise FormatError('Definition field exceeds its declared block')
        return r.get(fmt, at, '<')
    def string(at, limit):
        length = get('I', at, limit)
        end = at + 4 + length
        if not 0 < length < 65536 or end > limit or data[end-1] != 0:
            raise FormatError('Invalid definition string extent')
        try:
            return data[at+4:end-1].decode('ascii'), end
        except UnicodeDecodeError as error:
            raise FormatError('Unsupported definition string encoding') from error
    def block(marker, name):
        start = marker - 8
        size, length = get('2I', start, len(data))
        end = start + size
        if length != len(name)+1 or data[marker:marker+length] != name+b'\0' or end > len(data) or size < 8+length:
            raise FormatError('Invalid definition block header')
        return start, end
    marker = data.find(b'StreamInfo\0')
    if marker < 0:
        raise FormatError('Uncompressed definition StreamInfo missing')
    _, info_end = block(marker, b'StreamInfo')
    version = get('I', marker+11, info_end)
    if version not in (25, 26, 27, 28, 29, 30, 31):
        raise FormatError(f'Definition stream version {version} is not verified')
    marker = data.find(b'ClassList\0', info_end)
    if marker < 0:
        raise FormatError('Definition ClassList missing')
    _, limit = block(marker, b'ClassList')
    classes, schemas = [], []
    for match in re.finditer(b'\x06\0\0\0Class\0', data[marker:limit]):
        pos = marker + match.start() + 4
        _, end = block(pos, b'Class')
        if end > limit:
            raise FormatError('Class block exceeds class list')
        name, after = string(pos+6, end)
        types_marker = data.find(b'Types\0', after, end)
        if types_marker < 0:
            raise FormatError('Definition class has no type schema')
        _, types_end = block(types_marker, b'Types')
        if types_end > end:
            raise FormatError('Type schema exceeds class block')
        count = get('I', types_marker+6, types_end)
        if count > 65536:
            raise FormatError('Unreasonable definition field count')
        pos, fields = types_marker+10, []
        for _ in range(count):
            typ = get('I', pos, types_end)
            field, pos = string(pos+4, types_end)
            details = get('5I' if version >= 27 else '4I', pos, types_end)
            pos += 20 if version >= 27 else 16
            fields.append({'type':typ, 'name':field, 'details':details})
        if pos != types_end:
            raise FormatError('Definition field schema does not fill block')
        classes.append(name)
        schemas.append(fields)
    if not classes:
        raise FormatError('Empty definition class list')
    lists = []
    for match in re.finditer(b'\x05\0\0\0OLST\0', data[limit:]):
        start, end = block(limit+match.start()+4, b'OLST')
        cls = get('H', start+13, end)
        if cls >= len(classes):
            raise FormatError('Definition list has unknown class')
        lists.append({'start':start, 'end':end, 'class':cls})
    def fields_for(index, chain=()):
        if index in chain or index >= len(schemas):
            raise FormatError('Invalid inherited definition schema')
        for field in schemas[index]:
            if field['details'][2] & 0xc0000000 == 0xc0000000:
                yield from fields_for(field['type'], chain+(index,))
            else:
                yield field
    objects = []
    # Only direct members of typed lists have that list's schema. Nested
    # GAMEANIMDATA MOBJ blocks are not Character Anim Entry objects.
    members = set()
    for owner in lists:
        count = get('I', owner['start'] + 15, owner['end'])
        if count > 65536:
            raise FormatError('Unreasonable definition object count')
        pos = owner['start'] + 19
        for _ in range(count):
            _, end = block(pos + 8, b'MOBJ')
            if end > owner['end']:
                raise FormatError('Definition member exceeds its list')
            members.add(pos)
            pos = end
    for match in re.finditer(b'\x05\0\0\0MOBJ\0', data[limit:]):
        start, end = block(limit+match.start()+4, b'MOBJ')
        if start not in members:
            continue
        owners = [o for o in lists if o['start'] < start and end <= o['end']]
        if not owners:
            raise FormatError('Definition object has no enclosing typed list')
        cls = min(owners, key=lambda o:o['end']-o['start'])['class']
        pos = start + (17 if version >= 28 else 16)
        if pos > end:
            raise FormatError('Truncated definition object header')
        values = {}
        for field in fields_for(cls):
            if pos == end or field['details'][2] & 0x80000000:
                break
            typ = field['type']
            if typ == 5:
                value, pos = string(pos, end)
            elif typ in FORMATS:
                fmt = FORMATS[typ]
                value = get(fmt, pos, end)
                pos += struct.calcsize('<' + fmt)
                numbers = value if isinstance(value, tuple) else (value,)
                if not all(math.isfinite(v) for v in numbers):
                    raise FormatError('Non-finite definition value')
            else:
                break
            values[field['name']] = value
        objects.append({'class':classes[cls], 'offset':start, 'size':end-start,
                        'fields':values, 'decoded_end':pos, 'complete':pos==end})
    return {'source':str(Path(path).resolve()), 'source_sha256':source_sha256,
            'version':version, 'objects':objects}


def character_definition(path):
    result = read_definition(path)
    definitions = [o for o in result['objects'] if o['class']=='Character Definition' and 'Skeleton Name' in o['fields']]
    if len(definitions) != 1:
        raise FormatError('Expected one character definition with a skeleton name')
    result['character'] = definitions[0]['fields']
    return result
