"""Observed PC AN4 trees; ANI-D poses and gated newer ANI-E inventory."""
from pathlib import Path
import hashlib
import math
from .cu3 import Reader, Animation, FormatError
from .tt_deflate import decompress


# LEGO Batman 2 (docs/LB2_ANIMATION.md): big-endian trees 2 and 4-7 with the
# 72-byte header and nodes, and little-endian trees 1 and 2 with 44-byte header
# and nodes (the same node fields up to +36). Records are 80 bytes in both.
LB2_BIG_ENDIAN = (2, 4, 5, 6, 7)
LB2_LITTLE_ENDIAN = (1, 2)


class AnimationFile:
    def __init__(self, path, fps=30, data=None):
        self.path = Path(path)
        raw = self.path.read_bytes() if data is None else data
        self.name = self.path.stem
        self.sha256 = hashlib.sha256(raw).hexdigest()
        self.fps = fps
        if not math.isfinite(fps) or not 0 < fps < 1000:
            raise FormatError('Invalid preview FPS')
        if raw.startswith(b'Deflate_v1.0'):
            raw = decompress(raw)
        self.data = raw
        r = Reader(raw)
        version, size = r.get('2I', 0)
        endian, head = '>', 72
        if len(raw) >= 8 and r.get('I', 0, '<') in LB2_LITTLE_ENDIAN and r.get('I', 4, '<') == len(raw):
            version, size = r.get('2I', 0, '<')
            endian, head = '<', 44
        elif version not in (*LB2_BIG_ENDIAN, 13, 14, 15, 16, 18, 19, 20):
            size = -1
        if size != len(raw) or size < head:
            raise FormatError('Standalone AN4 requires a verified big-endian v2/4-7/13-16/18-20 tree or a '
                              'little-endian LB2 v1/2 tree; ANI-E is inspection only.')
        self.endian, self.header_size = endian, head
        get = lambda fmt, at: r.get(fmt, at, endian)
        strings, children = get('2I', 16)
        if not head <= strings < size:
            raise FormatError('AN4 string table outside file')
        self.version, self.actors = version, []
        visited = set()

        def visit(at, parent, depth=0):
            if depth > 64 or at in visited or at < head or at + head > size:
                raise FormatError('Invalid or cyclic standalone AN4 hierarchy')
            visited.add(at)
            if len(visited) > 4096:
                raise FormatError('Too many AN4 nodes')
            count = get('H', at + 8)
            child, records, name = get('3I', at + 20)
            if not name:
                raise FormatError('Invalid one-based AN4 actor name')
            actor = dict(index=len(self.actors), offset=at, parent=parent,
                         name=r.string(strings + name - 1, size), records=[])
            self.actors.append(actor)
            number = r.get('B', at + 12)
            if number and not records:
                raise FormatError('AN4 record table missing')
            for i in range(number):
                rec = records + i * 80
                if rec < head or rec + 80 > size:
                    raise FormatError('AN4 record outside file')
                label, ani = get('2I', rec + 64)
                if not label or ani < head or ani + 80 > size:
                    raise FormatError('AN4 animation/name pointer is invalid')
                actor['records'].append(dict(index=i, offset=rec, name=r.string(strings + label - 1, size),
                    matrix=list(get('16f', rec)), animation=Animation(r, ani, size)))
            if count > 4096:
                raise FormatError('Too many child nodes')
            for i in range(count):
                visit(child + i * head, actor['index'], depth + 1)

        count = get('H', 8)
        if count > 4096:
            raise FormatError('Too many AN4 root nodes')
        for i in range(count):
            visit(children + i * head, None)

    def choose_actor(self, nodes, name=''):
        candidates = [a for a in self.actors if any(r['animation'].nodes == nodes for r in a['records'])
                      and (a['name'].casefold() == name.casefold() if name else a['parent'] is None)]
        if len(candidates) != 1:
            available = ', '.join(a['name'] for a in self.actors)
            raise FormatError('Specify one compatible AN4 actor by name. Available: ' + available)
        return candidates[0]

    def morph_animation(self, actor):
        """Standalone BE node +36 points to a bounded BE BSA/ANI-D block.

        CU3 embeds a different, little-endian tree. Keep its decoder separate.
        """
        r = Reader(self.data)
        # LEGO Batman 2's little-endian trees (44-byte nodes) keep the
        # pointer in the node's last word and write the magic reversed
        # (docs/LB2_FACES.md).
        little = self.endian == '<'
        at = r.get('I', actor['offset'] + (40 if little else 36), self.endian)
        if not at:
            return None
        if at < self.header_size or self.data[at:at+4] != (b'\0ASB' if little else b'BSA\0'):
            raise FormatError('Unsupported standalone AN4 facial-control block')
        header, padded, size, reserved = r.get('4I', at+4, self.endian)
        if little:
            # These three words are file offsets there, not block sizes.
            header, padded, size = header - at, padded - at, size - at
        # Only the observed bytes 01 01 00 00 are accepted for LB2 trees.
        # Keeping the word opaque does not justify accepting arbitrary flags.
        allowed_reserved = {0}
        if self.version in LB2_BIG_ENDIAN + LB2_LITTLE_ENDIAN:
            allowed_reserved.add(0x101 if little else 0x01010000)
        if header != 20 or reserved not in allowed_reserved or size < 100 \
                or not size <= padded <= size+4 or at+padded > len(self.data):
            raise FormatError('Standalone BSA header/range is not verified')
        animation = Animation(r, at+header, at+size)
        animation.bsa_reserved = reserved
        animation.prepare(morph_channels=True)
        return animation
