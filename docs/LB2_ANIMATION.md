# LEGO Batman 2 PC: animation sets (AN4 trees 1-7, ANI-B)

Builds on [LB2_CHARACTERS.md](LB2_CHARACTERS.md) and
[LB2_OLDER_VERSIONS.md](LB2_OLDER_VERSIONS.md). The standalone AN4 reader (`an4.py`)
now reads LEGO Batman 2's animation trees. The shared animation-block decoder
(`cu3.py` `Animation`) also reads its ANI-B blocks. With the older definition
streams (the `.as` animation sets), the Character add-on's LB2 profile now lists
and plays a character's clips, capes included.

## Trees

LB2's 1,731 `.an4` files (unpacked from the `*_an4_nxg.pak` banks) come in two
forms:

| | versions (files) | byte order | header | node |
|---|---|---|---|---|
| tree | 2 (2), 4 (15), 5 (151), 6 (82), 7 (1,285) | big-endian | 72 bytes | 72 bytes |
| tree | 1 (55), 2 (141) | little-endian | 44 bytes | 44 bytes |

- **Big-endian trees** have the LMSH1 layout of versions 13-20: root count at +8,
  string table and first node at +16, nodes with child count (+8), record count
  (+12) and child/record/name pointers (+20). The 80-byte records hold a matrix,
  then name and animation pointers.
- **Little-endian trees** keep the same node fields up to +36 in 44-byte nodes.
  Their first node is at +44. Single-node files would also parse with 72-byte
  nodes. The 9 files with several root nodes or children show the 44-byte stride:
  names, records and children land on valid entries only with it.

The facial-control (BSA) pointer at node +36 is used only for big-endian trees;
little-endian trees refuse it.

## ANI-B blocks

LB2 has two animation-block tags: `ANID` (4,679 blocks) and `ANIB` (3,987,
`BINA` in the little-endian files). They are spread through every character
group. ANI-B has the ANI-D header: counts, flags, frame count, minimum and
scale, nine table offsets, ratio and first frame, at the same positions.
Decoded as ANI-D, ANI-B blocks:
- satisfy every structural check (key stride, scale table, key groups, node
  flags);
- move as smoothly as ANI-D blocks. Per channel, the mean change per frame
  relative to the channel's range has median 0.065 for ANI-B and 0.063 for
  ANI-D, over 94 and 102 blocks. A wrong decoding jumps across the range.
- give correct poses in Blender (below).

So ANI-B is accepted and sampled as ANI-D. The block keeps `variant = 'ANIB'` so
reports can tell them apart.

## Coverage

Every LB2 `.an4` tree now reads. Of the animation records in them:

- **3,221 sample:** all 6-curve blocks (flags `0xE4`/`0xEC`), in every tree
  version, ANI-B and ANI-D.
- **1,023 are 9-curve blocks** (flags `0xA4`/`0xAC`): many level and vehicle
  clips, rides, some taunts. The bare sampler (`prepare()` with no options)
  refuses 9-curve skeletal blocks for every game, as before. The character
  importer does not use that path: `prepare_pose` reads them with the scene
  rules, where channels 6-8 are bone scale, used only on nodes with flag 8.
  All 1,023 read and sample that way.
  - 965 stay inside plain ranges on every frame (translation within 50,
    rotation within 7 radians, scale within 20).
  - 51 of the other 58 are rotations wound past one turn (spins; some table
    minimums are whole multiples of pi, such as -78.54 = -25 pi).
  - 7 have scale keys the files really hold: a scale table entry of minimum
    1.0 and step 15,259,023, so the key runs from 1 to 10^12 (Catwoman's
    `Object` actor in `idle3`, Penguin's save-point and RC switches), and
    Poison Ivy's `whip_crack` root at 100.
  - Blender check below: they pose correctly.
- 2 are 6-curve blocks with flags `0xD4`/`0xDC`, refused as before.

## Blender checks

Character add-on built locally from this branch, Blender 5.2.2 in the
background, original files from the extracted tree:

- **Batman** (`batman.cd`) with three clips from `batman_default`:
  - `idle` (big-endian), `WALK` (little-endian), `Run`: all import, as 321, 21
    and 21 frames.
  - The 27 cape bones move: up to 0.04, 0.08 and 0.14 units between first and
    middle frame.
  - In the bind pose the cape lies flat behind the figure (as LB2_CHARACTERS.md
    noted). In the idle it hangs down the back. The walk and run show a
    mid-stride pose with the cape trailing.
- **Animation catalogs** (`refresh_catalog`), then importing the first 40
  entries that have a source:

  | Character | Animation sets | Clips | With a source | Played (of 40) |
  |---|---|---|---|---|
  | Batman | 57 | 387 | 348 | 39 |
  | Joker | 64 | 452 | 413 | 39 |
  | Superman | 55 | 389 | 350 | 39 |

  - Clips with a source are all members of `*_an4_nxg.pak` banks.
  - Each character lists 39 clips whose source is missing from the game files.
  - Issues reported while playing are about faces and attachments, not the
    body:
    - LB2 facial blocks (BSA header, 53-channel layout) are not verified;
    - some attachment actors are not matched.

## Regression

- 300 random LMSH1 and LB3 `.an4` files (seed 11), every actor, record, header
  and two samples hashed before and after: all identical except two LMSH1 files.
  - An LB2-era `Swim` clip (tree version 7) shipped in LMSH1's lion set now reads.
  - One file's refusal message changed.
- `test_an4_standalone.py`, `test_an4_edit.py` pass.

## Checks

- `formats/cu3/scripts/test_lb2_an4.py`, constructed two-node trees:
  - big-endian versions 2 and 4-7 and little-endian 1 and 2 sample exactly as the
    same tree with ANI-D;
  - versions 3 and 8, little-endian 3, a size mismatch and a little-endian facial
    block are refused.

- **9-curve clips, Blender 5.2.2:** Catwoman (`catwoman.cd`) with `idle3`
  (103 nodes, 175 frames, flags `0xAC`, node 102 with scale) and `whip_crack`
  from `catwoman_default`: both import; mid-clip she stands in the idle and
  strides with the arm out in the whip crack; her 27 tail/cape bones move up to
  0.04 and 0.36 units.

Not checked: anything in the game. Not done: LB2 facial animation, cutscenes
(CU3).
