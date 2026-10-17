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
        if self.endian != '>':
            raise FormatError('Facial-control blocks are verified only in big-endian AN4 trees')
        at = r.get('I', actor['offset']+36)
        if not at:
            return None
        if at < 72 or self.data[at:at+4] != b'BSA\0':
            raise FormatError('Unsupported standalone AN4 facial-control block')
        header, padded, size, reserved = r.get('4I', at+4)
        if header != 20 or reserved or size < 100 or not size <= padded <= size+4 or at+padded > len(self.data):
            raise FormatError('Standalone BSA header/range is not verified')
        animation = Animation(r, at+header, at+size)
        animation.prepare(morph_channels=True)
        return animation
