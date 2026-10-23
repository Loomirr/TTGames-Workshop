# Animation support

The [per-game shader and facial checklist](VISUAL_AND_FACE_COVERAGE.md) tracks
1:1 rendering, face reconstruction, facial playback and native export as separate
completion requirements. The evidence below describes partial progress.

Start with the [Character addon](../formats/character/README.md) to load a
supported character and choose an animation. To edit one, use **Copy active clip for editing**, change its pose keys, then **Export animation (AN4 / PAK)...**.
For a clip loaded from a PAK, choose **Write PAK with the other source clips** to write a new
bank while keeping the other clips. Exports go to a separate folder.

## What works today

Support depends on the file's actual layout and its matching character rig.
Two games can use `.an4` files with different contents.

| Game / file family | Available workflow | What still needs work |
| --- | --- | --- |
| LEGO Marvel Super Heroes | Supported character animation import and limited AN4 edits. Captain America's edited idle and the rebuilt combat bank passed a user-run game test. | Other clips and edits need their own game checks. |
| LEGO Batman 2 | Supported character animation import. Version 0.5.29 adds experimental editing of its checked ANI-B/ANI-D clips, including both byte orders and reduced-detail tracks. Batman's walk and run passed Blender edit/export/reload tests. | No in-game confirmation for the new writer. |
| LEGO Batman 3, The Hobbit, Marvel's Avengers | Supported character animation import and limited AN4 editing. Shared reader/writer checks cover original clips from these games. | No blanket game verification. Edited face and attachment actions cannot be exported. |
| The Lord of the Rings | Animation reference discovery now uses the observed NXG names. Shared readers accept checked standalone tree versions 8 and 11, with experimental body-clip writing. | These are file-level tools; this does not add complete LOTR character assembly in Blender. |
| Dimensions | Shared readers accept checked standalone tree version 17, with experimental body-clip writing. | Complete character import, some facial controls, and game validation remain unavailable. |
| The Force Awakens, DC Super-Villains, Marvel Super Heroes 2 and other later games | Existing file/reference inspection remains available where documented. | ANI-E motion decoding and full character animation editing remain unsupported. Reading a header does not make a clip playable. |
| The Complete Saga, LEGO Batman 1, LEGO Indiana Jones 1 classic PC files | Read-only [AN3 inspection](../formats/classic-pc/README.md). | Binding AN3 motion to the correct rig, Blender playback and game export. |
| LEGO Star Wars 1, PC | Separate model importer and [ANI/BSA inspection, native-checked scalar sampling and constrained channel edits](../formats/hgp/lsw1/docs/ANIMATION_RECORDS.md). | Verified rig/face binding, clip timing/loops, Blender playback, new clips and in-game export validation. |
| LEGO Star Wars II | Separate [LSW2 addon](../formats/hgp/lsw2/README.md), with its own animation/editing limits. | The shared AN4 writer does not apply to HGP files. |
| LEGO Fortnite | Separate static model workflow. | Animation import/export remains unavailable. |

## Character addon's editing limits

Keep the original bones, rest pose, clip length and frame range. Edits must fit
channels already present in the clip: if a bone has no scale animation, the
exporter will refuse a new scale edit. Zero or negative scales and unsupported
shear are also refused. New animation slots and changes to character animation
definitions are not implemented.

Supported reduced-detail tracks are edited using their own native rigs. Unknown
extra tables remain a reason to refuse export. Leave **Omit unsupported events /
auxiliary tables** off for normal game replacements.

Unchanged clips keep their original bytes. Edited clips are sampled at whole
frames, so motion between frames may differ. Test the resulting file in its
original game, including transitions and distant viewing. A clip that reloads
in Blender has passed a different check from one that works in-game.

## Facial animations

The reader now accepts the checked 54-channel facial layout found in Hobbit
and Avengers files. It retains the extra channel, including when animated.
Reading these values is separate from matching them to a model's face targets;
missing or unverified target bindings are still reported.

This update does not export edited facial animations. Dimensions facial blocks
with the observed `0xA6` flags remain refused until their meaning is verified.

## What was checked in this update

- 67 original LOTR/Dimensions clips: 244 body records read and sampled.
- 44 edited original records: 32 LB2, 6 LOTR and 6 Dimensions. Version, byte
  order, block family, bone flags, extra tables and unrelated original bytes
  were retained. Five additional records with zero/nonpositive scales were
  refused by the existing writer guard.
- Batman's WALK and Run in Blender 5.2.2: Head edit across three detail levels,
  untouched Face actor and 15 other bank members preserved, custom reload,
  and byte-identical re-export when unchanged.
- 31 declared LOTR animation references resolved to the expected bank members,
  actors and clips in three original animation sets.
- 366 previously refused facial blocks: 341 Hobbit and 25 Avengers. More than
  5.1 million sampled scalar values matched a separate decoder. This does not
  establish rendered facial accuracy.

The new paths above have no additional in-game confirmation yet. The confirmed
LMSH1 test remains the baseline. See [export validation](../formats/character/EXPORT_VALIDATION.md)
for the earlier failure, fix and successful game test.
