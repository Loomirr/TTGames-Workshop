# giz.py report

File changed: `tools\giz.py` (only this one; uncommitted).
Everything below marked "measured" was run on all 525 `.giz` files (TCS 251, Indiana Jones 103, Batman 171).
Scratch scripts and raw output: `scratchpad\agent_giz\` (`verify.py` -> `verify.out`, `regress.py`, `scan1..9.py`).

## 1. File framing

    u32 file version (1)
    sections:  u32 name_len (1..64), name (no NUL), u32 body_size, body
    u32 0      end marker (a name_len of 0), then end of file

**What stopped the walker (measured):** nothing was misframed. The "unread tail" is the 4-byte end marker
`00 00 00 00`; the old loop saw name_len 0 and stopped without counting it. It is present in 520 files
(TCS 248, Indy 103, Batman 169) and nothing follows it in any of them.

The five files that are not "sections + end marker":

| File | What it is (measured) | Now |
|---|---|---|
| Batman `fairground_funhouse.giz`, `fairground_rollercoaster.giz` | old leftovers (no `.git` beside them): sections run exactly to end of file, no end marker; odd section name `force`; 3-byte headers | fully accounted for |
| TCS `ASTEROIDCHASE_INTRO.GIZ` (543 bytes), `LOSTDEATHSTAR2BATTLE_D.GIZ` (3,644 bytes) | every byte is zero, so "version 0" | rejected: "file is N zero bytes" |
| TCS `PLOPSARLACCPIT_C.GIZ` (24,576 bytes = 0x6000) | cut off: its GizmoPickup section claims 3,094 bytes, 1,100 are left | whole sections returned, cut-off reported, pickups rejected |

Files where every byte is accounted for:

| Game | Before | After |
|---|---|---|
| TCS | 0 / 251 | 248 / 251 (2 all-zero, 1 cut off) |
| Indiana Jones | 0 / 103 | 103 / 103 |
| Batman | 2 / 171 | 171 / 171 |

## 2. GizmoPickup

The brief's premise was slightly off (measured): the failing tables are **version 4**, not 5 and 6.

| Version | Files | Header | Record | Evidence |
|---|---|---|---|---|
| 4 | TCS 5 (4 whole + the cut-off file) | 12 bytes: u32 version, u32 count, u32 (=1) | 23 bytes | size = 12 + 23*count in 4 of 4 whole files; 391 records, all letters s/g/b/m/z, all positions sane |
| 5 | TCS 36 (35 empty, 1 with 135 records) | 20 bytes, same as v7 | 23 bytes | the one non-empty file fits 20 + 23*135; letters s/g/b/m/r. One file only: thin |
| 6 | TCS 2, both empty | 20 bytes | not known | empty tables are accepted; a v6 table with records is rejected as unverified |
| 7 | TCS 206, Indy 103, Batman 168 | 20 bytes: u32 version, u32 count, u32 (0/1/3), f32 (mostly 10.0), f32 (mostly 1.0) | 23 bytes | unchanged |

Record (same in 4, 5, 7): `char name[8], f32 x, y, z, u8 type_letter, u8 flags, u8 ?`.
The v4 files are development leftovers (`GUNGAN_A.GIZ` in the GUNGAN_B folder, `PRE_GLYN_JEDI_B`, `KAMINO_C_BACKUP`,
`ARSESARLACCPIT_C`, `PLOPSARLACCPIT_C`).

**The nonsense letters and absurd positions are not a layout problem (measured).** They are in three v7 files whose
tables are correctly framed (size = 20 + 23*count) but whose contents are damaged in the file itself:
- `RETAKE_E.GIZ` records 4..47 and `E1CHARACTERBONUS_A.GIZ` records 0..43: the same ~1,000 bytes of unrelated
  editor data (strings `force19`, `gate_011`, `light_a57`, `disc3`, `r2_lift`) lie over 44 records, starting in the
  middle of a record. Real pickups resume right after.
- `MAUL_A.GIZ` records 77 and 78 are all zero (blank slots).

These 90 records are still returned (indices stay stable) with a new key `"valid": false`. A record is valid when
its letter is one of `s g b p m r h c u e z`, its name is printable and its position is finite and under 5,000 units.

| Game | Tables read before | after | Pickups before | after | valid | not valid |
|---|---|---|---|---|---|---|
| TCS | 244 (5 rejected, 2 zero files) | 248 (3 rejected: the 2 zero files, the cut-off file) | 14,528 | 14,919 | 14,829 | 90 |
| Indiana Jones | 103 | 103 | 8,291 | 8,291 | 8,291 | 0 |
| Batman | 168 (3 files have no table) | 168 | 10,701 | 10,701 | 10,701 | 0 |

- Regression (measured): for all 515 tables the old code read, the new output is identical except for the added `valid` key.
- Largest coordinate of any valid pickup: TCS 2,816 (vehicle levels), Indy 77, Batman 168. Positions were checked
  for sanity only, **not** against each level's real bounds (scene files were not read).
- Letters `c` (375, names `c_pup1`), `u` (38, `u_pup1`), `z` (20, unnamed) and `e` occur only in TCS; their meaning
  was not looked up, so they stay type `unknown` but valid. (`e` occurs only inside the damaged records; it is in the
  allowed set because the brief listed it.)

## 3. Other sections

Header forms (measured: no section of any readable file fails these, and count is 0 exactly when the body is only its header):

| Header | Sections |
|---|---|
| u8 version, u16 count (3 bytes) | GizObstacle, GizBuildit, GizForce, GizTurret, BombGenerator, GizDig |
| u32 version, u32 count (8 bytes) | all others below |
| u32 version, u32 count, u32 ? (12 bytes) | Torp Machine v3/v4 (8 bytes in v1/v2), GizmoPickup v4 |
| u32 version, u16 count | GizFlock (**guessed**: consistent, count not independently checked) |
| u8 version, u8 (=1), then floats, no count | ShadowEditor: one settings block; size by version 1:18, 2:26, 3:34, 5:46, 8:66, 9/10/12:70 (measured, 517 files) |
| empty body (0 bytes) | GizFlock, Panel, SecurityDoor, Spinner, blowup, `force` in some files |

Fixed-size records that begin `char name[16], f32 x, y, z` (measured: every body of that version is exactly
header + count*record, every name printable, every position sane; rest of the record not decoded):

| Section | Version: record bytes (non-empty files / records) |
|---|---|
| Attracto | 3: 31 (22 / 44) |
| BombGenerator | 1: 58 (9 / 14) |
| Grapple | 10: 61 (3 / 6) |
| Lever | 6: 54 (39 / 161), 7: 55 (2 / 9), 9: 58 (66 / 176) |
| Plug | 2: 35 (2 / 8), 3: 36 (3 / 7), 4: 37 (2 / 2, thin), 5: 39 (64 / 196), 6: 43 (4 / 19) |
| SecurityDoor | 3: 40 (3 / 9) |
| Shard | 2: 32 (23 / 1,156) |
| TightRope | 2: 50 (2 / 4), 4: 75 (25 / 33) |
| Tube | 2: 37 (19 / 61), 3: 38 (6 / 9) |
| Whipper | 4: 56 (30 / 42) |
| ZipUp | 2: 60 (3 / 10), 4: 62 (67 / 178), 6: 65 (39 / 50) |

Check against the `.git` files (measured): gizmo names the `.git` gives for a type were looked for in that
section of the same area's `.giz`. Found: e.g. Attracto 44/44, Shard 590/590, Plug 161/161, Lever 400/403,
GizObstacle 7,223/7,255, blowup 7,994/8,166, GizmoPickup 804/811 (first 8 characters). So section name = `.git` Type.

Not fixed-size (seen, not decoded): HatMachine, Torp Machine, Panel, PushBlocks, Puzzle, Teleport hold
length-prefixed strings (u32 or u8 length), so their apparent constant record size is only because names are equally
long. `blowup` has two u32 after its version and the first is not a plain record count (Indy bodies of 168 and
5,851 bytes have it 0). Single-file versions (Grapple 1/8, Signal 2, Techno 1/3, GizObstacle 2, GizTurret 3) were
left out as unproven.

## 4. What changed in giz.py

- `scan(data)`: new; accounts for every byte, never raises, reports the end marker and any problem with its offset.
- `sections(data)`: same return shape; bounds-checked; raises `GizError` (a `ValueError`) for a file version other than 1.
  **Behaviour change:** the 2 all-zero files used to give `[]`, now raise; a cut-off section is no longer returned.
- `pickups(data)`: same return shape plus `valid`; versions 4, 5, 7 read, empty 6 read, anything else rejected with a message.
- New: `pickup_table` (adds header fields), `section_header`, `records` (the table above), `GizError`.
- Command line: `sections` now also prints version, count and whether end of file was reached; `pickups` unchanged
  (JSON is still the list of dicts) and warns about damaged records; new `records <file> <section>`. Rejections print
  one line to stderr and exit 2; no JSON is written then.

## 5. Still not understood / to know

- Record layouts of GizObstacle, GizBuildit, GizForce, GizTurret, blowup, MiniCut, Ledge, Spinner, Signal, Techno,
  Panel, PushBlocks, Puzzle, Teleport, GizDig, GizFlock, most Grapple versions, Tube v5, Lever v8, SecurityDoor v2/v4,
  BombGenerator v2 (variable length); the fields after the position in the fixed records; ShadowEditor's floats.
- GizmoPickup: header word (0/1/3) and two floats; `byte22`; letters c, u, z, e; v6 records (none exist); v5 rests on one file.
- Outside my file, not touched: `level_anatomy.py` reads `p["x"]` or `p["position"]` and compares `type` with
  single letters, while `giz.py` writes `pos` and long type names (before and after this change). It also does not
  skip `valid: false` records. `docs/FORMATS.md` and the README line for giz are now out of date.
