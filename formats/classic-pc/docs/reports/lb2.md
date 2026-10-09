# LEGO Batman 2: DC Super Heroes (PC) - archives, extraction, census

Date 2026-10-08. Source: `C:\Program Files (x86)\Steam\steamapps\common\LEGO Batman 2\GAME.DAT, GAME0.DAT, GAME1.DAT, GAME2.DAT`
(read only; no program file opened, nothing run). Scratch scripts and raw results:
`...\scratchpad\agent_lb2\` (`probe1..5.py`, `extract.py`, `census.py`, `paks.py`, `anims.py`, `heads.py`, `regress.py`,
`census.json`, `paks.json`, `regress.json`, `extract_GAME*.DAT.json`).

Every statement is marked **measured (n)** or **guessed**.

## 1. Index version -4 layout

All measured on all four archives = 11,865 file entries (5,817 + 4,357 + 1,476 + 215) unless noted.

```
u32 info_off (plain), u32 info_size          info_off + info_size == file size (4 of 4)
"BEGIN_APP_ID_STRINGPakDat v1.01END_APP_ID_STRING" ... (header text, same wording as Marvel's -5)
@info_off:
  i32 version (-4), i32 file_count
  file_count * { u32 off_hi, u32 zsize, u32 size, u32 flags }      16 bytes
        offset      = off_hi << 8            (NOT ORed with a flags byte, unlike -2 / -3 / -5)
        compression = flags & 0xff           (0 stored, 2 LZ2K)
        flags bytes 1 and 2: something else, unknown;  flags byte 3: always 0
  i32 name_count
  name_count * { i16 next, i16 prev, i32 name_off }                 8 bytes (as -2 / -3; not Marvel's 12)
        next > 0  -> directory;  next <= 0 -> file number -next
        prev != 0 -> sibling of record prev;  prev == 0 -> first child of the directory record just before
  i32 names_size, names blob
  file_count * u32 path hash, sorted ascending
  8 zero bytes
```

Evidence:
- **Name record size 8**: with 8 the names-size field is sane and the remainder of the index is exactly
  `file_count * 4 + 8` in 4 of 4 archives; with 12 the names size is nonsense (4 of 4). measured.
- **Tree rules are those of -2**: every `prev == 0` record directly follows a directory record (0 exceptions in
  13,219 name records, all four archives); number of records with `next <= 0` equals the file count, all ordinals
  distinct (4 of 4). measured.
- **Names to files**: `-next` is the file index, AND the hash table gives the same index: the -3 hash
  (0x811C9DC5 start, `h = (h ^ c) * 0x199933`, over the UPPER-CASE backslash path) hits the table for 11,865 of
  11,865 files and its position equals `-next` for 11,865 of 11,865. Lower case, as-is case and the standard FNV
  multiplier hit 0. So -4 is "the -3 hash table plus direct numbers"; the reader uses the direct number. measured.
- **Offset**: with the old rule `(off_hi << 8) | flags byte 1` there are 724 overlapping entries and only 562 of
  5,704 compressed entries start with "LZ2K"; with flags byte 2 it is no better; with `off_hi << 8` alone there are
  0 overlaps, 0 entries reaching into the index, 5,704 of 5,704 compressed entries start with "LZ2K", every one of the
  11,865 offsets is a multiple of 512, the files tile the archive with every gap under 512 bytes, the first file
  starts at 512 and the last ends exactly at the index (4 of 4). measured.
- Flags bytes 1 and 2 are non-zero in most entries (e.g. GAME.DAT 5,754 and 5,552 of 5,817) and are NOT part of the
  offset. What they are: not known (a per-file checksum fragment or leftover is a guess).
- The 12-byte name record and the 4 "extra zero bytes" of -5 are not present in -4. measured (4 of 4).

## 2. Compression methods met

| method | entries | note |
|---|---|---|
| 0 stored | 6,161 | zsize == size in all 6,161 |
| 2 LZ2K | 5,704 | all start with "LZ2K"; all decompress to the stated size with the existing `lz2k.py` |

No other method id occurs in the index (measured, 11,865 entries). No new decompressor was needed in `ttdat.py`.
(521 LZ2K entries of GAME.DAT have zsize >= size; they still read correctly.)
A second, different compression exists INSIDE the `.pak` / `.pac` packages ("Deflate_v1.0" wrapper): `ttpak.py`
already handles it, see section 5.

## 3. Extraction

Free space before: 1006 GB. Output: `<project>\extracted\lb2\game` (git-ignored: `git check-ignore` confirms).

| archive | entries | unnamed | written | bytes unpacked | bytes packed | failures |
|---|---|---|---|---|---|---|
| GAME.DAT | 5,817 | 0 | 5,817 | 1,666,753,798 | 1,292,508,804 | 0 |
| GAME0.DAT | 4,357 | 0 | 4,357 | 2,155,629,117 | 1,233,600,261 | 0 |
| GAME1.DAT | 1,476 | 0 | 1,476 | 2,151,856,775 | 1,228,520,697 | 0 |
| GAME2.DAT | 215 | 0 | 215 | 489,898,611 | 251,418,532 | 0 |
| total | 11,865 | 0 | 11,865 | 6,464,138,301 | 4,006,048,294 | 0 |

Every entry has a name, every file read at its stated size, no path occurs in two archives (11,865 unique paths),
11,865 files on disk. measured. Top folders: GAME.DAT = chars (3,949), cut (600), audio (405), stuff (364),
commonobjects (312), `__dlc1__`, `__dlc2__`, scripts, gui, ...; GAME0/1/2 = levels only.

Extra (my addition, needed to test the animation reader): every package member was also written to
`<project>\extracted\lb2\pak_unpacked\<package path>_unpacked\` (9,328 files, 591 MB). Delete it freely.

## 4. Extension census (11,865 files; leading bytes are the most common "bytes 0-3 | bytes 4-7")

| ext | files | bytes | leading bytes (most common) |
|---|---|---|---|
| .led | 1,991 | 23,026,751 | `17000000 0b000000` x1,607 (little-endian); `<be size> .CC4` x384 or so |
| .txt | 1,669 | 7,266,871 | text |
| .tex | 1,099 | 53,506,901 | `DDS ` x1,098; one Photoshop file |
| .gsc | 976 | 4,442,800,280 | `<u32 BE size> 00000001 "02UN"` x976 |
| .pak | 795 | 435,481,965 | `7a563412` (0x1234567A) x795 |
| .pc_shaders | 715 | 158,286,524 | `<be size> .CC4` |
| .sf | 705 | 1,133,102 | text scripts |
| .dno | 559 | 56,384,839 | `<be size> SERI` |
| .cd | 454 | 4,976,182 | `17000000 0b000000` |
| .as | 426 | 5,440,853 | `17000000 0b000000` |
| .giz | 401 | 2,590,324 | `11000000 00000000` (version 17) x400; `0f000000` x1 |
| .ogg | 394 | 381,043,479 | `OggS` |
| .pac | 362 | 142,812,367 | `7a563412` x362 |
| .ghg | 283 | 263,257,771 | `<u32 BE size> 00000001 "02UN"` x283 |
| .cu3 | 206 | 115,153,098 | `01000000` then big-endian fields |
| .aib | 186 | 277,218 | `<be size> .CC4` |
| .sub | 185 | 47,801 | text |
| .cpd | 178 | 168,671 | `17000000 0b000000` |
| .csv | 119 | 2,609,976 | text |
| .par 64, .ptl 35, .cfg 12, .por 11, .apj 8, .ft2 7, .lua 5, .sfx 5, .binary 4, .fmv 4 (363,916,708 bytes, `FMV!`), .git 2, .ats 2, .fpk 1, .fnt 1, .png 1 | | | |

There is NO loose `.an3`, `.an4` or `.cu2` file anywhere in the four archives (measured). Animations live inside
packages (section 5).

## 5. Reader by reader (construct only, exceptions caught; readers as they stood in the release folder at run time)

| reader | files | reads | result |
|---|---|---|---|
| `nu20.NU20` on .gsc | 976 | 0 | all: "not an NU20-first file" |
| `nu20.NU20` on .ghg | 283 | 0 | same |
| `nxg.Nxg` on .gsc | 976 | 0 | all: "not a .CC4 resource file" |
| `nxg.Nxg` on .ghg | 283 | 0 | same |
| `an3.An3` on loose .an3 | 0 | - | no such files |
| `an3.An4Set` on loose .an4 | 0 | - | no such files |
| `cu2.Cutscene` on .cu2 | 0 | - | no such files |
| `cu2.Cutscene` on .cu3 (extra) | 206 | 0 | all: UnsupportedVersion |
| `giz.sections` on .giz | 401 | 0 | all: GizError, file version not supported (400 are version 17, 1 is 15; the reader knows 1) |
| `ttpak.Pak` on .pak | 795 | 795 | 3,883 members, 1,679 Deflate-wrapped; every member read, every inflated size right |
| `ttpak.Pak` on .pac (extra) | 362 | 362 | 4,993 members, 280 wrapped; all read |
| `ttpak.Pak` on .fpk (extra) | 1 | 1 | 452 text members; all read |
| `an3.An4Set` on .an4 members of the .pak files | 1,731 | 1,731 construct, but only 828 yield animation blocks | see below |
| `an3.An3` on .an3 members of the .pac files | 180 | 0 | all fail (buffer error) |

Package members: .pak = .an4 1,731, .tex 986 (DDS), .txt 982, .cmo 96 (DDS), .cmi 68 (nested package), .krw 20;
.pac = .cbx 1,676, .wav 974, .dsp 886, .cd 444, .as 426, .cbs 229, .an3 180, .cpd 178. measured.

What the model files are (measured on all 1,259 .gsc + .ghg): `u32 BE size, u32 BE 1, "02UN", u32 BE version,
"OFNI" ...` with reversed big-endian tags (OFNI, LBTN, HGXT, SDNB, HSEM in 1,259; LTMU, TDML, PSID, TROP, ATEM in
most). That is the 2013-style BIG-ENDIAN NU20 BODY that `nxg.py` knows, but WITHOUT the ".CC4 / RESH" resource header
in front (a Marvel `.ghg` begins `<size> .CC4 HSER HSER ...`: measured on 1 Marvel file). NU20 versions seen: 0x37
(833 files), 0x38 (129), 0x34 (100), 0x14, 0x12, 0x32, 0x35, 0x33, 0x39, 0x13. The Marvel vertex-list tag "DXTV"
occurs in only 2 of 976 .gsc and 0 of 283 .ghg, so even with the header check passed `nxg.py` would not find its
meshes: the mesh / vertex layout inside HSEM is an earlier one. (That last consequence is guessed from the tag count;
`nxg.py` was not modified to try.)

What the animation members are (measured on all 1,731 .an4 members and 180 .an3 members):
- 1,535 big-endian sets, set version 2 (2 files), 4 (15), 5 (151), 6 (82), 7 (1,285). Marvel's is 13.
  - 828 (all version 7) hold `ANID` blocks: 4,679 blocks, all read by `An3`, 0 block errors (channels per node:
    6 in 3,320 blocks, 9 in 768, 37 in 578, 14 in 11, 1 in 2).
  - 707 hold `ANIB` blocks (about 3,980 blocks; 4 of the files also carry a "BINA"): `An4Set` looks only for `ANID`, so it
    constructs with ZERO blocks. Not read.
- 196 LITTLE-endian sets (version 1: 55 files, version 2: 141) with little-endian `BINA` blocks (673 blocks).
  `An4Set` constructs with zero blocks and a wrong (byte-swapped) version. Not read.
- the 180 `.an3` inside .pac files are named `*_ps3.an3` and are big-endian `ANI9` with a 4-byte size in front
  (builder animations). `An3` fails on all 180.

### Engine generation, file type by file type

| file type | LEGO Batman 2 is | measured on |
|---|---|---|
| archive index | between: -3's hash table + -2's records + PakDat v1.01 header of -5; own offset rule | 4 archives |
| archive compression | 2008-style (LZ2K only) | 11,865 entries |
| models / scenes (.gsc, .ghg) | 2013-side body (big-endian "02UN" NU20, `_nxg` names) with NO ".CC4" resource header and an earlier mesh layout: transitional. Neither reader reads it | 1,259 files |
| ".CC4" resource header | exists already, but only on .pc_shaders, .aib and part of .led | 715 + 186 + ~384 |
| textures | loose DDS named .tex (2013 naming), also packed in .pak | 1,099 + 986 |
| animation | 2013-style AN4 sets inside `_an4_nxg.pak`, older set versions (2 to 7, Marvel 13); 48 % readable now (ANID), the rest ANIB or little-endian BINA. No 2008 `.an3` (the 180 `.an3` are big-endian builder files) | 1,731 + 180 |
| cutscenes | CU3 (2013-style name), not CU2; not read | 206 |
| gizmos (.giz) | 2008-style section file (`u32 version, name, size`) but version 17 instead of 1; not read | 401 |
| packages (.pak, .pac, .fpk) | 2013-style, identical container and Deflate wrapper: fully read | 1,158 packages, 9,328 members |
| definitions (.cd, .as, .cpd, .apj) | binary `17000000 0b000000` (as Marvel's undecoded .cd / .as; likeness to Marvel guessed from CLAUDE.md, not compared) | 1,066 |
| audio | .ogg, and .cbx / .wav inside .pac | 394 loose |

Conclusion: LEGO Batman 2 (2012) is on the NEW ("nxg") engine generation for almost everything - big-endian model
bodies, AN4, CU3, PakDat, TT packages - but one step before LEGO Marvel: models lack the ".CC4" wrapper and use an
earlier mesh layout, animation sets are older versions with ANIB blocks, and the outer archive still compresses with
LZ2K. Only the archive, packages and 828 animation sets read with today's tools.

## 6. Regression (edited `release\...\ttdat.py` against untouched `<project>\tools\ttdat.py`)

| archive | version | entries old | entries new | whole table identical (path, offset, zsize, size, method) | named | 26 sample files byte-identical |
|---|---|---|---|---|---|---|
| Lego Batman\GAME.DAT | -2 | 10,366 | 10,366 | yes | 10,366 | 26 of 26 |
| LEGO Indiana Jones ...\GAME.DAT | -2 | 9,242 | 9,242 | yes | 9,242 | 26 of 26 |
| Lego Star Wars Saga\GAME.DAT | -3 | 12,174 | 12,174 | yes | 12,174 | 26 of 26 |
| LEGO Marvel Super Heroes\GAME.DAT | -5 | 6,084 | 6,084 | yes | 6,084 | 26 of 26 |

The unmodified reader still refuses LEGO Batman 2 ("index version -4 not handled"), as expected. measured.

## 7. What changed in `ttdat.py` (the only source file edited; uncommitted)

1. Docstring: LEGO Batman 2 named in the header; a paragraph describing index version -4.
2. `rec_size` table gains `-4: 8`, with a comment; the "not handled" message now lists -4.
3. Offset line: `offset = (off_hi << 8) if self.version == -4 else (off_hi << 8) | ((flags >> 8) & 0xFF)`.

Nothing else: the name-tree walk, the -3 hash path, `read`, and the command line are untouched, so -2, -3 and -5
take exactly the code they took before (section 6).

## 8. Still open

- Flags bytes 1 and 2 of a -4 file record: meaning unknown (not needed for reading).
- The header bytes after the PakDat text (before the first file at 512): not looked at.
- Models: `nxg.py` needs (a) to accept a file that starts `size, 1, "02UN"` with no ".CC4" header and (b) the
  earlier mesh layout (no "DXTV" tag) worked out. Not attempted (not my file).
- Animation: `ANIB` blocks (about 3,980 in 707 sets), little-endian `BINA` sets (196), `_ps3.an3` `ANI9` files (180).
- CU3 cutscenes (206), .giz version 17 (401), .dno ("SERI", 559), .led, .cd / .as / .cpd, .cbx / .cbs audio,
  .fmv video, .ft2 / .fnt fonts: no reader.
- `cu2.py` and `giz.py` were being edited by others during this work; their failure texts above are from the
  version present when the census ran.
- The game was not run and no save location was looked up.
