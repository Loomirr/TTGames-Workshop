"""Case-insensitive lookup under an explicitly selected extracted asset root."""
from pathlib import Path, PurePosixPath
import hashlib
from .cu3 import FormatError


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
        for path in self.root.rglob('*'):
            if path.is_file() and path.suffix.lower() in ('.ghg', '.gsc', '.cd', '.tex', '.nxg_textures', '.cu3', '.an4', '.as', '.pak', '.txt', '.led'):
                # Do not follow a link outside the selected asset tree.
                if path.resolve().is_relative_to(self.root):
                    self.files.setdefault(path.name.casefold(), []).append(path)

    def find_exact(self, reference, required=True):
        return self.find(reference, required=required, exact=True)

    def find(self, reference, suffix='', extension='', required=True, exact=False):
        clean = str(reference).replace('\\', '/')
        if clean.startswith('/'):
            raise FormatError('Asset reference must be relative to the selected game root')
        parts = PurePosixPath(clean).parts
        if not parts or '..' in parts or ':' in clean:
            raise FormatError('Asset reference must be relative to the selected game root')
        basename = PurePosixPath(clean).name
        if extension:
            stem = PurePosixPath(basename).stem
            if suffix and not stem.casefold().endswith(suffix.casefold()):stem += suffix
            basename = stem + extension
        candidates = self.files.get(basename.casefold(), [])
        if exact:
            ending = '/'.join((*parts[:-1], basename)).casefold()
            candidates = [p for p in candidates if p.relative_to(self.root).as_posix().casefold()==ending]
        elif len(candidates) > 1 and len(parts) > 1:
            ending = '/'.join((*parts[:-1], basename)).casefold()
            exact = [p for p in candidates if p.as_posix().casefold().endswith('/'+ending)]
            if exact:
                candidates = exact
        if len(candidates) > 1:
            hashes = {hashlib.sha256(p.read_bytes()).digest() for p in candidates}
            if len(hashes) == 1:
                return sorted(candidates)[0]
            raise FormatError(f'Ambiguous asset reference: {reference}; multiple different files match')
        if candidates:
            return candidates[0]
        if required:
            raise FormatError(f'Missing asset: {basename}')
        return None
