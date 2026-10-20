"""Deterministic batch discovery; no Blender or archive extraction required."""
from pathlib import PurePosixPath


def catalog_paths(assets, scope='CHARACTERS', search=''):
    if scope not in ('CHARACTERS', 'VEHICLES', 'DEFINITIONS', 'MODELS', 'ALL'):
        raise ValueError('Unknown batch scope')
    classic = getattr(assets, 'profile', None) in ('LB1', 'TCS')
    paths = {}
    for name, entries in assets.files.items():
        if not name.lower().endswith(('.cd', '.ghg', '.gsc')):
            continue
        for entry in entries:
            path = (entry[1]['path'] if isinstance(entry, tuple)
                    else entry.relative_to(assets.root).as_posix()).replace('\\', '/')
            lower = path.lower()
            suffix = PurePosixPath(lower).suffix
            character = (suffix == '.ghg' and lower.startswith('chars/') and '_lr_pc.' not in lower) if classic else (
                suffix == '.cd' and '/super_char' not in '/' + lower and (
                    any(c in '/' + lower for c in ('/minifig', '/small/', '/bigfig', '/biggerfig', '/creature')) or '/' not in lower))
            vehicle = suffix in ('.ghg', '.gsc') and any(
                part in ('vehicles', 'vehicle', 'cars', 'car', 'boats', 'planes') for part in lower.split('/')[:-1])
            include = {'CHARACTERS': character, 'VEHICLES': vehicle,
                       'DEFINITIONS': suffix == '.cd', 'MODELS': suffix in ('.ghg', '.gsc'),
                       'ALL': suffix in ('.cd', '.ghg', '.gsc')}[scope]
            if include and search.casefold() in lower.casefold():
                paths.setdefault(lower, path)
    return sorted(paths.values(), key=lambda p: (p.casefold(), p))


def select_paths(paths, start=0, limit=20):
    if start < 0 or limit < 0:
        raise ValueError('Start and limit must be nonnegative')
    return paths[start:start + limit] if limit else paths[start:]
