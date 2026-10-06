"""Portable archive path checks, with Windows aliases checked on every host.

This module has no Blender dependency. Names retain their source spelling;
case folding is used only to diagnose ambiguous output paths.
"""
from pathlib import Path
import os


def safe_path(name):
    if not isinstance(name, str):
        raise ValueError('Unsafe archive path: expected text')
    name = name.replace('\\', '/')
    parts = name.split('/')
    if not name or len(name) > 4096 or any(part in ('', '.', '..') for part in parts):
        raise ValueError('Unsafe archive path')
    for part in parts:
        # TT's verified archive layouts use ASCII. Do not silently replace
        # undecodable characters or accept platform-dependent Unicode aliases.
        if (not part.isascii() or len(part) > 255 or part[-1] in '. ' or
                any(ord(char) < 32 or ord(char) == 127 or char in '<>:"|?*' for char in part)):
            raise ValueError('Unsafe archive filename')
        stem = part.split('.', 1)[0].rstrip(' .').upper()
        if (stem in {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'} or
                len(stem) == 4 and stem[:3] in {'COM', 'LPT'} and stem[3] in '123456789'):
            raise ValueError('Reserved Windows device name in archive path')
    return '/'.join(parts)


def validate_paths(names):
    """Reject duplicate files, file/directory conflicts and case aliases."""
    paths, spellings, files = [], {}, set()
    for value in names:
        name = safe_path(value)
        parts = name.split('/')
        for length in range(1, len(parts) + 1):
            spelling = '/'.join(parts[:length])
            key = spelling.casefold()
            prior = spellings.get(key)
            if prior is not None and prior != spelling:
                raise ValueError(f'Case-colliding archive paths: {prior!r} and {spelling!r}')
            spellings[key] = spelling
            if length < len(parts) and key in files:
                raise ValueError(f'Archive file is also a directory: {spelling!r}')
        key = name.casefold()
        if key in files:
            raise ValueError(f'Duplicate archive output path: {name!r}')
        files.add(key)
        paths.append(name)
    for key in files:
        parts = key.split('/')
        if any('/'.join(parts[:length]) in files for length in range(1, len(parts))):
            raise ValueError('Archive file/directory output collision')
    return paths


def preflight_destination(destination, names, *, require_absent=False):
    """Check every output before decoding/writing; never creates directories.

    Existing links, non-directory parents, case aliases and existing targets
    are rejected. The write itself must still create files exclusively; this
    preflight does not claim to lock an output tree against other processes.
    """
    paths = validate_paths(names)
    root = Path(os.path.abspath(Path(destination).expanduser()))
    if require_absent and os.path.lexists(root):
        raise FileExistsError(f'Choose a new extraction destination: {root}')
    targets = [root.joinpath(*name.split('/')) for name in paths]
    checked = set()
    for target in [root, *targets]:
        for current in [*reversed(target.parents), target]:
            if current in checked:
                continue
            checked.add(current)
            if current.is_symlink() or (hasattr(current, 'is_junction') and current.is_junction()):
                raise ValueError(f'Archive destination contains a symbolic link: {current}')
            if current.parent.exists():
                for sibling in current.parent.iterdir():
                    if sibling.name != current.name and sibling.name.casefold() == current.name.casefold():
                        raise ValueError(f'Archive destination has a case alias: {current}')
            if os.path.lexists(current):
                if current == target and target != root:
                    raise FileExistsError(f'Archive output already exists: {target}')
                if not current.is_dir():
                    raise ValueError(f'Archive output parent is not a directory: {current}')
    return root, targets
