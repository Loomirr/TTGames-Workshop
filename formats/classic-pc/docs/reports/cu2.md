# cu2.py: header per version, frame rate, cuts (2026-10-08)

Only file edited: `tools\cu2.py` (uncommitted; the `release` folder does not
show in `git status`). Scratch scripts and outputs: `...\scratchpad\agent_cu2\`. Nothing was committed, pushed or
posted; no window, game or editor was started. The installs were only read (cutscene `.OGG` lengths, see 2).

"Measured n / m" = true in n of the m files (or tables, or blocks) that have the thing. All 452 files were used
unless a smaller m is given. "Guess" is marked as such.

## 1. The header, per version

Files: TCS 205 (516: 1, 517: 28, 519: 176), Indy 112 (519: 5, 520: 107), Batman 135 (517: 2, 520: 133).

**The header does not shift between versions** (measured 452 / 452: every word 0x00..0x6c is of the same kind,
pointer / zero / value, at the same offset in all four versions; `survey2.py`).

| offset | what | evidence |
|---|---|---|
| 0x00 | u32 version | 516 / 517 / 519 / 520 |
| 0x04 | u32 load address; repeated at 0x28 | 452 / 452 |
| 0x08 | f32 length in frames, always a whole number | 452 / 452 |
| 0x0c..0x1c | pointers: names, cameras, objects, characters, effects | same offsets in every version |
| 0x20 | pointer to a sixth section (starts with six floats like a box) | only 3 TCS files (the 516 file, two 519); not decoded |
| 0x40 | u8 0, u8 a flag (0 or 1), u16 last frame = length - 1 | u16: 452 / 452; flag not understood (0 in all 516 / 517, mixed in 519 / 520) |
| 0x4c | u32 offset inside the file, multiple of 16 | TCS: equals the start of the first animation block 204 / 204; in 520 it lies before it (235 of 240); not understood further |
| 0x50 | pointer to 0x70 when a table of 16-byte records sits before the names, else 0 | table not decoded (all zero in TCS, `00 ff 00 00 ...` in 520) |
| 0x5c | f32, an optional frame rate | 30.0 in 198 version-520 files, 37.5 in 2 (Batman), 0 in all 211 files of 516 / 517 / 519 and in 40 version-520 files |

So the length was never the problem: it is at 0x08 in every version, and the per-character animation blocks agree
(longest block ends exactly at the length in 182 of 204 TCS files with blocks; in version 520 it usually ends 2
frames later, 178 of 240; shorter in 73 files where no track runs to the end).

What really differs by version is the animation block tag: `ANI4` in all TCS files, `ANI6` in Batman's two 517
files and part of Indy's 519, `ANI8` in 520. The block layout the reader uses is the same for all three (all 19,619
blocks decode; decoded curves of ANI4 are as smooth as ANI8's, sample of 10,083 curves, `smooth.py`: a weak check).

## 2. Frame rate: why 0x5c is 0, and where the rate really is

- 0x5c is simply **not filled in** by the older exporter (every 516 / 517 / 519 file) and by 40 version-520 files.
  It is not a different kind of file: those 40 have the same header, flags and tables as the others. (Why those 40
  were written without it: not known. Guess: exported with an older tool build.)
- The rate is in the **script beside the cutscene** (`<name>.txt` for `<name>_pc.cu2` / `<NAME>.CU2`): a line
  `fpsec <n>`. 443 of 452 cutscenes have a script; 123 have an `fpsec` line (TCS 100: 30 x 91, 24 x 6, 25, 20, 60;
  Indy 13; Batman 10, all 24 except three Indy 30s). The games' own `main_intro_a.cfg` comment calls it
  "cutrate - optional playback rate of file - in fps".
- **The script wins over the header** (measured against each cutscene's own sound file, frames / seconds of OGG,
  only sounds used by exactly one unchained script, `audio.py`): 13 cutscenes with 30.0 at 0x5c and `fpsec 24`
  give 14.9 to 23.8, never above 24.
- **With no `fpsec` and 0 at 0x5c the rate is 30** (measured indirectly): 66 such TCS cutscenes: 41 lie between
  29.0 and 30.1 frames per second of sound, median 29.98; Batman / Indy 520 files with 0: medians 29.2 / 28.7
  (28 files). Sound files are usually a little longer than the picture, so values just under the rate are expected.
- **37.5** (2 Batman files, `waynevillain_outro`, `nastysewers_outro`): not understood. One has `fpsec 24` and
  measures 23.4; the other has none and measures 30.9, which fits 30 better than 37.5. 37.5 = 30 x 30 / 24. Guess: a
  left-over of a 24 -> 30 conversion. The reader still reports 37.5 for the one without a script line and flags it.

## 3. Cuts and camera indices: explained, not errors

- Cut table header is `u16 count, u16 length of the cutscene, ptr frames, ptr camera indices, f32 first cut frame`
  (both new fields measured 420 / 420).
- **Every out-of-range cut frame is NEGATIVE** (26 files: 6 TCS, 9 Indy, 11 Batman); none lies at or after the
  length (420 / 420); lists are strictly ascending (420 / 420). The camera track starts before the part of the
  timeline that was kept. The last cut at or before frame 1 gives the camera at the start.
- Proof: the camera section has a byte (section + 16) holding the **starting camera index**, and it equals the
  camera of the last cut at or before frame 1 (or of the first cut when that comes later) in 420 / 420.
  The ten bytes after it are a camera id -> index table (433 / 433 camera sections).
- **Bad camera indices are all 255 = "no camera"** (4 files: 3 Indy, 1 TCS). Every index in every cut list is
  below the camera count or 255 (420 / 420). What the game shows during a 255 stretch is not known (guess: the
  gameplay camera).
- 7 TCS files hold non-whole cut frames (1.25, 469.995): `cuts` rounds, new `cut_times` keeps them.

## 4. What changed in cu2.py

- `Cutscene(path, strict=True, script=True)`: versions 516 / 517 / 519 / 520 are read (table `VERSIONS` with the
  file counts); any other raises `UnsupportedVersion` (a `ValueError`) with a plain message; `strict=False` reads
  it with the 520 layout and says UNVERIFIED in `notes`. Too-short, damaged or impossible contents raise
  `ValueError` with the file name, never `struct.error` / `IndexError`.
- `fps` is always above 0: the script's `fpsec`, else the header, else 30.0. New: `fps_source` (`script` /
  `header` / `default`), `fps_known`, `fps_header`, `fps_script`, `script`, `seconds`.
  Note for callers: for 16 files (9 Batman, 7 Indy) `fps` is now 24 where it used to be 30 (15) or 37.5 (1).
- New: `notes` (sentences about anything unusual), `cut_times`, `start_camera`, `shots` (the cut list as played,
  inside 0..length, 255 -> None), `camera_at(frame)`, `NO_CAMERA`, `sixth_at`, `flag`.
- `cuts` is unchanged (raw frames, may be negative; raw indices, may be 255) so existing callers see what they saw.
- `Block`: key type 10 is now read (one byte per frame, like type 8; it is only ever the 12th channel of a
  12-channel root block, exactly one key word per segment, 1761 / 1761). Its MEANING is not known. Also: tag check
  (`Block.tag`), slot-count check, clear `ValueError`s. `nodes`, `frames`, `start`, `channels`, `pose()` as before.
- `info` and `list` never divide by zero and never stop on a bad file; `info` prints `NOT READ: ...` and exits 1;
  `list` shows version, frames, seconds, rate with its source (`s` script, `h` header, `?` assumed) and `!` for
  files with notes. The docstring holds the layout with the measured counts.
- Kept working and checked on all files: `Cutscene(path)`, `.characters`, `.cameras`, `.cuts`, `.frames`, `.fps`,
  `.block(at)`, `Block.pose(frame)`, `Block.start`, `Block.frames`, `Block.nodes`.

## 5. Before / after, all 452 files (`truth.py` = old reader, `verify.py` = new; both run on every file)

| | TCS (205) | Indy (112) | Batman (135) |
|---|---|---|---|
| `info` succeeds, before | 0 | 89 | 111 |
| `info` succeeds, after | 205 | 112 | 135 |
| `list` lines that fail, before -> after | 205 -> 0 | 23 -> 0 | 24 -> 0 |
| fps known, before (non-zero header) | 0 | 89 | 111 |
| fps known, after (script or header) | 100 | 92 | 112 |
| fps assumed 30 and said so, after | 105 | 20 | 23 |
| files with a cut list | 181 | 108 | 131 |
| raw cuts all inside 0..length (same before and after) | 175 | 99 | 120 |
| cuts inside, or explained by the start-camera byte, after | 181 | 108 | 131 |
| `shots` cover 0..length without gaps, after | 181 | 108 | 131 |
| camera indices all below the count (same before and after) | 180 | 105 | 131 |
| camera indices valid counting 255 = none, after | 181 | 108 | 131 |
| character root blocks decode, before | 1073 / 1943 | 782 / 1414 | 871 / 1130 |
| character root blocks decode, after | 1943 / 1943 | 1414 / 1414 | 1130 / 1130 |
| character skeleton blocks decode (before = after) | 1944 / 1944 | 1438 / 1438 | 1362 / 1362 |
| camera blocks / object blocks decode (before = after) | 185 / 5127 | 103 / 2049 | 130 / 2794 |

A correction to the brief: "the per-character animation blocks already decode in 100% of files" was true only for
skeleton blocks. 1761 root blocks (39%) raised "unhandled key types [10]" in the old reader.

Also run: eight test files made in the scratch folder (six bad: unknown version twice, empty, 40 bytes, garbage,
impossible count; two readable): each bad one gives a one-line `NOT READ` message from `info` and `list`, no traceback.

## 6. Still not understood

- Frame rate when neither the script nor the header gives one: 30 is an assumption backed by sound lengths, not a
  stored value; the proof would be in the exe (not looked at). The 9 cutscenes without a script, and any chained
  through `next_cut_scene`, were not measured individually.
- 37.5 at 0x5c (2 files); why 40 version-520 files have 0 there; the flag at 0x41; the exact meaning of 0x4c; the
  record table at 0x70; the sixth section (0x20); the effects section; the characters' third track.
- What is shown during a camera-255 stretch, and during the frames before a late first cut (the start byte says
  the first cut's camera; whether the game also shows it then was not confirmed).
- Whether the timeline is 0- or 1-based: most cut lists begin at frame 1 and the start byte follows "at or before
  frame 1", and version-520 blocks run 2 frames past the length. `shots` starts the first shot at 0.
- Key types 8 and 10: storage is read, meaning unknown. Root-block channels 8 to 11 not understood.
- ANI4 / ANI6 curve decoding is only checked by smoothness and by clean slot arithmetic, not against a picture.
- Version 516 rests on one 976-byte file with no characters, animation or cut list.
- A file cut short after its section tables reads as "fewer things" without a note (inner pointers that fall
  outside the file are treated as absent, as before).
- `anim_export.py` (not mine to edit) passes a fixed 30 for cutscene performances; 16 cutscenes play at 24.
