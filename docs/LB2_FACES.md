# LEGO Batman 2 PC: facial animation (BSA blocks)

Builds on [LB2_ANIMATION.md](LB2_ANIMATION.md). LB2 animation sets carry facial
weights in the same place as LMSH1 and LB3: a `BSA` block hanging off the `Face`
actor's node, holding a one-node ANI-D/ANI-B block of scalar channels, one per
face shape target. The reader already decoded these for the later games
(53 channels). LB2 differs in three ways, now read:

| | LMSH1 / LB3 | LB2 big-endian trees | LB2 little-endian trees |
|---|---|---|---|
| pointer in the actor node | +36 | +36 | +40 (last word of the 44-byte node) |
| magic | `BSA\0` | `BSA\0` | `\0ASB` |
| header words after the magic | header size 20, padded size, size, reserved 0 | same; reserved can be set | header end, padded end, end as **file offsets**; reserved can be set |
| channels | 53 | 37 | 37 |

- **37 channels.** Joker's face meshes import with exactly 37 shape targets,
  `TT_Target_000` to `TT_Target_036`. Catwoman's have fewer (18 on the first),
  all numbered below 37. All 1,057 LB2
  BSA blocks that are not 1-channel tracks have 37 channels, flags `0xA4`, one
  node with node flag 0. Accepted counts are now 37 and 53; others are still
  refused.
- **Little-endian offsets.** In `WALK` (Batman) the face node's last word is
  0x54A0, where `\0ASB` starts; the three words after it are 0x54B4, 0x5554,
  0x5553: 20 bytes past the block, then its padded end and end, in the file.
  Subtracting the block's own position gives the big-endian form (20, 180, 179).
- **Reserved word.** 130 big-endian blocks have 0x01010000 and 29 little-endian
  ones 0x00000101: the same four bytes `01 01 00 00` in both byte orders, so
  probably two byte fields. They do not change the block. They are kept as
  `bsa_reserved` and accepted for LB2 tree versions (1, 2, 4-7) only; newer trees
  still refuse a nonzero reserved word. Their meaning is unknown.

## Checks

- **Every LB2 `.an4`:** 1,057 facial blocks read and sample (320 ANI-B and 578
  ANI-D big-endian, 130 with the reserved word, 29 little-endian).
  - Weights stay between -0.25 and 1.23. The largest step between frames of a
    moving channel has median 0.22: eyes and mouth change over a few frames.
  - 41 stay refused: 1-channel, all-zero tracks on creatures (giraffe and others),
    which have no face shapes.
- **Body and face agree in length** for 886 blocks whose actor has one clip: the
  importer applies these. On actors with several clips (a combo, a jump and
  land) one face block spans the longest clip; which part belongs to each clip
  is not known, so the importer refuses these, as it does for LB3.
- **Blender 5.2.2, original files, the add-on built from this branch:**
  - Joker, `Rifle_TakeHit1`: frame 1 eyes open, frame 20 eyes squeezed shut and
    mouth open.
  - Catwoman, `Takehit1`: target 14 goes 0.98, 0.71, 0.39, 0.09 at frames 1, 10,
    20, 32, and target 13 reaches 0.91 at frame 32, the same values the sampler
    gives; the preview copies show the same weights, and her mouth changes shape.
  - Animation catalog, first 40 clips with a source: facial issues fell from
    22 to 12 (Batman), 31 to 11 (Joker) and 33 to 14 (Superman). Every one left
    is the several-clips case or a length mismatch.
- **Regression:** 800 random LMSH1 and LB3 `.an4` files, every actor, record and
  facial block hashed before and after. 757 are identical. The 43 that changed
  are Marvel files whose 37-channel face blocks now read (41 in tree version 13,
  2 in version 7, such as the borrowed `combat_gandalf` sword sets). The importer
  still refuses a face with a target number at or above the block's channel
  count; these Marvel clips were not checked in Blender.
- `formats/cu3/scripts/test_lb2_faces.py`: constructed trees in both byte orders
  and versions 1, 2 and 7; the reserved word for LB2 and a version-13 refusal;
  36 and 38 channels refused; a little-endian block with the big-endian magic
  refused. All other `test_*.py` in `formats/cu3/scripts` and `formats/character`
  pass, including the two Blender ones.

Not checked: anything in the game. The names of the 37 shapes are not known
(the targets keep their native numbers). The preview's facial shading stays
approximate: Catwoman's mouth interior shows as a dark rectangle around the lips.
