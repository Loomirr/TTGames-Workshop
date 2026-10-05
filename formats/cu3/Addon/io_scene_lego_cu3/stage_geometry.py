"""Bounded stage DISP inventory for observed LMSH1 21 and LB3 32 layouts.

The full command pool contains both static candidates and named special
geometry. Walking it as one render list assigns stale materials to specials
and can duplicate animated props. This reader preserves the separation and
native indices; it does not claim to resolve visibility or enable rendering.
"""
from pathlib import Path
import math
from .cu3 import FormatError
from .native_mesh import Cursor
from .native_display import read_display


def decode_stage_commands(display, matrix_count, part_count, material_count):
    """Validate observed commands and separate static candidates from specials."""
    commands = display['commands']
    if not commands or not all(isinstance(n, int) and n >= 0 for n in (matrix_count, part_count, material_count)):
        raise FormatError('Invalid stage command inventory bounds')
    boundaries = [i for i, row in enumerate(commands) if row[0] == 0x87]
    if len(boundaries) != 1 or commands[-1] != (0x8e, 0, 0):
        raise FormatError('Unverified stage static/special command boundaries')
    boundary = boundaries[0]
    if boundary < 1 or commands[boundary-1] != (0x84, 4, 0):
        raise FormatError('Stage special section has no verified boundary marker')
    owners = {}
    for special in display['specials']:
        if special.get('locator_only'):
            continue
        clip = display['clips'][special['clip']]
        for material, command in zip(clip['materials'], clip['items']):
            if not 0 <= material < material_count or not boundary < command < len(commands)-1:
                raise FormatError('Named stage special references an invalid material or command section')
            owners.setdefault(command, []).append({'special':special['index'], 'material':material})
    allowed = {0x84:4, 0x85:1, 0x80:3, 0x8b:1, 0xb0:3, 0x83:0, 0xb3:0, 0x87:0, 0x8e:0}
    static, named, groups, controls = [], [], [], []
    material, group = None, None
    for index, (opcode, flags, value) in enumerate(commands):
        if opcode not in allowed or flags != allowed[opcode]:
            raise FormatError(f'Unverified stage command/flags at command {index}: {opcode:#x}/{flags:#x}')
        if opcode in (0x84, 0x8b, 0x87, 0x8e) and value:
            raise FormatError(f'Unverified stage control value at command {index}')
        if opcode == 0x84:
            if index >= boundary:
                raise FormatError('Stage group marker occurs inside named-special commands')
            material, group = None, None
        elif opcode == 0x85:
            if not index < value < boundary or commands[value] != (0x84, 4, 0):
                raise FormatError('Stage group target is outside the static section')
            if index == 0 or commands[index-1] != (0x84, 4, 0):
                raise FormatError('Stage group target has no group marker')
            group = {'first_command':index-1, 'end_command':value, 'material':None}
            groups.append(group)
        elif opcode == 0x80:
            if index >= boundary or not 0 <= value < material_count or group is None:
                raise FormatError('Invalid stage material assignment')
            material = value
            group['material'] = value
        elif opcode == 0x8b:
            if group is None or material is None or index >= boundary:
                raise FormatError('Stage control occurs outside its material group')
        elif opcode == 0xb0:
            if value not in (1, 2, 3):
                raise FormatError('Unverified stage rendering-control value')
            controls.append({'command':index, 'opcode':opcode, 'flags':flags, 'value':value})
        elif opcode == 0x83:
            if not 0 <= value < matrix_count:
                raise FormatError('Stage draw matrix reference outside pool')
        elif opcode == 0xb3:
            if not 0 <= value < part_count or index == 0 or commands[index-1][0] != 0x83:
                raise FormatError('Stage mesh draw has an invalid part or matrix binding')
            row = {'command':index, 'part':value, 'matrix':commands[index-1][2], 'flags':flags}
            if index < boundary:
                if material is None or group is None or not index < group['end_command']:
                    raise FormatError('Static stage draw has no bounded material group')
                row.update(material=material, group=group['first_command'])
                static.append(row)
            else:
                links = owners.get(index)
                if not links or len({link['material'] for link in links}) != 1:
                    raise FormatError('Named stage draw has no unambiguous special material binding')
                row.update(material=links[0]['material'], specials=[link['special'] for link in links])
                named.append(row)
        elif opcode == 0x87:
            material, group = None, None
        elif opcode == 0x8e and index != len(commands)-1:
            raise FormatError('Stage command end occurs before the end of the pool')
    if any(commands[index][0] != 0xb3 for index in owners):
        raise FormatError('Named stage special refers to a non-draw command')
    return {'static_candidates':static, 'named_draws':named, 'groups':groups,
            'render_controls':controls, 'special_boundary_command':boundary,
            'can_render_faithfully':False,
            'limitations':['Static/special separation and native bindings are decoded; render-control and visibility semantics remain unverified.',
                           'Stage placement and active nested scenes require the level definition; do not instantiate every pool command.']}


def read_stage_geometry(path, part_count, material_count):
    """Read the affine matrix pool and verified command shape, without Blender."""
    path = Path(path)
    display = read_display(path, part_count)
    version = display['version']
    if version not in (21, 32):
        raise FormatError(f'Stage matrix layout not verified for DISP {version}')
    data = path.read_bytes()
    cursor = Cursor(data, display['end_offset'])
    arrays = []
    def array(element_size=None):
        at = cursor.at
        cursor.expect(b'ROTV', '4s')
        count = cursor.count(1000000)
        if element_size is not None:
            cursor.take(count * element_size)
        arrays.append({'offset':at, 'count':count, 'element_size':element_size})
        return count
    groups = array()
    for _ in range(groups):
        cursor.take(cursor.count(1000000) * 2)
    if version == 21:
        cursor.take(1)  # Retained layout byte; no rendering meaning assigned.
    for element_size in (16, 16, 64 if version == 32 else 44, 4, 4):
        array(element_size)
    if version == 32:
        cursor.expect(b'ROTV', '4s')
    matrix_offset = cursor.at
    count = cursor.count(1000000)
    matrices = []
    for _ in range(count):
        values = cursor.get('12f')
        if not all(math.isfinite(value) for value in values):
            raise FormatError('Non-finite stage matrix')
        # Source affine matrices store four rows of three floats. The omitted
        # column is (0,0,0,1); row-vector conversion stays with the caller.
        matrices.append([value for row in range(4) for value in (*values[row*3:row*3+3], float(row==3))])
    result = decode_stage_commands(display, len(matrices), part_count, material_count)
    result.update(schema='tt.stage-geometry-inventory.v1', source=str(path.resolve()),
                  display_version=version, matrix_array_offset=matrix_offset,
                  matrix_end_offset=cursor.at, matrix_arrays_before=arrays,
                  display_matrices=matrices, commands=display['commands'],
                  specials=display['specials'], clips=display['clips'])
    return result
