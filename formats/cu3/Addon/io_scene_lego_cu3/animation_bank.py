"""Read-only observed 0x1234567A animation bank; no external extractor."""
from pathlib import Path, PurePosixPath
import struct
from .cu3 import FormatError
from .tt_deflate import decompress


class AnimationBank:
    def __init__(self, path, data=None):
        if (len(data) if data is not None else Path(path).stat().st_size) > 256 * 1024 * 1024:
            raise FormatError('Animation bank exceeds the 256 MiB limit')
        self.path, self.data = Path(path), Path(path).read_bytes() if data is None else data
        if len(self.data) < 24:
            raise FormatError('Truncated animation bank')
        magic, count, total, crc, reserved1, reserved2 = struct.unpack_from('<6I', self.data)
        if magic != 0x1234567A or total != len(self.data) or count > 65536 or 24 + count*28 > total:
            raise FormatError('Unverified animation bank layout')
        self.entries = {}
        for index in range(count):
            name_at, offset, size, kind, _, checksum, _ = struct.unpack_from('<7I', self.data, 24+index*28)
            if not 24 + count*28 <= name_at < total or not 24 + count*28 <= offset <= total or size > total-offset:
                raise FormatError('Animation bank entry exceeds bounds')
            end = self.data.find(b'\0', name_at, min(total, name_at+4096))
            if end < 0:
                raise FormatError('Unterminated animation bank name')
            try:
                name = self.data[name_at:end].decode('ascii').replace('\\', '/')
            except UnicodeDecodeError as error:
                raise FormatError('Invalid animation bank name') from error
            relative = PurePosixPath(name)
            if relative.is_absolute() or '..' in relative.parts or ':' in name or not name:
                raise FormatError('Unsafe animation bank member name')
            key = name.casefold()
            if key in self.entries:
                raise FormatError('Duplicate animation bank member')
            self.entries[key] = dict(name=name, offset=offset, size=size, kind=kind)

    def read(self, name):
        entry = self.entries.get(name.casefold())
        if entry is None:
            raise FormatError('Animation bank member missing: ' + name)
        payload = self.data[entry['offset']:entry['offset']+entry['size']]
        return decompress(payload) if payload.startswith(b'Deflate_v1.0') else payload
