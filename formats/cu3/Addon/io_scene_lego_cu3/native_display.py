"""Observed DISP 7-14 (LEGO Batman 2), 16-18/21-24/26/32 draw bindings and named model instances."""
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
    if version not in (7, 8, 9, 10, 12, 13, 14, 16, 17, 18, 21, 22, 23, 24, 26, 32):
        raise FormatError(f'DISP {version} requires a separate verified reader')
    dx = version in (26, 32)
    # LEGO Batman 2's older lists (with MESH 47): see docs/LB2_GEOMETRY.md.
    old = version in (7, 8, 9, 10)
    def separator():
        # Non-DX11 arrays are separated by ROTV (skipped unchecked as before);
        # in DISP 9 and 10 it is checked, and DISP 7 and 8 have none.
        if not old:
            c.take(4)
        elif version >= 9:
            c.expect(b'ROTV', '4s')
    def array(size=None):
        if dx:
            c.expect(b'ROTV', '4s')
        n = c.count(1_000_000)
        if size is not None:
            c.take(n * size)
        return n
    if not dx:
        array(1)
        separator()
    commands = [c.get('BBI') for _ in range(array())]
    if not dx:
        separator()
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
            separator()
            array(size)
        if version in (16, 17):
            # Three additional per-clip scalar arrays precede the specials
            # (also in LMSH1's DISP 17: docs/LMSH1_VEHICLES.md).
            # Treating the first count as the specials count loses hats/props.
            for _ in range(3):
                c.expect(b'ROTV', '4s')
                if array(4) != len(clips):
                    raise FormatError(f'DISP {version} auxiliary count differs from clip table')
        elif version in (12, 13, 14):
            # LEGO Batman 2 has the same three per-clip arrays, but only the
            # first carries a ROTV marker; the other two are count + values.
            c.expect(b'ROTV', '4s')
            for _ in range(3):
                if array(4) != len(clips):
                    raise FormatError('LB2 display auxiliary count differs from clip table')
        elif old:
            # The same per-clip arrays (two in DISP 7), then two more arrays
            # that DISP 12 dropped: pairs of command indices (8 bytes each)
            # and 16-byte records. Neither is interpreted.
            separator()
            for _ in range(2 if version == 7 else 3):
                if array(4) != len(clips):
                    raise FormatError('LB2 display auxiliary count differs from clip table')
            separator()
            array(8)
            separator()
            array(16)
        separator()
    names_at = data.find(b'LBTN')
    names_start = names_at + 12
    names_end = names_start + c.reader.get('I', names_at + 8) if names_at >= 0 else 0
    specials = []
    for index in range(array()):
        start = c.at
        if dx and version != 26:
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
            lod_ranges = [c.reader.get('f', body + 124 + i*4) for i in range(ranges)]
        else:
            name = c.reader.string(names_start + c.get('I'), names_end)
            matrix = list(c.reader.get('16f', start + 4))
            clip, flags, ranges = c.reader.get('3I', start + 180)
            if ranges > 100_000:
                raise FormatError('Unreasonable native display range count')
            c.at = start
            c.take(204 + 4 * ranges)
            lod_ranges = [c.reader.get('f', start + 192 + i*4) for i in range(ranges)]
        # The all-ones clip index is an empty named locator, observed on
        # accessory VFX anchors. Keep its position in the specials table:
        # native layer/attachment indices still refer to that table.
        locator_only = dx and clip == 0xffffffff
        if (not locator_only and clip >= len(clips)) or not all(math.isfinite(v) for v in matrix):
            raise FormatError('Invalid native display instance')
        bindings, unsupported = [], []
        draw_list = [] if locator_only else zip(clips[clip]['materials'], clips[clip]['items'])
        for material, command in draw_list:
            opcode, command_flags, part = commands[command]
            if opcode in (0x80, 0xb3):
                if part >= part_count:
                    raise FormatError('Display references an absent mesh part')
                bindings.append({'part': part, 'material': material})
            else:
                unsupported.append({'opcode': opcode, 'flags': command_flags, 'value': part})
        specials.append(dict(index=index, name=name, matrix=matrix, clip=clip,
                             flags=flags, parts=bindings, unsupported_commands=unsupported,
                             locator_only=locator_only, lod_ranges=lod_ranges))
    return dict(version=version, specials=specials, commands=commands,
                clips=clips, end_offset=c.at)


def model_bindings(display, special, *, highest_detail=True):
    """Select the nearest native LOD, without interpreting stage draw pools.

    Verified static accessories store far-to-near thresholds and consecutive
    clips. HGOL alternatives without this table retain their authored binding.
    Unknown LOD tables fail instead of choosing a mesh by triangle count/name.
    """
    ranges = special.get('lod_ranges', [])
    if not highest_detail or not ranges or special.get('locator_only'):
        return special['parts']
    # Observed Avengers DISP 32 accessories retain four ordered LOD clips
    # even when their nearest two (or all four) distance thresholds are zero.
    # This only selects the explicit final clip for a highest-detail preview;
    # it does not attempt to reproduce the engine's distance switching.
    zero_tail = display['version'] == 32 and len(ranges) == 4
    if (display['version'] not in (7, 8, 9, 10, 12, 13, 14, 16, 17, 18, 21, 22, 24, 26, 32)
            or len(ranges) > 8 or ranges[-1] != 0
            or any(not math.isfinite(v) or v < 0 for v in ranges)
            or any(a <= b and not (zero_tail and a == b == 0)
                   for a, b in zip(ranges, ranges[1:]))):
        raise FormatError('Unverified native model LOD thresholds')
    first = special['clip']
    if first + len(ranges) > len(display['clips']):
        raise FormatError('Native model LOD clips exceed the display table')
    levels = []
    for clip in display['clips'][first:first + len(ranges)]:
        bindings = []
        for material, index in zip(clip['materials'], clip['items']):
            opcode, flags, part = display['commands'][index]
            if (opcode, flags) != (0xb3, 0):
                raise FormatError('Unverified native model LOD draw command')
            bindings.append(dict(part=part, material=material))
        if not bindings:
            raise FormatError('Native model LOD has no draw bindings')
        levels.append(bindings)
    return levels[-1]
