"""LEGO Star Wars II (2006, PC) character animations (.an3, tag '4INA'): reading, and proof of which
skeleton a clip belongs to. Plain Python.

Block layout (little-endian; pointers relative to the block's start):
    u32 tag, u16 nodes, u16 frames, u16 curve group size, u16 original frames, u16 curve count,
    u16 first frame, u8 end frames, u8 short count, u8 fixed up, 5 pad,
    f32 constant base, f32 constant scale,
    u32 curve scales/minimums, u32 constants, u32 key types, u32 keys, u32 node flags, u32 tangent keys
Per node nine channels: translation x y z, rotation x y z (radians), scale x y z. A key type of 16 or more
is a constant (entry type-16 of the constants table); 6 is an animated curve. Curves are stored as one
u32 per 4-frame segment: a low-byte anchor and four 6-bit blends towards the next segment's anchor;
value = minimum + scale * blended anchor.

Convention, measured on the LSW2 files (see docs/FORMAT.md): a node's stored rotation Rx Ry Rz (row
vectors) and translation live in a Z-mirrored space, M' = diag(1,1,-1,1) M diag(1,1,-1,1), and the
rotation is applied on top of the bone's bind rotation and the scale first: local = [S B R', t']. The translations then
reproduce the bind translations of the bones a clip holds still, and posed meshes stretch least.
"""
import math
import re
import struct


class AnimationError(ValueError):
    pass


