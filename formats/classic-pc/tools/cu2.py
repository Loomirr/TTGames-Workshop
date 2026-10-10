"""Reader for the original games' cutscene files (*.cu2: LEGO Batman, LEGO Indiana Jones, LEGO Star Wars: TCS).

Worked out from the files themselves (2026-10-05, GAME_STUDY.md 3x; header, versions, frame rate and cut table
re-measured on all 452 files of the three games on 2026-10-08); no community documentation was found.
"Measured n / m" below means: true in n of the m files (or tables, or blocks) that have the thing.

A .cu2 is a memory image: every pointer is an absolute address, the file's own load address is the u32 at 4.

VERSIONS (u32 at 0): 516 (1 file, TCS), 517 (28 TCS, 2 Batman), 519 (176 TCS, 5 Indy), 520 (133 Batman, 107 Indy).
The header is laid out THE SAME in all four: no offset shifts (measured 452 / 452). What differs is the tag of the
animation blocks ("ANI4" in TCS, "ANI6" in some 517 / 519 files of Batman and Indy, "ANI8" in 520; stored reversed,
"4INA") and which optional fields are filled in. Any other version number is refused (see Cutscene).
    0x00 u32 version          0x04 u32 load address (repeated at 0x28, measured 452 / 452)
    0x08 f32 length in frames (a whole number, measured 452 / 452)
    0x0c ptr names (zero-terminated strings; a name offset elsewhere is 1-based, 0 = none)
    0x10 ptr cameras   0x14 ptr objects   0x18 ptr characters   0x1c ptr effects (NOT decoded)
    0x20 ptr a sixth section (3 TCS files only; begins with six floats like a box; NOT decoded)
    0x40 u8 0, u8 a flag (0 or 1, NOT understood), u16 last frame = length - 1 (measured 452 / 452)
    0x4c u32 an offset inside the file, a multiple of 16 (in TCS it is where the first animation block starts,
         measured 204 / 204; in version 520 it lies before that; NOT understood further)
    0x50 ptr to 0x70 when a table of 16-byte records lies between the header and the names (NOT decoded), else 0
    0x5c f32 a frame rate, OPTIONAL: 30.0 in 198 version-520 files, 37.5 in 2, and 0 in every 516 / 517 / 519 file
         and in 40 version-520 files (see FRAME RATE)
  cameras     u32 count, ptr camera array, ptr animation block, ptr cut table,
              u8 the camera in force when the cutscene starts (an index, 255 = none),
              10 x u8 camera id -> index in the array (255 = no such id; measured 433 / 433), u8 ?, ptr ?
              camera (0x50 bytes): 4x4 matrix (row vectors, the position in row 3), u8 animated, u8 id, u8 node in
              the animation block, u8 ?, two numbers (NOT understood), f32 field of view in radians (axis NOT confirmed)
              cut table: u16 count, u16 length of the cutscene in frames (measured 420 / 420), ptr frames (f32
              each), ptr camera index (u8 each), f32 the first cut's frame again (measured 420 / 420)
  objects     ptr array, u32 count. object (0x5c bytes): matrix, u32 name, 2 x u32, ptr animation block, ptr
              visibility cut table, ...   (set pieces of the level scene that the cutscene moves)
  characters  ptr array, u32 count. character (0x64 bytes): matrix, u32 name, ptr root animation block (1 node: where
              the character is), ptr skeleton animation block, ptr a third track (NOT decoded: expressions / events?)
  animation block: the same layout as a character .an3 (tools/an3.py) with these differences: the tag reads "ANI4",
              "ANI6" or "ANI8"; the u16 at 12 is the channels per node (9 for a skeleton, a camera or an object; 6, 7,
              9, 10, 11 or 12 for a character's root); the u16 at 14 is the frame of the cutscene the block STARTS on;
              curves are key type 7:
              two u32 per 4-frame segment = a 16-bit anchor and four 12-bit blends toward the next segment's anchor
              (word A: low 16 anchor, bits 16-27 blend 0, bits 28-31 the low 4 bits of blend 3;
               word B: bits 0-11 blend 1, 12-15 the middle 4 bits of blend 3, 16-27 blend 2, 28-31 its top 4 bits).
              Key types 8 and 10 are one byte per frame (one u32 per segment). Type 10 is only ever the 12th channel
              of a 12-channel root block (measured 1761 / 1761); what the byte means is NOT known for either.
              Checked on the Gotham Streets intro: camera 1 starts exactly on its stored matrix and moves evenly.
              In version-520 files the longest block usually ends 2 frames after the stated length (178 of 240).

FRAME RATE. The file alone does not always say. What was measured:
  - the script beside the cutscene (<name>.txt for <name>_pc.cu2 or <NAME>.CU2) may hold a line "fpsec <n>"
    (123 of the 443 scripts: 30, 24, 25, 20, 60). It wins over 0x5c: 13 cutscenes with 30.0 in the header and
    "fpsec 24" in the script have 14.9 to 23.8 frames per second of their own sound file (never more than 24).
  - with no fpsec line and 0 at 0x5c the games play at 30: of 66 such TCS cutscenes with a sound file of their own,
    41 have 29.0 to 30.1 frames per second of sound (median 29.98); Batman and Indy version-520 files with 0 at
    0x5c: medians 29.2 and 28.7 (28 files). So a 0 at 0x5c means "not set", not a different kind of file.
  - 37.5 at 0x5c (2 Batman files) is NOT understood: one has "fpsec 24", the other measures 30.9.
  Cutscene.fps is therefore: the script's fpsec, else the header's value, else 30.0 with fps_source "default"
  (an assumption backed by the sound lengths, not read from anything).

CUTS. A cut list is sorted by frame (measured 420 / 420) and no cut lies at or after the length (420 / 420).
  Frames BELOW 0 are real (26 files): the camera track starts before the part that was kept, and the camera of the
  last cut at or before frame 1 is the one in force at the start; the camera section stores exactly that index in
  its own byte (measured 420 / 420; where the first cut comes later than frame 1 the byte is the first cut's camera).
  Camera index 255 is "no camera" (4 files; what the game then shows is NOT known), never a bad index: every index
  in every cut list is below the camera count or 255 (420 / 420). A few TCS cut frames are not whole numbers
  (1.25, 469.995): Cutscene.cuts rounds them, Cutscene.cut_times keeps them.

    python tools/cu2.py info <file.cu2>          one cutscene: cuts, cameras, characters, objects
    python tools/cu2.py list <folder>            every cutscene under a folder, one line each
"""
import math
import os
import re
import struct
import sys
try:
    from .reader_bounds import read_file, span, finite
