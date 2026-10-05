"""Read-only installed-game companion lookup with an external extraction cache.

Only requested files are decoded. Installed archives are never modified.
The observed LB3 -6 index follows the format documented by ttgames.bms;
this bounded implementation and chunk decoder use no external runtime.
"""
from pathlib import Path, PurePosixPath
import hashlib
import os
import secrets
import struct
from .cu3 import FormatError
from .archive_compression import decode_entry


def _safe_path(name):
    name = name.replace('\\', '/')
    parts = PurePosixPath(name).parts
    if len(name)>4096 or not parts or name.startswith('/') or ':' in name or any(p in ('', '.', '..') for p in name.split('/')):
        raise FormatError('Unsafe archive asset path')
    for part in parts:
        stem = part.split('.',1)[0].upper()
        if (len(part)>255 or part[-1] in '. ' or any(ord(c)<32 or c in '<>"|?*' for c in part) or
                stem in ('CON','PRN','AUX','NUL') or
                len(stem)==4 and stem[:3] in ('COM','LPT') and stem[3] in '123456789'):
            raise FormatError('Unsafe or reserved archive asset filename')
    return '/'.join(parts)


def _path_hash(name):
    value = 0x811c9dc5
    for byte in name.upper().replace('/', '\\').encode('ascii'):
        value = ((value ^ byte) * 0x199933) & 0xffffffff
    return value


def index_v6(path):
    path = Path(path)
    archive_size = path.stat().st_size
    with path.open('rb') as stream:
        header = stream.read(8)
        if len(header) != 8:
            raise FormatError('Truncated DAT header')
        offset, size = struct.unpack('<II', header)
        if offset & 0x80000000:
            offset = ((offset ^ 0xffffffff) << 8) + 256
        if not 8 <= offset <= archive_size or not 8 <= size <= min(256 * 1024 * 1024, archive_size - offset):
            raise FormatError('DAT index exceeds archive bounds')
        stream.seek(offset)
        data = stream.read(size)
    def get(fmt, at):
        n = struct.calcsize('<' + fmt)
        if at < 0 or at + n > len(data):
            raise FormatError('DAT index table exceeds bounds')
        values = struct.unpack_from('<' + fmt, data, at)
        return values[0] if len(values) == 1 else values
    version, count = get('iI', 0)
    if version != -6 or not 0 < count <= 1000000:
        raise FormatError('Unverified DAT index version/count')
    names_at = 8 + count * 16
    names_count = get('I', names_at)
    if not 0 < names_count <= 1000000:
        raise FormatError('Unreasonable DAT name count')
    names_at += 4
    strings_at = names_at + names_count * 12 + 4
    strings_size = get('I', strings_at - 4)
    hashes_at = strings_at + strings_size
    if not strings_size or hashes_at + count * 4 > len(data):
        raise FormatError('DAT strings or hashes exceed index')
    by_hash = {}
    for i in range(count):
        key = get('I', hashes_at + i * 4)
        if key in by_hash:
            raise FormatError('Ambiguous DAT path hash')
        by_hash[key] = i
    folders, mapped = {}, {}
    for i in range(names_count):
        child, previous, name_offset, parent = get('hhiI', names_at + i * 12)
        name = ''
        if name_offset >= 0:
            start = strings_at + name_offset
            if start >= hashes_at:
                raise FormatError('DAT name outside string table')
            end = data.find(b'\0', start, hashes_at)
            if end < 0:
                raise FormatError('Unterminated DAT path name')
            name = data[start:end].decode('ascii')
        prefix = folders.get(parent, '')
        if len(name)>255 or len(prefix)+len(name)>4096:
            raise FormatError('DAT path exceeds supported name/depth limits')
        folders[i] = prefix
        if child > 0:
            folders[i] = prefix + name + '\\'
            continue
        if not name:
            continue
        full = _safe_path((prefix + name).lstrip('\\').upper())
        number = by_hash.get(_path_hash(full))
        if number is None or number in mapped:
            raise FormatError('DAT path has no unique matching file hash')
        low, packed, raw, flags = get('4I', 8 + number * 16)
        file_offset = (low << 8) | (flags >> 24)
        if (file_offset < 8 or file_offset + packed > archive_size or
                file_offset < offset + size and file_offset + packed > offset):
            raise FormatError('DAT file extent overlaps header/index or exceeds payload region')
        mapped[number] = {'path':full,'offset':file_offset,'packed_size':packed,'size':raw,'flags':flags & 0xffffff}
    if len(mapped) != count:
        raise FormatError('DAT index contains unresolved file paths')
    return [mapped[i] for i in range(count)]


