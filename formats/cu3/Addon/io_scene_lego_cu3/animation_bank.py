"""Read-only observed 0x1234567A animation bank; no external extractor."""
from pathlib import Path
from .cu3 import FormatError
from .tt_deflate import decompress
from .pak_reader import read_pak, parse_pak


class AnimationBank:
    def __init__(self, path, data=None):
        self.path, self.data = Path(path), read_pak(path) if data is None else data
        # Validate the whole bank before any caller can decode a member.
        self.entries = {entry['name'].casefold(): entry for entry in parse_pak(self.data)}

    def read(self, name):
        entry = self.entries.get(name.casefold())
        if entry is None:
            raise FormatError('Animation bank member missing: ' + name)
        payload = self.data[entry['offset']:entry['offset']+entry['size']]
        decoded = decompress(payload, max_output=entry['decoded_size']) if entry['compressed'] else payload
        if len(decoded) != entry['decoded_size']:
            raise FormatError('Animation bank member decoded size mismatch')
        if decoded.startswith(b'Deflate_v1.0'):
            raise FormatError('Nested TT deflate member framing is not verified')
        return decoded
