"""Bounded, explicit TCS character layer selection for static inspection.

Only a matching sibling definition's layers_high directive is interpreted.
Missing, conflicting and unsupported definitions leave all native layers visible.
No definition includes, alternate costumes, runtime switches or inferred LODs.
"""
import re
from pathlib import Path

MAX_DEFINITION_BYTES = 1024 * 1024


def parse_high_layers(text, layer_count):
    """Return native indices, or raise ValueError rather than guess visibility."""
    if not isinstance(layer_count, int) or not 0 < layer_count <= 4096:
        raise ValueError('Invalid native layer count')
    directives = []
    for raw in text.lstrip('\ufeff').splitlines():
        line = re.split(r'//|;', raw, maxsplit=1)[0].strip()
        if re.match(r'layers_high\b', line, re.IGNORECASE):
            directives.append(line)
    if not directives:
        raise ValueError('No explicit layers_high directive; includes and other detail levels are not inferred')
    if len(directives) != 1:
        raise ValueError('Multiple layers_high directives; visibility is ambiguous')
    match = re.fullmatch(r'layers_high\s*=\s*([0-9]+(?:\s*,\s*[0-9]+)*)',
                         directives[0], re.IGNORECASE)
    if not match:
        raise ValueError('Unsupported layers_high syntax; expected comma-separated nonnegative indices')
    fields = re.split(r'\s*,\s*', match.group(1))
    if len(fields) > layer_count or any(len(value) > 10 for value in fields):
        raise ValueError('layers_high exceeds the native layer table')
    indices = [int(value) for value in fields]
    if len(set(indices)) != len(indices):
        raise ValueError('Duplicate native index in layers_high')
    if any(index >= layer_count for index in indices):
        raise ValueError('layers_high references an index outside the native layer table')
    return indices


def configured_layers(model_path, layer_count):
    """Resolve a same-stem TXT beside a PC GHG; report a reversible fallback."""
    path = Path(model_path)
    result = dict(status='all_layers_fallback', definition=None, selected=None,
                  reason=None, directive='layers_high')
    stem = path.stem
    if stem.casefold().endswith('_pc'):
        stem = stem[:-3]
    wanted = (stem + '.txt').casefold()
    try:
        candidates = [p for p in path.parent.iterdir()
                      if p.name.casefold() == wanted and p.is_file()]
        if len(candidates) != 1:
            result['reason'] = ('No matching sibling character TXT' if not candidates
                                else 'Ambiguous case-insensitive sibling character TXT names')
            return result
        definition = candidates[0]
        result['definition'] = str(definition)
        with definition.open('rb') as stream:
            data = stream.read(MAX_DEFINITION_BYTES + 1)
        if len(data) > MAX_DEFINITION_BYTES:
            raise ValueError('Character TXT exceeds the 1 MiB inspection limit')
        if b'\0' in data:
            raise ValueError('Character TXT contains NUL bytes; unsupported text encoding')
        text = data.decode('utf-8-sig') if data.startswith(b'\xef\xbb\xbf') else data.decode('latin-1')
        result['selected'] = parse_high_layers(text, layer_count)
        result['status'] = 'configured_high'
    except (OSError, ValueError, UnicodeError) as error:
        result['reason'] = str(error)
    return result
