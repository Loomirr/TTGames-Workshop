"""Read explicit LSW1 PC character layer sets without executing script text."""
from pathlib import Path
import re


LAYER_SETS = ('special', 'high', 'medium', 'low', 'dead')


def strip_comments(text):
    result = list(text)
    i = 0
    quoted = False
    block = False
    while i < len(text):
        if block:
            if text[i:i+2] == '*/':
                result[i:i+2] = '  '
                block = False
                i += 2
                continue
            if text[i] not in '\r\n':
                result[i] = ' '
        elif quoted:
            if text[i] == '"':
                quoted = False
        elif text[i] == '"':
            quoted = True
        elif text[i:i+2] == '/*':
            result[i:i+2] = '  '
            block = True
            i += 2
            continue
        elif text[i:i+2] == '//' or text[i] == ';':
            while i < len(text) and text[i] not in '\r\n':
                result[i] = ' '
                i += 1
            continue
        i += 1
    if block or quoted:
        raise ValueError('Unterminated comment or string in LSW1 character definition')
    return ''.join(result)


def parse_layer_sets(text, only=None):
    """Top-level layer declarations only; animation overrides stay separate."""
    result = {}
    blocks = []
    for number, line in enumerate(strip_comments(text).splitlines(), 1):
        line = line.strip()
        boundary = re.match(r'^(\w+)_(start|end)\b', line, re.I)
        if boundary:
            name, direction = (v.lower() for v in boundary.groups())
            if direction == 'start':
                blocks.append(name)
            elif not blocks or blocks.pop() != name:
                raise ValueError(f'Unmatched definition block at line {number}')
            continue
        if blocks:
            continue
        field = re.match(r'^layers_(special|high|medium|low|dead)\b(.*)$', line, re.I)
        if not field:
            continue
        name, value = field.groups()
        name = name.lower()
        if only is not None and name != only:
            continue
        if name in result:
            raise ValueError(f'Duplicate layers_{name} declaration at line {number}')
        if not re.fullmatch(r'\s*=\s*\d+(?:\s*,\s*\d+)*\s*', value):
            raise ValueError(f'Invalid layers_{name} list at line {number}')
        indices = [int(v.strip()) for v in value.split('=', 1)[1].split(',')]
        if len(indices) > 32 or any(i >= 32 for i in indices):
            raise ValueError(f'layers_{name} exceeds supported LSW1 layer bounds')
        result[name] = list(dict.fromkeys(indices))
    if blocks:
        raise ValueError('Unclosed block in LSW1 character definition')
    return result


def companion(path, suffix):
    """Same-stem sibling only; refuse case collisions on case-sensitive hosts."""
    path = Path(path)
    expected = path.stem.casefold() + suffix
    matches = [p for p in path.parent.iterdir() if p.name.casefold() == expected and p.is_file()]
    if len(matches) != 1:
        raise ValueError(f'Expected one {path.stem}{suffix} beside {path.name}; found {len(matches)}')
    return matches[0]


def read_layer_set(path, name, layer_count):
    if name not in LAYER_SETS:
        raise ValueError('Unknown LSW1 definition layer set')
    path = Path(path)
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('LSW1 character definition is too large')
    with path.open('rb') as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('LSW1 character definition is too large')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('latin1')
    sets = parse_layer_sets(text, only=name)
    if name not in sets:
        raise ValueError(f'{path.name} has no layers_{name} declaration; choose automatic model layers')
    selected = sets[name]
    missing = [i for i in selected if i >= layer_count]
    if missing:
        raise ValueError(f'{path.name}: layers_{name} references unavailable layers {missing}; model has {layer_count}')
    return selected