except ImportError:
    from reader_bounds import read_file, span, finite

# version: how many of the 452 files of the three games the layout was checked on
VERSIONS = {516: 1, 517: 30, 519: 181, 520: 240}
BLOCK_TAGS = (b"4INA", b"6INA", b"8INA")
NO_CAMERA = 255
DEFAULT_FPS = 30.0          # see FRAME RATE above: measured from sound lengths, not stored anywhere
FRAME_KEYS = (8, 10)        # key types stored as one byte per frame


class UnsupportedVersion(ValueError):
    """The file's version number is not one of those the layout was checked on."""


class Block:
    """One animation block inside a cutscene (see the top of this file)."""

    def __init__(self, d, off):
        if off < 0 or off + 60 > len(d):
            raise ValueError(f"animation block at {off:#x}: outside the file")
        self.tag = bytes(d[off:off + 4])
        if self.tag not in BLOCK_TAGS:
            raise ValueError(f"animation block at {off:#x}: tag {self.tag!r} is not one of ANI4 / ANI6 / ANI8")
        try:
            self._read(d, off)
        except struct.error as ex:
            raise ValueError(f"animation block at {off:#x}: runs past the end of the file ({ex})") from None

    def _read(self, d, off):
        self.nodes, self.frames, group, _orig, self.channels, self.start = struct.unpack_from("<6H", d, off + 4)
        if not 0 < self.nodes <= 4096 or not self.frames or self.channels not in (6,7,9,10,11,12) or group % 4:
            raise ValueError('Unverified animation dimensions or key stride')
        _fi, cbase, cscale, sm, cp, ktp, kp, csf, _tk = struct.unpack_from("<IffIIIIII", d, off + 24)
        if not 60 <= cp <= ktp or (ktp-cp) % 2:
            raise ValueError('Invalid animation table order/alignment')
        span(d,off+cp,ktp-cp,'constants')
        span(d,off+ktp,self.nodes*self.channels*2,'key types')
        # Original constant-only blocks have group=0 and a null keys pointer.
        # Only moving blocks own a key range; no synthetic fallback groups.
        if group:
            if not ktp <= kp <= csf or (csf-kp) % 4:
                raise ValueError('Invalid animation key range/alignment')
            span(d,off+kp,csf-kp,'keys')
        elif kp:
            raise ValueError('Constant-only block has an unverified non-null keys pointer')
        finite((cbase,cscale),'constant quantization')
        self.key_types = struct.unpack_from(f"<{self.nodes * self.channels}H", d, off + ktp)
        bad = sorted({k for k in self.key_types if k < 16 and k not in (6, 7) + FRAME_KEYS})
        if bad:
            raise ValueError(f"animation block at {off:#x}: unhandled key types {bad}")
        self.constants = [cbase + v * cscale for v in struct.unpack_from(f"<{max(0, ktp - cp) // 2}H", d, off + cp)]
        if any(k >= 16 and k-16 >= len(self.constants) for k in self.key_types):
            raise ValueError('Animation constant index outside table')
        finite(self.constants,'constants')
        self.slots = group // 4
        self.curve_slot, slot, self.flag_slot = [], 0, {}
        for i, k in enumerate(self.key_types):
            if k in (6, 7):
                self.curve_slot.append((slot, k))
                slot += 2 if k == 7 else 1
            elif k in FRAME_KEYS:           # one byte per frame, no scale (seen as 0 / 1 / 2; meaning NOT known)
                self.flag_slot[i] = slot
                slot += 1
        if slot != self.slots:
            raise ValueError(f"animation block at {off:#x}: its key types need {slot} key words per segment, the block has {self.slots}")
        span(d,off+sm,len(self.curve_slot)*8,'curve parameters')
        self.params = [struct.unpack_from("<ff", d, off + sm + 8 * i) for i in range(len(self.curve_slot))]
        finite((v for row in self.params for v in row),'curve parameters')
        self.segments = ((csf - kp) // 4) // self.slots if self.slots else 0
        if self.slots and ((csf-kp) % (4*self.slots) or self.segments < (self.frames+3)//4):
            raise ValueError('Animation key groups do not cover the declared timeline')
        self.keys = struct.unpack_from(f"<{self.slots * self.segments}I", d, off + kp) if self.slots else ()

    def curve(self, index, frame):
        scale, low = self.params[index]
        slot, kind = self.curve_slot[index]
        seg = min(frame // 4, self.segments - 1)
        nxt = min(seg + 1, self.segments - 1)
        a = self.keys[seg * self.slots + slot]
        if kind == 6:
            a0, a1 = a & 0xFF, self.keys[nxt * self.slots + slot] & 0xFF
            blend = ((a >> (8 + 6 * (frame % 4))) & 63) / 63.0
        else:
            b = self.keys[seg * self.slots + slot + 1]
            a0, a1 = a & 0xFFFF, self.keys[nxt * self.slots + slot] & 0xFFFF
            blend = ((a >> 16) & 0xFFF, b & 0xFFF, (b >> 16) & 0xFFF,
                     ((b >> 28) << 8) | (((b >> 12) & 0xF) << 4) | (a >> 28))[frame % 4] / 4095.0
        return low + scale * (a0 + (a1 - a0) * blend)

    def pose(self, frame):
        """Per node (tx, ty, tz, rx, ry, rz, sx, sy, sz) at a frame counted from the block's own start. A character's
        root block has 6, 7, 10, 11 or 12 channels instead (9 once) (the first six are position and rotation; the 7th and the
        12th are per-frame bytes, meaning NOT confirmed; channels 8 to 11 NOT understood)."""
        if not isinstance(frame,int):raise ValueError('Use an integer source frame')
        frame = max(0, min(frame, self.frames - 1))
        out, c = [], 0
        for n in range(self.nodes):
            v = []
            for ch in range(self.channels):
                k = self.key_types[n * self.channels + ch]
                if k >= 16:
                    v.append(self.constants[k - 16])
                elif k in FRAME_KEYS:
                    word = self.keys[min(frame // 4, self.segments - 1) * self.slots + self.flag_slot[n * self.channels + ch]]
                    v.append((word >> (8 * (frame % 4))) & 0xFF)
                else:
                    v.append(self.curve(c, frame))
                    c += 1
            out.append(tuple(v))
        return out


def script_path(path):
    """The game script that belongs to a cutscene file (<name>.txt beside <name>_pc.cu2 or <NAME>.CU2), or None."""
    folder, base = os.path.split(os.path.abspath(path))
    want = re.sub(r"(?i)(_pc)?\.cu2$", "", base).lower() + ".txt"
    try:
        for f in os.listdir(folder):
            if f.lower() == want:
                return os.path.join(folder, f)
    except OSError:
        pass
    return None


def script_fps(txt):
    """The value of the first "fpsec <n>" line of a cutscene script that is not commented out, or None."""
    try:
        for line in read_file(txt).decode('latin1').splitlines():
                m = re.match(r"\s*fpsec\s+([0-9]+(?:\.[0-9]+)?)", re.split(r"//|;", line)[0], re.I)
                if m and 0 < float(m.group(1)) <= 240:
                    return float(m.group(1))
    except OSError:
        pass
    return None


class Cutscene:
    """One cutscene file.

    version, frames (length), fps (always above 0), fps_source ("script", "header" or "default"), fps_header (the raw
    f32 at 0x5c, 0 when not set), fps_script (the script's fpsec or None), fps_known (False when fps is only the
    assumed 30), seconds, cameras, cuts [(frame, camera index)], cut_times (the frames as stored), start_camera,
    shots, objects, characters, notes (plain sentences about anything in this file that is unusual or not understood).

    A version number outside VERSIONS always raises UnsupportedVersion.
    script=False leaves the script beside the file unread (fps then comes from the
    header or the default)."""

    def __init__(self, path, script=True):
        self.path = path
        self.d = d = read_file(path)
        self.notes = []
        if len(d) < 0x70:
            raise ValueError(f"{path}: {len(d)} bytes is too short for a cutscene file (the header alone is 0x70)")
        self.version, self.base = struct.unpack_from("<II", d, 0)
        if self.version not in VERSIONS:
            raise UnsupportedVersion(f"{path}: version {self.version} is not one this reader was checked on "
                                     f"({', '.join(map(str, sorted(VERSIONS)))}); not read")
        elif self.version == 516:
            self.notes.append("version 516 was checked on one file only (no characters, no animation, no cut list in it)")
        if self.u32(0x28) != self.base:
            raise ValueError('CU2 load-address copies disagree')
        try:
            self._read(d)
        except (struct.error, IndexError, ValueError) as ex:
            raise ValueError(f"{path}: version {self.version}, but the contents do not follow the known layout ({ex})") from None
        self._rate(script)

    def _read(self, d):
        length = struct.unpack_from("<f", d, 8)[0]
        if not (math.isfinite(length) and 0 <= length < 1e6):
            raise ValueError(f"length {length!r} at 0x08 is not a frame count")
        self.frames = int(round(length))
        if length != self.frames:
            self.notes.append(f"the length at 0x08 is {length!r}, not a whole number of frames")
        if struct.unpack_from("<H", d, 0x42)[0] != max(self.frames - 1, 0):
            self.notes.append(f"the last frame at 0x42 ({struct.unpack_from('<H', d, 0x42)[0]}) is not the length - 1")
        self.flag = d[0x41]
        self.names_at, cam_at, obj_at, chr_at, self.fx_at, self.sixth_at = (self.ptr(o) for o in (0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20))
        for o, what in ((0x0C, "names"), (0x10, "cameras"), (0x14, "objects"), (0x18, "characters"), (0x1C, "effects"), (0x20, "sixth section")):
            if self.u32(o) and not self.ptr(o):
                self.notes.append(f"the {what} pointer at {o:#x} points outside the file (cut short?): {what} not read")
        self.cameras, self.cuts, self.cut_times, self.camera_block_at, self.start_camera = [], [], [], 0, None
        if cam_at:
            count = self.count(cam_at, "camera")
            arr, blk, cut = self.ptr(cam_at + 4), self.ptr(cam_at + 8), self.ptr(cam_at + 12)
            for i in range(count if arr else 0):
                o = arr + i * 0x50
                animated, ident, node, other = d[o + 0x40:o + 0x44]
                self.cameras.append({"matrix": struct.unpack_from("<16f", d, o), "animated": animated, "id": ident, "node": node, "byte3": other,
                                     "raw": d[o + 0x44:o + 0x4C].hex(), "fov": struct.unpack_from("<f", d, o + 0x4C)[0]})
            self.camera_block_at = blk
            self.start_camera = d[cam_at + 16]
            if cut:
                self._cuts(d, cut)
        self.objects = []
        if obj_at:
            arr, count = self.ptr(obj_at), self.count(obj_at + 4, "object")
            for i in range(count if arr else 0):
                o = arr + i * 0x5C
                self.objects.append({"name": self.name(self.u32(o + 0x40)), "matrix": struct.unpack_from("<16f", d, o), "anim_at": self.ptr(o + 0x4C)})
        self.characters = []
        if chr_at:
            arr, count = self.ptr(chr_at), self.count(chr_at + 4, "character")
            for i in range(count if arr else 0):
                o = arr + i * 0x64
                self.characters.append({"name": self.name(self.u32(o + 0x40)), "matrix": struct.unpack_from("<16f", d, o),
                                        "root_at": self.ptr(o + 0x44), "skeleton_at": self.ptr(o + 0x48), "third_at": self.ptr(o + 0x4C)})
        if self.sixth_at:
            self.notes.append(f"a sixth section at {self.sixth_at:#x} (pointer at 0x20) is not decoded")

    def _cuts(self, d, cut):
        n, length = struct.unpack_from("<HH", d, cut)
        frames_at, cams_at = self.ptr(cut + 4), self.ptr(cut + 8)
        if n and not (frames_at and cams_at):
            self.notes.append(f"the cut table at {cut:#x} counts {n} cuts but points nowhere: cuts not read")
            return
        self.cut_times = list(struct.unpack_from(f"<{n}f", d, frames_at)) if n else []
        cams = d[cams_at:cams_at + n]
        if len(cams) != n or not all(math.isfinite(t) and abs(t) < 1e6 for t in self.cut_times):
            self.cut_times = []
            self.notes.append(f"the cut table at {cut:#x} does not hold {n} sensible cuts: cuts not read")
            return
        self.cuts = list(zip((int(round(t)) for t in self.cut_times), cams))
        if length != self.frames:
            self.notes.append(f"the cut table says the cutscene is {length} frames long, the header {self.frames}")
        if any(a >= b for a, b in zip(self.cut_times, self.cut_times[1:])):
            self.notes.append("the cuts are not in order of frame")
        late = [f for f, _c in self.cuts if f >= self.frames]
        if late:
            self.notes.append(f"cuts at or after the length ({self.frames}): frames {late}")
        early = [f for f, _c in self.cuts if f < 0]
        if early:
            self.notes.append(f"{len(early)} cut(s) before frame 0 (from {early[0]}): the camera track starts before the kept part; "
                              "only the last of them matters, it gives the camera at the start")
        wrong = sorted({c for _f, c in self.cuts if c >= len(self.cameras) and c != NO_CAMERA})
        if wrong:
            self.notes.append(f"cuts name cameras that do not exist: {wrong} (the file has {len(self.cameras)})")
        if any(c == NO_CAMERA for _f, c in self.cuts):
            self.notes.append("camera index 255 in the cut list means no cutscene camera for that stretch (what is shown then is not known)")
        if self.cuts and self.start_camera != self._first_camera():
            self.notes.append(f"the start-camera byte ({self.start_camera}) is not the camera the cut list gives at the start ({self._first_camera()})")

    def _first_camera(self):
        """The camera index the cut list gives at the start: the last cut at or before frame 1 (1.25 in a few TCS
        files), else the first cut's."""
        before = [c for t, c in zip(self.cut_times, (c for _f, c in self.cuts)) if t < 2]
        return before[-1] if before else self.cuts[0][1]

    def _rate(self, script):
        fps = struct.unpack_from("<f", self.d, 0x5C)[0]
        self.fps_header = fps if math.isfinite(fps) and 0 < fps <= 240 else 0.0
        if fps != self.fps_header:
            self.notes.append(f"the f32 at 0x5c ({fps!r}) is not a frame rate: ignored")
        self.script = script_path(self.path) if script else None
        self.fps_script = script_fps(self.script) if self.script else None
        if self.fps_script:
            self.fps, self.fps_source = self.fps_script, "script"
            if self.fps_header and self.fps_header != self.fps_script:
                self.notes.append(f"the script's fpsec {self.fps_script:g} is used, not the header's {self.fps_header:g} (sound lengths show the script wins)")
        elif self.fps_header:
            self.fps, self.fps_source = self.fps_header, "header"
        else:
            self.fps, self.fps_source = DEFAULT_FPS, "default"
            self.notes.append(f"no frame rate in the file (0 at 0x5c) and no fpsec line in "
                              f"{'its script' if self.script else 'a script (none found beside it)' if script else 'a script (not looked for)'}: "
                              f"{DEFAULT_FPS:g} is ASSUMED (the games' rate where nothing says otherwise, from sound lengths)")
        if self.fps_header not in (0.0, 30.0):
            self.notes.append(f"the header's frame rate {self.fps_header:g} is unusual (2 of 452 files) and not confirmed by the sound length")

    @property
    def fps_known(self):
        return self.fps_source != "default"

    @property
    def seconds(self):
        return self.frames / self.fps

    @property
    def shots(self):
        """The cut list as it plays: [(first frame, frame after the last, camera index or None)], inside 0..frames.
        Cuts before the start are folded into the first shot; None stands for camera index 255 (no camera)."""
        if not self.cuts:
            return []
        marks = [(0, self._first_camera())] + [(f, c) for (f, c), t in zip(self.cuts, self.cut_times) if t >= 2 and 0 < f < self.frames]
        if len(marks) > 1 and marks[1][1] == marks[0][1] and not any(t < 2 for t in self.cut_times):
            marks.pop(1)                     # the first cut comes late and its camera already runs from the start
        out = []
        for (f, c), nxt in zip(marks, marks[1:] + [(self.frames, None)]):
            if nxt[0] > f:
                out.append((f, nxt[0], None if c == NO_CAMERA else c))
        return out

    def camera_at(self, frame):
        """The camera index in force at a frame of the cutscene, or None where the cut list says no camera (or the
        file has no cut list)."""
        for a, b, c in self.shots:
            if a <= frame < b:
                return c
        return self.shots[-1][2] if self.shots and frame >= self.frames else None

    def u32(self, o):
        return struct.unpack_from("<I", self.d, o)[0]

    def ptr(self, o):
        v = self.u32(o)
        return v - self.base if self.base < v < self.base + len(self.d) else 0

    def count(self, o, what):
        n = self.u32(o)
        if n > 4096:
            raise ValueError(f"{n} {what}s at {o:#x} is not a believable count")
        return n

    def name(self, off):
        if not off or not self.names_at:
            return ""
        s = self.names_at + off - 1
        span(self.d,s,1,'name')
        end = self.d.find(b"\0", s)
        if end < 0:raise ValueError('Unterminated CU2 name')
        return self.d[s:end].decode("latin1")

    def block(self, at):
        return Block(self.d, at) if at else None

    def rate_text(self):
        how = {"script": "from the script's fpsec", "header": "from the header", "default": "ASSUMED, nothing states it"}[self.fps_source]
        return f"{self.fps:g} fps ({how})"


def info(path):
    try:
        c = Cutscene(path)
    except (ValueError, OSError) as ex:
        print(f"NOT READ: {ex}")
        return False
    print(f"{path}: version {c.version}, {c.frames} frames at {c.rate_text()} = {c.seconds:.1f} s")
    print(" cuts (frame, camera):", c.cuts)
    if c.cuts:
        print(" shots as played (from, to, camera):", [(a, b, "none" if cam is None else cam) for a, b, cam in c.shots])
    for i, cam in enumerate(c.cameras):
        m = cam["matrix"]
        print(f" camera {i}: at ({m[12]:.2f}, {m[13]:.2f}, {m[14]:.2f}) fov {math.degrees(cam['fov']):.1f} deg animated {cam['animated']} "
              f"id {cam['id']} node {cam['node']} byte3 {cam['byte3']} raw {cam['raw']}")
    if c.camera_block_at:
        try:
            b = c.block(c.camera_block_at)
            print(f" camera animation: {b.nodes} nodes, {b.frames} frames from frame {b.start}")
        except ValueError as ex:
            print(f" camera animation: NOT READ: {ex}")
    for ch in c.characters:
        m, line = ch["matrix"], ""
        for key in ("root_at", "skeleton_at"):
            if ch[key]:
                try:
                    b = c.block(ch[key])
                    line += f" | {key[:-3]}: {b.nodes} nodes, frames {b.start}..{b.start + b.frames}"
                except ValueError as ex:
                    line += f" | {key[:-3]}: NOT READ: {ex}"
        print(f" character {ch['name']}: at ({m[12]:.2f}, {m[13]:.2f}, {m[14]:.2f}){line}")
    print(" objects:", ", ".join(o["name"] for o in c.objects))
    for note in c.notes:
        print(" note:", note)
    return True


def listing(folder):
    """One line per cutscene. After the seconds: the frame rate and where it comes from (s = the script's fpsec,
    h = the header, ? = assumed 30). A trailing ! means the file has notes: see them with info."""
    found = 0
    for root, _dirs, files in os.walk(folder):
        for f in sorted(files):
            if f.lower().endswith(".cu2"):
                found += 1
                p = os.path.join(root, f)
                rel = os.path.relpath(p, folder)
                try:
                    c = Cutscene(p)
                    mark = {"script": "s", "header": "h", "default": "?"}[c.fps_source]
                    odd = [n for n in c.notes if "ASSUMED" not in n]
                    print(f"{rel:62s} v{c.version} {c.frames:5d} fr {c.seconds:6.1f} s @{c.fps:g}{mark}  {len(c.cuts):3d} cuts  "
                          + ", ".join(ch["name"] for ch in c.characters) + ("  !" if odd else ""))
                except Exception as ex:             # one bad file must never stop the list
                    print(f"{rel:62s} NOT READ: {ex}"[:240])
    if not found:
        print(f"no .cu2 files under {folder}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "info":
        sys.exit(0 if info(sys.argv[2]) else 1)
    elif len(sys.argv) >= 3 and sys.argv[1] == "list":
        listing(sys.argv[2])
    else:
        print(__doc__)
