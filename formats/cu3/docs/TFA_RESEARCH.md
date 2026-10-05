# The Force Awakens PC cutscenes

The current development source can inspect the actor references in the
observed TFA CU3 versions 22–27. This does **not** enable full character,
environment or camera reconstruction. Most of this game's animation records
use ANI-E, whose sampler remains disabled.

## What was checked

- All 19 installed base/DLC archives were indexed: 105,620 file entries and
  426 CU3 files. Every file path resolved through a stored hash or an explicit
  named override, with file ranges checked against the archive data region.
- All 426 extracted CU3 files passed the bounded structural reader and the
  actual Blender **Inspect scene references** operator in Blender 5.2.2.
- 876 ANI-D animation records passed descriptor preparation and first/last
  scalar sampling. Another 47 records retained explicit unsupported-layout
  errors. This is not full-motion or visual validation.
- Two native minifig animation examples were reconstructed privately:
  ScoutTrooper in `LEVEL01_A2_TREEFALL_NXG.CU3` and Poe in
  `LEVEL7_B_COVERDIVE_NXG.CU3`. Their 63-bone Blender pose matrices matched the
  decoded transforms at five checked frames, with maximum differences below
  0.000012. These examples contain armatures only, without meshes, source
  cameras, materials or environment geometry.
- A private TFA `SUPER_MINIFIG_DX11.GHG` skeleton probe recovered HGOL17's
  native bones and bind matrices. Parent/local/inverse bind consistency was
  checked, but public GHG loading still rejects HGOL17 until broader model
  validation is complete.

No TFA preview has been matched frame-for-frame against the running game.

## Observed format differences

| CU3 version | Files | Embedded AN4 version when actors exist |
| --- | ---: | --- |
| 22 | 4 | 17 |
| 23 | 1 | 18 |
| 24 | 4 | 18 |
| 25 | 21 | 18 |
| 26 | 33 | 19 |
| 27 | 363 | 20 |

TFA's actor metadata can end with a length-prefixed, null-terminated resource
name. Treating that length as an unused word caused every following actor to
be read at the wrong offset. The reader now preserves the string as
`resource_name`, checks its length and terminator, and advances past it. The
runtime precedence of this name versus outer AN4 instance names remains
unverified. Do not assume the LB3 character replacement workflow works here.

Some records have no animation pointer and retain only their static matrix.
The reader preserves those records without trying to interpret offset zero
as an ANI-D header. Each TFA CU3 version is gated to its observed tree version;
unknown combinations are rejected.

## Archive inventory

The standalone reader accepts the observed `.CC40TAD` version 2, type -8
index. It is separate from the DCSV type -12 reader and the older DAT -6
reader. The type -8 file table uses 32-bit path hashes and split byte offsets.
Zero-hash entries resolve through the trailing explicit name/file-ID table.
Its remaining digest metadata is not interpreted.

```sh
python scripts/archive_index_cc8.py GAME2.DAT tfa-index.json
```

Choose a new output filename. This command inventories archives; it does not
decompress game files or install external extraction software. Most base-game
CU3 files in the tested installation are in `GAME2.DAT`; DLC cutscenes also
exist in `DLC8.DAT`, `DLC11.DAT` and `DLC12.DAT`.

## Remaining work

ANI-E motion, TFA camera/object footers, character definition variants,
HGOL17 model binding, shaders, environments, sound and effects still need
dedicated decoding and visual checks. TFA remains an inspection/research
profile rather than an available full-scene assembly profile.
