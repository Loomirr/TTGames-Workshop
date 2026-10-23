"""Observed animation banks, with guarded ordered-member replacement."""
import hashlib
import struct
from pathlib import Path
from .cu3 import FormatError
from .tt_deflate import decompress
from .pak_reader import read_pak, parse_pak, MAX_PACKED


class AnimationBank:
    def __init__(self, path, data=None):
        self.path, self.data = Path(path), read_pak(path) if data is None else data
        # Validate the whole bank before any caller can decode a member.
        self.entries = {entry['name'].casefold(): entry for entry in parse_pak(self.data)}

    def _member(self, name):
        entry = self.entries.get(name.casefold())
        if entry is None:
            raise FormatError('Animation bank member missing: ' + name)
        payload = self.data[entry['offset']:entry['offset']+entry['size']]
        decoded = decompress(payload, max_output=entry['decoded_size']) if entry['compressed'] else payload
        if len(decoded) != entry['decoded_size']:
            raise FormatError('Animation bank member decoded size mismatch')
        if decoded.startswith(b'Deflate_v1.0'):
            raise FormatError('Nested TT deflate member framing is not verified')
        return payload, decoded

    def read(self, name):
        """Return decoded bytes for inspection and imported-source identity."""
        return self._member(name)[1]

    def read_stored(self, name):
        """Return validated original member bytes, retaining native compression."""
        return self._member(name)[0]

    def replace_members(self, replacements, expected_sha256):
        """Return a separate bank using the measured LMSH1 ordered layout.

        Preserve prefix metadata and entry order, with two zero bytes after
        each payload and four-byte alignment before the next payload. Other
        layouts remain readable but cannot be rewritten by this writer.
        """
        data = self.data
        if hashlib.sha256(data).hexdigest() != expected_sha256:
            raise FormatError('Animation bank changed since import')
        entries = list(self.entries.values())
        if not entries or any(entry['kind'] != 4 for entry in entries):
            raise FormatError('Bank export requires the observed animation entry layout')
        if struct.unpack_from('<2I', data, 16) != (0, 0):
            raise FormatError('Bank flags/checksum layout is not supported for export')
        first = entries[0]['offset']
        table_end = 24 + 28 * len(entries)
        if first < table_end or any(entry['offset'] % 4 for entry in entries):
            raise FormatError('Bank export requires aligned, ordered payloads')
        for index, entry in enumerate(entries):
            name_at = struct.unpack_from('<I', data, 24 + 28 * index)[0]
            if not table_end <= name_at < first or data.find(b'\0', name_at, first) < 0:
                raise FormatError('Bank names must precede all payloads for export')
            end = entry['offset'] + entry['size']
            following = entries[index + 1]['offset'] if index + 1 < len(entries) else len(data)
            wanted = (end + 5) & ~3 if index + 1 < len(entries) else end + 2
            if following != wanted or any(data[end:following]):
                raise FormatError('Bank payload order or padding is not supported for export')
        changes = {}
        for name, value in replacements.items():
            key = name.casefold()
            if key not in self.entries or key in changes:
                raise FormatError('Unknown or duplicate animation bank replacement: ' + name)
            if not isinstance(value, bytes) or not value:
                raise FormatError('Animation bank replacement must be nonempty bytes')
            changes[key] = value

        def build(overrides):
            size = first
            for index, entry in enumerate(entries):
                payload = overrides.get(entry['name'].casefold())
                size += (len(payload) if payload is not None else entry['size']) + 2
                if index + 1 < len(entries):
                    size = (size + 3) & ~3
                if size > MAX_PACKED:
                    raise FormatError('Rebuilt animation bank exceeds packed-byte limit')
            output = bytearray(data[:first])
            for index, entry in enumerate(entries):
                payload = overrides.get(entry['name'].casefold())
                if payload is None:
                    payload = data[entry['offset']:entry['offset'] + entry['size']]
                offset = len(output)
                output.extend(payload)
                output.extend(b'\0\0')
                if index + 1 < len(entries):
                    output.extend(bytes((-len(output)) % 4))
                struct.pack_into('<2I', output, 28 + 28 * index, offset, len(payload))
            struct.pack_into('<I', output, 8, len(output))
            return bytes(output)

        if build({}) != data:
            raise FormatError('Animation bank cannot be reconstructed byte-for-byte')
        result = build(changes)
        checked = AnimationBank(self.path, data=result)
        if list(checked.entries) != list(self.entries):
            raise FormatError('Rebuilt animation bank member identities changed')
        for key, old in self.entries.items():
            new = checked.entries[key]
            if any(new[field] != old[field] for field in ('name', 'kind', 'crc', 'compressed')):
                raise FormatError('Rebuilt animation bank member metadata or storage changed')
            original = self.read_stored(key)  # Validate every source member too.
            if checked.read_stored(key) != changes.get(key, original):
                raise FormatError('Rebuilt animation bank member verification failed')
        return result
