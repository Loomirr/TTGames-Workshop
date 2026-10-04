"""Observed DISP 18/21/23/32 draw bindings and named model instances."""
from pathlib import Path
import math
from .cu3 import FormatError
from .native_mesh import Cursor


def read_display(path, part_count):
    data = Path(path).read_bytes()
    at = data.find(b'PSID')
    if at < 0:
        raise FormatError('Native display section missing')
    c = Cursor(data, at + 4)
    version = c.get('I')
    if version not in (18, 21, 23, 32):
        raise FormatError(f'DISP {version} requires a separate verified reader')
    dx = version == 32
    def array(size=None):
        if dx:
            c.expect(b'ROTV', '4s')
        n = c.count(1_000_000)
        if size is not None:
            c.take(n * size)
        return n
    if not dx:
        array(1)
        c.take(4)
    commands = [c.get('BBI') for _ in range(array())]
    if not dx:
        c.take(4)
    clips = []
    for _ in range(array()):
        if dx:
            pairs = [c.get('2I') for _ in range(c.get('H'))]
            items, materials = [p[0] for p in pairs], [p[1] for p in pairs]
        else:
            c.take(2)
            materials = [c.get('I') for _ in range(c.count(100_000))]
            items = [c.get('I') for _ in range(c.count(100_000))]
        if len(materials) != len(items) or any(i >= len(commands) for i in items):
            raise FormatError('Invalid native display command list')
        clips.append({'materials': materials, 'items': items})
    if not dx:
        for size in (2, 4):
            c.take(4)
            array(size)
        c.take(4)
    names_at = data.find(b'LBTN')
    names_start = names_at + 12
    names_end = names_start + c.reader.get('I', names_at + 8) if names_at >= 0 else 0
    specials = []
    for index in range(array()):
        start = c.at
        if dx:
            length = c.get('H')
            name = c.reader.string(c.at, c.at + length)
            c.take(length)
            body = c.at
            matrix = list(c.reader.get('16f', body))
            clip, flags, ranges = c.reader.get('3I', body + 112)
            if ranges > 100_000:
                raise FormatError('Unreasonable native display range count')
            extra = c.reader.get('I', body + 132 + 4 * ranges)
            if extra > 100_000:
                raise FormatError('Unreasonable native display extra count')
            c.take(136 + 4 * ranges + 4 * extra)
        else:
            name = c.reader.string(names_start + c.get('I'), names_end)
            matrix = list(c.reader.get('16f', start + 4))
            clip, flags, ranges = c.reader.get('3I', start + 180)
            if ranges > 100_000:
                raise FormatError('Unreasonable native display range count')
            c.at = start
            c.take(204 + 4 * ranges)
        if clip >= len(clips) or not all(math.isfinite(v) for v in matrix):
            raise FormatError('Invalid native display instance')
        bindings, unsupported = [], []
        for material, command in zip(clips[clip]['materials'], clips[clip]['items']):
            opcode, command_flags, part = commands[command]
            if opcode in (0x80, 0xb3):
                if part >= part_count:
                    raise FormatError('Display references an absent mesh part')
                bindings.append({'part': part, 'material': material})
            else:
                unsupported.append({'opcode': opcode, 'flags': command_flags, 'value': part})
        specials.append(dict(index=index, name=name, matrix=matrix, clip=clip,
                             flags=flags, parts=bindings, unsupported_commands=unsupported))
    return dict(version=version, specials=specials, commands=commands,
                clips=clips, end_offset=c.at)