class Clip:
    def __init__(self, data, name=''):
        try:
            self._read(data, name)
        except AnimationError:
            raise
        except (struct.error, IndexError, ValueError, ZeroDivisionError) as e:
            raise AnimationError(f'{name}: damaged animation ({e})') from e

    def _read(self, data, name):
        self.name = name
        if len(data) < 64 or data[1:4] != b'INA':
            raise AnimationError(f'{name}: not an animation block')
        self.tag = data[:4]
        self.nodes, self.frames, group, self.original_frames, self.curve_count = struct.unpack_from('<5H', data, 4)
        if not 1 <= self.nodes <= 255 or not 1 <= self.frames <= 100000:
            raise AnimationError(f'{name}: {self.nodes} nodes, {self.frames} frames')
        cbase, cscale = struct.unpack_from('<ff', data, 28)
        sm, cp, ktp, kp, csf = struct.unpack_from('<5I', data, 36)
        n_types = self.nodes * 9
        for at, size in ((ktp, 2 * n_types), (cp, 0), (sm, 0), (kp, 0)):
            if at > len(data) or at + size > len(data):
                raise AnimationError(f'{name}: a table lies outside the file')
        self.key_types = struct.unpack_from(f'<{n_types}H', data, ktp)
        unknown = sorted({v for v in self.key_types if v < 16 and v != 6})
        if unknown:
            raise AnimationError(f'{name}: unsupported key types {unknown}')
        self.slots = group // 4
        self.curve_slot = []
        for kt in self.key_types:
            if kt == 6:
                self.curve_slot.append(len(self.curve_slot))
        moving = len(self.curve_slot)
        if moving and self.slots < moving:
            raise AnimationError(f'{name}: {moving} curves but {self.slots} key slots')
        if ktp < cp:
            raise AnimationError(f'{name}: constants table out of order')
        self.constants = [cbase + v * cscale for v in struct.unpack_from(f'<{(ktp - cp) // 2}H', data, cp)]
        if any(kt >= 16 and kt - 16 >= len(self.constants) for kt in self.key_types):
            raise AnimationError(f'{name}: a constant index lies past the table')
        if sm + 8 * moving > len(data):
            raise AnimationError(f'{name}: curve table outside the file')
        self.curve_params = [struct.unpack_from('<ff', data, sm + 8 * i) for i in range(moving)]
        if self.slots:
            self.segments = ((csf - kp) // 4) // self.slots if csf > kp else (self.frames + 3) // 4 + 1
            if kp + 4 * self.slots * self.segments > len(data) or self.segments < 1:
                raise AnimationError(f'{name}: keys outside the file')
            self.keys = struct.unpack_from(f'<{self.slots * self.segments}I', data, kp)
        else:
            self.segments, self.keys = 0, ()

    def _curve(self, index, frame):
        scale, low = self.curve_params[index]
        seg = min(frame // 4, self.segments - 1)
        slot = self.curve_slot[index]
        key = self.keys[seg * self.slots + slot]
        a = key & 0xFF
        nxt = self.keys[min(seg + 1, self.segments - 1) * self.slots + slot] & 0xFF
        blend = ((key >> (8 + 6 * (frame % 4))) & 63) / 63.0
        return low + scale * (a + (nxt - a) * blend)

    def pose(self, frame):
        """Per node (tx, ty, tz, rx, ry, rz, sx, sy, sz) at a frame, as stored."""
        frame = max(0, min(frame, self.frames - 1))
        out, curve = [], 0
        for node in range(self.nodes):
            values = []
            for ch in range(9):
                kt = self.key_types[node * 9 + ch]
                if kt >= 16:
                    values.append(self.constants[kt - 16])
                else:
                    values.append(self._curve(curve, frame))
                    curve += 1
            out.append(tuple(values))
        return out

    def local_matrices(self, frame, bones=None):
        """Per node: the model-space local matrix (16 floats, row-major, row vectors) at a frame.

        With `bones` (the skeleton the clip drives), each rotation is applied on top of the bone's bind
        rotation, as the game does; without, the stored rotation alone (used to compare translations)."""
        out = []
        for j, (tx, ty, tz, rx, ry, rz, sx, sy, sz) in enumerate(self.pose(frame)):
            r = _euler_xyz(rx, ry, rz)
            m = [r[0][0], r[0][1], r[0][2], 0.0, r[1][0], r[1][1], r[1][2], 0.0,
                 r[2][0], r[2][1], r[2][2], 0.0, tx, ty, tz, 1.0]
            for k in (2, 6, 8, 9, 14):          # Z mirror: diag(1,1,-1,1) M diag(1,1,-1,1)
                m[k] = -m[k]
            rot = [m[0:3], m[4:7], m[8:11]]
            if bones is not None:
                b = bones[j]['local']
                rot = [[sum(b[i * 4 + k] * rot[k][c] for k in range(3)) for c in range(3)] for i in range(3)]
            scale = (sx, sy, sz)                # the scale is applied first, in the bone's own axes: S B R
            for i in range(3):
                m[i * 4:i * 4 + 3] = [x * scale[i] for x in rot[i]]
            out.append(m)
        return out


def _euler_xyz(rx, ry, rz):
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    x = [[1, 0, 0], [0, cx, sx], [0, -sx, cx]]
    y = [[cy, 0, -sy], [0, 1, 0], [sy, 0, cy]]
    z = [[cz, sz, 0], [-sz, cz, 0], [0, 0, 1]]
    mul = lambda a, b: [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mul(mul(x, y), z)


def ownership(clip, bones, tolerance=1e-3):
    """Share (0..1) of the bones whose translation the clip keeps constant that sit at the skeleton's
    bind translation at frame 0; 0 if the counts differ or the clip moves more than half the bones.

    Matching node and bone counts alone prove nothing. The bind translations are the skeleton's
    proportions, so a clip made for another skeleton type fails here; minifigures that share one
    skeleton legitimately share clips (measured: cross-character passes differ only in name style,
    such as `leftHand` against `leftElbowLength|leftHand`)."""
    if clip.nodes != len(bones):
        return 0.0
    frame0 = clip.local_matrices(0)
    hits = judged = 0
    for j, b in enumerate(bones):
        if any(clip.key_types[j * 9 + k] < 16 for k in range(3)):
            continue                                  # the clip moves this bone's translation
        judged += 1
        t = b['local'][12:15]
        hits += max(abs(frame0[j][12 + k] - t[k]) for k in range(3)) < tolerance
    if judged < len(bones) / 2:
        return 0.0
    return hits / judged


OWNED = 0.9   # the share that counts as proof


def declared_clips(txt):
    """Clip names a character .txt declares (its anim_start blocks), lower case, in order."""
    out = []
    for m in re.finditer(r'^\s*anim_start\s*=\s*"?([^"\s]+)', txt, re.IGNORECASE | re.MULTILINE):
        name = m.group(1).lower()
        if name not in out:
            out.append(name)
    return out


def frame_rates(txt):
    """{clip name (lower case): frames per second} from a character .txt (`fpsec=` inside an
    anim_start ... anim_end block)."""
    rates, current = {}, None
    for line in txt.splitlines():
        line = line.strip()
        m = re.match(r'anim_start\s*=\s*"?([^"\s]+)"?', line, re.IGNORECASE)
        if m:
            current = m.group(1).lower()
            continue
        if line.lower().startswith('anim_end'):
            current = None
            continue
        m = re.match(r'fpsec\s*=\s*([0-9.]+)', line, re.IGNORECASE)
        if m and current:
            try:
                fps = float(m.group(1))
            except ValueError:
                continue
            if 1.0 <= fps <= 240.0:
                rates[current] = fps
    return rates
