# File formats

What is worked out, per format, and what is still open. Each reader's first lines carry the exact layout;
this page is the overview. "Measured" means read from the games' own files.

**Corrections since this page was first written** (details and evidence in `reports/`):

- **`.DAT`:** index version -4 (LEGO Batman 2) is as -2 except that the offset is `off_hi << 8` alone, with no
  low byte from the flags word.
- **NU20:** each model's mesh list was being read one entry off, which paired most meshes with the wrong
  material. Fixed; per-mesh material pairing in character files is no longer an open item. Packed blend
  indices are 4 bytes, and flag 0x80 is a 4-byte slot.
- **AN3:** a fourth tag exists, `5INA` (one TCS file), in an unrelocated layout. All three games map actions
  to files the same way and need the same Z mirror.
- **CU2:** the value at 0x5C is an optional frame rate, zero in every TCS cutscene and some others. The rate
  is `fpsec` in the script beside the cutscene, else the header, else an assumed 30. The header does not shift
  between versions 516 and 520. Negative cut frames mean the camera track starts before the kept part;
  camera 255 means no camera. Key type 10 (one byte per frame, meaning unknown) occurs in root tracks.
- **GIZ:** files end with a 4-byte zero marker. Pickup table version 4 has a 12-byte header; versions 5 to 7
  have 20 bytes. The 23-byte record is the same in versions 4, 5 and 7.

## The three games side by side

| | LEGO Batman (2008) | LEGO Indiana Jones 1 (2008) | LEGO Star Wars: TCS (2007) |
|---|---|---|---|
| Archives | `GAME.DAT` and level archives, index version -2 | `GAME.DAT` + `RAIDERS`, `TEMPLE`, `CRUSADE`, index version -2 | `GAME.DAT` + `EPISODE_*.DAT`, index version -3 |
| Compression | LZ2K | LZ2K | LZ2K |
| Extraction result | everything reads | 9,465 files, 4.30 GB, 0 failures | 12,174 files from `GAME.DAT`, 44 to 46 per episode archive |
| Exe | plain 32-bit | wrapped by Steam (encrypted code section) | not looked at |
| Formats | `.gsc` `.ghg` `.an3` `.cu2` `.giz` `.git` `.scp` `.txt` | identical to Batman | same family, older engine version |

Counts in TCS: `.an3` 2,911, `.ghg` 688, `.gsc` 504, `.scp` 859, `.giz` 251, `.git` 166, `.wav` 1,147, plus
`.ptl`/`.par` particles and `.ai2` paths. Its level folders are laid out like the later games'
(`LEVELS\EPISODE_I\NEGOTIATIONS\NEGOTIATIONS_A\...` with an `AI` folder).

## `.DAT` archives (`ttdat.py`)

    u32 a, u32 info_size            a is negative-encoded: info_off = ((~a) << 8) + 0x100
    @info_off:
      i32 version, i32 file_count
      file_count * { u32 off_hi, u32 zsize, u32 size, u32 flags }
            offset = (off_hi << 8) | (flags >> 8 & 0xff);  flags & 0xff = compression (0 none, 2 LZ2K)
      i32 name_count
      name_count * { i16 next, i16 prev, i32 name_off }
            next > 0 -> directory;  next <= 0 -> file with index -next
            prev != 0 -> sibling of record prev;  prev == 0 -> first child of the preceding directory
      i32 names_size, names blob (NUL-terminated strings)
      file_count * u32 crc

Differences by version:

- **-2** (Batman, Indy): as above.
- **-3** (TCS): the index offset is stored plainly, and **a file is found through a hash of its upper-case
  path** (FNV-style, prime 0x199933, start 0x811C9DC5), not through the number in its name record. Ignoring
  this extracts every file under the wrong name. All 12,174 names hit the hash table.
- **-5** (Marvel): 12-byte name records, plain index offset.

## LZ2K (`lz2k.py`)

A stream is a sequence of chunks: `'LZ2K'`, u32 unpacked size, u32 packed size, packed bytes. Each chunk is
an LZH bitstream of the LHA -lh5- family: 8 KB sliding window, blocks that start with a 16-bit symbol count
followed by three Huffman code-length tables. Marvel also has stored (uncompressed) chunks.

## NU20 scenes and models (`nu20.py`)

`*_pc.gsc` (scenes) and `*_pc.ghg` (models). In these games the file is "NU20 first":

    'NU20', i32 -nu20_size, u32 version, i32 -1
    tagged chunks (tag[4], u32 size including the 8-byte header):
        HEAD NTBL TREF TST0 MS00 SST0 INID FDNS BNDS DISP VBIB SALI DYNO GSNH PNTR

