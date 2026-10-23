"""Bounded primitive fields from observed self-describing character files.

Class names and embedded schemas choose interpretation. Inline classes retain
their ownership; nested resource objects remain unparsed. Decoded byte extents
and completeness are recorded explicitly.
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
    return read_definition_bytes(Path(path).read_bytes(), source=path)


def read_definition_bytes(data, *, source=None):
    """Decode existing definition layouts without reopening an input snapshot.

    The source is optional provenance; it does not affect layout selection.
    Compressed definitions retain the existing TT deflate output/block limits.
    """
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
    # Observed older definitions include streams 18-24. Streams 20/21 were
    # independently checked on 15 original CD/AS files, including every retained
    # primitive's value and byte offset (DEFINITION_COMPATIBILITY_2026-10-21).
    # 3 schema words per field before 22, a 16-bit list count before 24 and
    # an 18-byte object header before 25.
    if version not in (18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31):
        raise FormatError(f'Definition stream version {version} is not verified')
    marker = data.find(b'ClassList\0', info_end)
    if marker < 0:
        raise FormatError('Definition ClassList missing')
    _, limit = block(marker, b'ClassList')
    # New primitive layouts must be established by their embedded TypeList,
    # not guessed from a game's name or the numeric field ID. In particular,
    # later streams change pointer/resource widths while adding Colour4.
    declared_types = {}
    type_marker = data.find(b'TypeList\0', info_end, marker)
    if type_marker >= 0:
        _, type_end = block(type_marker, b'TypeList')
        if type_end > marker - 8:
            raise FormatError('Definition type list exceeds its metadata region')
        count = get('I', type_marker + 9, type_end)
        if count > 256:
            raise FormatError('Unreasonable definition primitive type count')
        pos = type_marker + 13
        for index in range(count):
            _, end = block(pos + 8, b'Type')
            if end > type_end:
                raise FormatError('Definition primitive type exceeds its list')
            name, after = string(pos + 13, end)
            size = get('i', after, end)
            if after + 4 != end:
                raise FormatError('Definition primitive type does not fill block')
            declared_types[index] = (name, size)
            pos = end
        if pos != type_end:
            raise FormatError('Definition primitive types do not fill list')
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
            details = get('5I' if version >= 27 else '4I' if version >= 22 else '3I', pos, types_end)
            pos += 4 * len(details)
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
    def fields_for(index, chain=(), budget=None):
        if index in chain or index >= len(schemas) or len(chain) >= 64:
            raise FormatError('Invalid inherited definition schema')
        if budget is None:
            budget = [65536]
        budget[0] -= 1
        if budget[0] < 0:
            raise FormatError('Unreasonable expanded definition field count')
        for field in schemas[index]:
            if field['details'][2] & 0xc0000000 == 0xc0000000:
                yield from fields_for(field['type'], chain+(index,), budget)
            else:
                yield field

    def read_fields(index, pos, end, chain=(), budget=None):
        if index in chain or index >= len(schemas) or len(chain) >= 64:
            raise FormatError('Invalid inline definition schema')
        if budget is None:
            budget = [65536]
        values, spans = {}, {}
        for field in fields_for(index, budget=budget):
            budget[0] -= 1
            if budget[0] < 0:
                raise FormatError('Unreasonable expanded definition field count')
            typ, field_start = field['type'], pos
            flags = field['details'][2]
            if flags & 0x80000000:
                # Only the observed embedded-class flag is enabled. Inherited
                # fields are already expanded by fields_for above.
                if flags & 0xf0000000 != 0xa0000000:
                    return values, spans, pos, False
                nested, nested_spans, after, complete = read_fields(
                    typ, pos, end, chain + (index,), budget)
                if not complete:
                    # An inline class has no extent of its own. An unknown
                    # member prevents locating subsequent outer fields safely.
                    return values, spans, field_start, False
                value = {'class': classes[typ], 'fields': nested,
                         'field_spans': nested_spans, 'inline': True}
                pos = after
                span = {'offset':field_start, 'end':pos, 'type':None,
                        'class_index':typ, 'inline':True}
            else:
                if pos == end:
                    return values, spans, pos, False
                fmt = FORMATS.get(typ)
                if typ == 14 and declared_types.get(typ) == ('Half', 2):
                    fmt = 'e'
                elif typ == 19 and declared_types.get(typ) == ('Colour4', 16):
                    fmt = '4f'
                if typ == 5:
                    value, pos = string(pos, end)
                elif fmt is not None:
                    value = get(fmt, pos, end)
                    pos += struct.calcsize('<' + fmt)
                    numbers = value if isinstance(value, tuple) else (value,)
                    if not all(math.isfinite(v) for v in numbers):
                        raise FormatError('Non-finite definition value')
                else:
                    return values, spans, pos, False
                span = {'offset':field_start, 'end':pos, 'type':typ}
            values[field['name']] = value
            spans[field['name']] = span
        return values, spans, pos, True
    objects = []
    # Only direct members of typed lists have that list's schema. Nested
    # GAMEANIMDATA MOBJ blocks are not Character Anim Entry objects.
    members = set()
    for owner in lists:
        count = get('I' if version >= 24 else 'H', owner['start'] + 15, owner['end'])
        if count > 65536:
            raise FormatError('Unreasonable definition object count')
        pos = owner['start'] + (19 if version >= 24 else 17)
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
        pos = start + (17 if version >= 28 else 16 if version >= 25 else 18)
        if pos > end:
            raise FormatError('Truncated definition object header')
        values, field_spans, pos, fields_complete = read_fields(cls, pos, end)
        objects.append({'class':classes[cls], 'offset':start, 'size':end-start,
                        'fields':values, 'field_spans':field_spans,
                        'decoded_end':pos, 'complete':fields_complete and pos==end})
    return {'source':str(Path(source).resolve()) if source is not None else None, 'source_sha256':source_sha256,
            'version':version, 'byte_order':'little', 'objects':objects,
            'field_span_address_space':'decompressed definition bytes',
            'structure_identity':{'format':'typed-definition', 'version':version, 'byte_order':'little'},
            'unparsed_scope':'Inline classes are decoded when all members are understood. Nested resource objects and unknown field types remain undecoded; dependency closure covers retained declarations only.'}


def character_definition(path):
    result = read_definition(path)
    definitions = [o for o in result['objects'] if o['class']=='Character Definition' and 'Skeleton Name' in o['fields']]
    if not definitions and result['version'] < 24:
        # LB2's older streams (faces, the base minifigure) name their model in
        # 'Model File' and have no skeleton name: read it as the model override.
        definitions = [o for o in result['objects'] if o['class']=='Character Definition' and o['fields'].get('Model File')]
        if len(definitions) == 1:
            fields = definitions[0]['fields']
            definitions[0] = dict(definitions[0], fields=dict(fields, **{'Override Model File':fields['Model File'], 'Skeleton Name':''}))
    if len(definitions) != 1:
        offsets=', '.join(hex(o['offset']) for o in definitions)
        raise FormatError('Expected one character definition with a skeleton name; found '+str(len(definitions))+
                          (' at '+offsets if offsets else ''))
    result['character'] = definitions[0]['fields']
    return result