class ArchiveAssetIndex:
    """AssetIndex-compatible provider for supported installed LB3/LMSH1 DATs."""
    def __init__(self, root, profile, cache_root=None):
        self.game_root = Path(root).resolve()
        if profile not in ('LB3', 'LMSH1'):
            raise FormatError('Installed archive assembly is verified only for LB3 and LMSH1')
        archives = sorted(p for p in self.game_root.iterdir() if p.is_file() and p.suffix.casefold()=='.dat'
                          and p.stem.upper().startswith(('GAME','DLC')))
        if not archives:
            raise FormatError('No supported game archives in the selected folder')
        if cache_root is None:
            base = Path(os.environ['LOCALAPPDATA']) if os.environ.get('LOCALAPPDATA') else Path.home() / '.cache'
            cache_root = base / 'TTGamesWorkshop' / 'asset-cache'
        cache_root = Path(cache_root).expanduser().resolve()
        if cache_root.is_relative_to(self.game_root):
            raise FormatError('Choose an extraction cache outside the installed game')
        fingerprint = hashlib.sha256()
        fingerprint.update(str(self.game_root).encode('utf-8'))
        for archive in archives:
            stat = archive.stat()
            fingerprint.update(f'{archive.name}:{stat.st_size}:{stat.st_mtime_ns}'.encode('utf-8'))
        self.root = cache_root / (profile.lower() + '-' + fingerprint.hexdigest()[:20])
        self.cache_base = cache_root
        self._validate_cache_root()
        self.files, self.events = {}, []
        if profile == 'LMSH1':
            from .archive_v5 import index_v5
            reader = index_v5
        else:
            reader = index_v6
        for archive in archives:
            for entry in reader(archive):
                if PurePosixPath(entry['path']).suffix.casefold() in ('.ghg','.gsc','.cd','.tex','.nxg_textures','.cu3','.an4','.txt','.led'):
                    self.files.setdefault(PurePosixPath(entry['path']).name.casefold(), []).append((archive, entry))
        self.profile, self.archive_count = profile, len(archives)

    def _validate_cache_root(self):
        resolved = self.root.resolve()
        if not resolved.is_relative_to(self.cache_base) or resolved.is_relative_to(self.game_root):
            raise FormatError('Archive cache link escapes its selected directory or points into the game')
        return resolved

    def _read(self, archive, entry):
        if entry['packed_size'] > 256 * 1024 * 1024 or entry['size'] > 256 * 1024 * 1024:
            raise FormatError('Requested archive companion exceeds the 256 MiB limit')
        with archive.open('rb') as stream:
            stream.seek(entry['offset'])
            packed = stream.read(entry['packed_size'])
        if len(packed) != entry['packed_size']:
            raise FormatError('Archive changed or companion payload is truncated')
        return decode_entry(packed, entry['size'])

    @staticmethod
    def _atomic_write(target, data):
        temporary = target.with_name(target.name + '.' + secrets.token_hex(8) + '.tmp')
        try:
            with temporary.open('xb') as output:
                output.write(data)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()

    def find_exact(self, reference, required=True):
        return self.find(reference, required=required, exact=True)

    def find(self, reference, suffix='', extension='', required=True, exact=False):
        clean = _safe_path(str(reference))
        parts = PurePosixPath(clean).parts
        basename = parts[-1]
        if extension:
            stem = PurePosixPath(basename).stem
            if suffix and not stem.casefold().endswith(suffix.casefold()):
                stem += suffix
            basename = stem + extension
        candidates = self.files.get(basename.casefold(), [])
        if exact:
            ending = '/'.join((*parts[:-1],basename)).casefold()
            candidates = [(a,e) for a,e in candidates if e['path'].casefold()==ending]
        elif len(candidates) > 1 and len(parts) > 1:
            ending = '/'.join((*parts[:-1],basename)).casefold()
            matches = [(a,e) for a,e in candidates if e['path'].casefold()==ending or e['path'].casefold().endswith('/'+ending)]
            if matches:
                candidates = matches
        if not candidates:
            if required:
                raise FormatError('Missing archive companion: ' + basename)
            return None
        archive, entry = candidates[0]
        if entry['packed_size'] > 256 * 1024 * 1024 or entry['size'] > 256 * 1024 * 1024:
            raise FormatError('Requested archive companion exceeds the 256 MiB limit')
        cache_boundary = self._validate_cache_root()
        target = self.root / _safe_path(entry['path'])
        digest_file = target.with_name(target.name + '.sha256')
        if not target.resolve().is_relative_to(cache_boundary) or not digest_file.resolve().is_relative_to(cache_boundary):
            raise FormatError('Archive cache target escapes selected cache')
        if target.is_file() and digest_file.is_file() and len(candidates)==1:
            if digest_file.stat().st_size != 64:
                raise FormatError('Cached companion digest is damaged; choose a fresh cache folder')
            digest = digest_file.read_text(encoding='ascii').strip()
            if (target.stat().st_size != entry['size'] or len(digest)!=64 or
                    hashlib.sha256(target.read_bytes()).hexdigest()!=digest):
                raise FormatError('Cached companion was modified or damaged; choose a fresh cache folder')
            return target
        data = self._read(archive, entry)
        if any(self._read(a,e)!=data for a,e in candidates[1:]):
            raise FormatError('Ambiguous archive asset reference: ' + str(reference))
        if target.exists():
            if target.read_bytes() != data:
                raise FormatError('Existing cached companion differs; choose a fresh cache folder')
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write(target, data)
            self.events.append({'path':entry['path'],'bytes':len(data),'archive':archive.name})
        self._atomic_write(digest_file, hashlib.sha256(data).hexdigest().encode('ascii'))
        return target

    def get_info(self):
        return {'kind':'installed_archives','profile':self.profile,'archive_count':self.archive_count,
                'cache':str(self.root),'extracted_files':len(self.events),
                'scope':'Requested model, definition, texture, configuration and declared stage companions. Installed archives are read only; extraction does not establish rendering fidelity.'}