- Character models are the same container, version 4, with no `GSNH` chunk: the scene header is reached
  through the pointer at offset 0x1C and sits inside a `CDAT` chunk.
- Textures are DDS. `nu20.py export` writes them as DDS and PNG, plus `scene.obj` and `scene.json`
  (materials, meshes, models, named special objects with their matrices, bones).
- **Skeleton:** bone table at scene header +0x164 (count, then pointer); 96-byte records with a name pointer
  and parent index, followed by bind and inverse-bind matrices. The rest pose is the bind array (its world
  transforms are exactly the inverses of the inverse-bind matrices). The matrices in the 96-byte records are
  not the rest pose.
- **Skinned vertices** (stride 36 or 40): the last 8 bytes are 3 weight bytes + 1 unused, then 3
  palette-index bytes + 1 unused. Each mesh record carries a palette of up to 8 bone indices.
- **Open:** per-mesh material pairing in character files (37 of 103 meshes pair correctly on the studied
  hero); camera data in `_cam_pc.gsc`; TCS materials.

Units are metres, Y up.

## AN3 animation (`an3.py`, `anim_export.py`)

`chars\<name>\<anim>_pc.an3`. Header fields as documented by BactaTank Classic / EasyAN3:

    u32 tag ('8INA' / '6INA': two versions), u16 nodes, u16 frames, u16 curve_group_size, u16 original_frames, ...
    name as text at offset 80

Worked out here against the skeleton:

- Per node 9 channels in this order: translation x y z (metres), rotation x y z (radians), scale x y z.
- A channel's key type is either >= 16, meaning constant number (type - 16) in the constants table with
  value = `constBase + u16 * constScale`; or 6, meaning an animated curve (numbered in order of appearance).
- Animated curves: `curveGroupSize / 4` of them, each with an f32 scale and f32 minimum. Keys are u32, one
  per four-frame segment. The low byte is an anchor (0 to 255); the four 6-bit fields are that segment's
  four frames, each a blend (0 to 63) from this anchor to the next segment's anchor.
  Value = minimum + scale * blended anchor.
- Rotation: Euler angles applied X, then Y, then Z, as row-vector (Direct3D-style) matrices.
- **Animations are stored mirrored (Z negated) relative to the model's skinning pose.** Every bone's
  animated translation z is exactly minus its bind z. To use an animation on the model, mirror each local
  transform: `M' = S * M * S` with `S = diag(1, 1, -1, 1)`. Without this the head is about 170 degrees off
  and the figure faces backwards.
- Playback rate is not in the file: it is `fpsec=` in the character's `.txt` (30 if absent).
- Marvel's `.an4` is the same thing in big-endian, with several animations per set.
- **Open:** animations with a node count other than the skeleton's (two-character and prop animations).

## CU2 cutscenes (`cu2.py`)

`cut\...\<name>_pc.cu2`, plus a scene of its own. No community documentation was found; this is from the
files. A `.cu2` is a memory image: every pointer is an absolute address and the file's own load address is
the u32 at 4.

    0x00 u32 version (520)   0x04 u32 load address   0x08 f32 length in frames   0x5c f32 frames per second (30)

It holds a cut list (frame, camera); cameras (position, direction, lens, movement as an animation block);
set pieces of the scene that it moves; and characters, each with a position track and a whole-skeleton
animation block made for that character's own skeleton. The animation blocks are the AN3 format with one
more curve type (7): two words per four frames = a 16-bit value and four 12-bit blends toward the next.

**Open:** the effects section; a third track per character (probably expressions); two numbers per camera.

## GIZ gizmo placement (`giz.py`)

    u32 version (1), then sections: u32 name_len, name, u32 body_size, body

Decoded: `GizmoPickup` (name, position, type letter `s`/`g`/`b`/`p`/`m`/`r`, flag) and a few more. Most
section bodies are still open. `.gin` (binary gizmo instance data, Indy) is not read.

## GIT puzzle logic (`git_study.py`, `level_anatomy.py`)

Plain text, one per level area. See `GAME_NOTES.md` for the model.

## Plain-text files

- `chars\<name>\<name>.txt`: character definition (flags, numbers, animation blocks).
- `<area>.txt`: level settings, including the camera "sock" blocks and `story_coins`.
- `scripts\*.scp` and `<area>\ai\*.scp`: AI state machines.
- `.ats`: sprite animation scripts (the stud spin is frames 0..31, one step every 2 ticks).
- `.fnt`: a DDS image with a glyph table (count at 0x1C, height and base at 0x24, 12-byte records from 0x6C).

## Not read at all

`.ai2` (paths and trigger areas), `.spl` (splines), `.ptl`/`.par` (particles), `.ctr`, `.cc2`, `.csc`, `.gra`,
`.ter`, `.sf`.
