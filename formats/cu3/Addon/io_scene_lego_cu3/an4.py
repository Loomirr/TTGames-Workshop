"""Observed PC AN4 trees; ANI-D poses and gated newer ANI-E inventory."""
from pathlib import Path
import hashlib
import math
from .cu3 import Reader, Animation, FormatError
from .tt_deflate import decompress


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
        if version not in (13, 14, 15, 16, 18, 19, 20) or size != len(raw) or size < 72:
            raise FormatError('Standalone AN4 requires a verified big-endian v13/14/15/16/18/19/20 tree; ANI-E is inspection only.')
        strings, children = r.get('2I', 16)
        if not 72 <= strings < size:
            raise FormatError('AN4 string table outside file')
        self.version, self.actors = version, []
        visited = set()

        def visit(at, parent, depth=0):
            if depth > 64 or at in visited or at < 72 or at + 72 > size:
                raise FormatError('Invalid or cyclic standalone AN4 hierarchy')
            visited.add(at)
            if len(visited) > 4096:
                raise FormatError('Too many AN4 nodes')
            count = r.get('H', at + 8)
            child, records, name = r.get('3I', at + 20)
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
                if rec < 72 or rec + 80 > size:
                    raise FormatError('AN4 record outside file')
                label, ani = r.get('2I', rec + 64)
                if not label or ani < 72 or ani + 80 > size:
                    raise FormatError('AN4 animation/name pointer is invalid')
                actor['records'].append(dict(index=i, offset=rec, name=r.string(strings + label - 1, size),
                    matrix=list(r.get('16f', rec)), animation=Animation(r, ani, size)))
            if count > 4096:
                raise FormatError('Too many child nodes')
            for i in range(count):
                visit(child + i * 72, actor['index'], depth + 1)

        count = r.get('H', 8)
        if count > 4096:
            raise FormatError('Too many AN4 root nodes')
        for i in range(count):
            visit(children + i * 72, None)

    def choose_actor(self, nodes, name=''):
        candidates = [a for a in self.actors if any(r['animation'].nodes == nodes for r in a['records'])
                      and (a['name'].casefold() == name.casefold() if name else a['parent'] is None)]
        if len(candidates) != 1:
            available = ', '.join(a['name'] for a in self.actors)
            raise FormatError('Specify one compatible AN4 actor by name. Available: ' + available)
        return candidates[0]
