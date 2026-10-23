"""Case-insensitive lookup under an explicitly selected extracted asset root."""
from pathlib import Path, PurePosixPath
import os
from .cu3 import FormatError
from .resource_identity import logical_reference


ASSET_EXTENSIONS = frozenset(('.ghg', '.gsc', '.cd', '.tex', '.nxg_textures',
    '.cu3', '.an4', '.as', '.pak', '.txt', '.led', '.cu2', '.an3', '.giz'))


def _asset_paths(root):
    """Enumerate fresh entries without resolving every ordinary file on Windows.

    Directory containment is checked before descending. File links receive their
    own check; lookups recheck containment in case a directory was replaced.
    Do not recurse through directory links or junctions (including cycles).
    """
    pending = [root]
    while pending:
        directory = pending.pop()
        if not directory.resolve().is_relative_to(root):
            continue
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    reparse = (os.name == 'nt' and
                        getattr(entry.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400)
                    if not entry.is_symlink() and not reparse:
                        pending.append(Path(entry.path))
                elif os.path.splitext(entry.name)[1].casefold() in ASSET_EXTENSIONS and entry.is_file():
                    path = Path(entry.path)
                    if not entry.is_symlink() or path.resolve().is_relative_to(root):
                        yield path


def open_assets(root, profile, cache_root=None):
    """Use an extracted asset tree or a supported installed game folder."""
    if not str(root).strip():
        raise FormatError('Choose an installed game or extracted asset folder')
    path = Path(root).expanduser().resolve()
    if not path.is_dir():
        raise FormatError('Choose an installed game or extracted asset folder')
    if any(p.is_file() and p.suffix.casefold()=='.dat' and p.stem.upper().startswith('GAME') for p in path.iterdir()):
        from .archive_assets import ArchiveAssetIndex
        return ArchiveAssetIndex(path, profile, cache_root)
    assets = AssetIndex(path)
    assets.profile = profile
    return assets


class AssetIndex:
    def __init__(self, root):
        if not str(root).strip():
            raise FormatError('Choose a folder containing extracted game assets')
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise FormatError('Choose a folder containing extracted game assets')
        self.files = {}
        for path in _asset_paths(self.root):
            self.files.setdefault(path.name.casefold(), []).append(path)

    def find_exact(self, reference, required=True):
        return self.find(reference, required=required, exact=True)

    def find(self, reference, suffix='', extension='', required=True, exact=False):
        clean = logical_reference(reference)
        parts = PurePosixPath(clean).parts
        basename = PurePosixPath(clean).name
        if extension:
            stem = PurePosixPath(basename).stem
            if suffix and not stem.casefold().endswith(suffix.casefold()):stem += suffix
            basename = stem + extension
        candidates = self.files.get(basename.casefold(), [])
        if exact or len(parts) > 1:
            ending = '/'.join((*parts[:-1], basename)).casefold()
            candidates = [p for p in candidates if p.relative_to(self.root).as_posix().casefold()==ending]
        if len(candidates) > 1:
            paths = sorted(p.relative_to(self.root).as_posix() for p in candidates)
            collision = len({p.casefold() for p in paths}) < len(paths)
            reason = 'case-colliding logical paths' if collision else 'ambiguous basenames in different logical paths'
            # Identical bytes do not establish resource ownership or equal
            # companions. A DLC clone may have different sibling dependencies.
            raise FormatError(f'Ambiguous asset reference: {reference}; {reason}: ' + ', '.join(paths))
        if candidates:
            if not candidates[0].resolve().is_relative_to(self.root):
                raise FormatError('Asset link escapes selected asset folder')
            return candidates[0]
        if required:
            raise FormatError('Missing asset: ' + '/'.join((*parts[:-1], basename)))
        return None
