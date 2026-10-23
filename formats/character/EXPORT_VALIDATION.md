# Native character export checks

The character addon writes loose native source files into a new folder. It
does not replace an installed character, rename a character slot, or write DAT
archives. Copying the exported files into a mod remains a separate operation.

## Navigation update (0.5.30 / CU3 0.1.37)

The Character sidebar separates import, animation and export. Its export
commands are also available in **File > Export**. Their availability follows
the selected character and active native clip; the next-import game selector
does not change the selected character's export format. Writer checks and
supported edits remain unchanged.

Blender 5.2.2 package checks passed for all eight game choices, panel and export
dialog draws, export selection requirements, saved game enum values and addon
registration/removal. Screenshots of the real sidebar were inspected at its
default narrow width for modern and classic choices and a synthetic selected
rig. Cutscene option draws were checked in all five modes.

Classic batch import now passes its selected game to the model reader. A
synthetic Blender regression checks both Batman 1 and TCS through batch import,
placement and reporting. Original game assets were not retested for this UI
update; it adds no format coverage or in-game validation.

## What edits are checked

Existing vertex positions, UVs, vertex colors, normals, palette-limited skin
weights and existing facial target coordinates have constrained native writers.
They preserve topology, native bindings and opaque file data. Position edits
must stay inside the original bounds. Facial Basis coordinates cannot change.
Repeated facial-offset runs cannot be split without a future stream rebuilder.

Native shader graphs, painted/replaced images, new geometry, removed draws,
new skin palettes, rest skeleton changes and character-definition rewrites are
not supported. Object placement and evaluated modifiers remain preview-only.
This is not yet an arbitrary Blender-to-game character exporter or a new-slot
character creator. [The main instructions](README.md#export-loose-native-files)
describe the supported workflow and separate animation writer.

## Preventing omitted edits

Fresh imports record their model instances and native draw membership. Export
rejects removed/detached attachments, deleted/duplicated draws, newly added
meshes, reparented geometry and changed native draw bindings. Renaming Blender
objects does not change this identity. Complete copies of a model remain
allowed, provided every instance proposes the same native bytes; the existing
shared-source conflict check still rejects different proposals.

Export also requires leaving Edit Mode, so Blender has committed pending mesh
edits before the writer reads its data. An import from an older addon lacks the
assembly inventory: its export report explicitly marks this check unavailable
and asks for reimport. An import that already omitted an unsupported attachment
keeps that omission in the export report. Its bundle contains consumed
resources, not a complete dump of every dependency named by the character.

Windows publication now uses extended paths internally. A valid destination
path no longer fails solely because the private staging suffix takes a native
animation-set filename past the legacy path limit. Logical exported filenames,
path validation, source ownership, hash verification and exclusive publication
are unchanged. Other applications may still have their own long-path limits.

## Reproducible checks

### Additional animation layouts (0.5.29 / CU3 0.1.36)

The shared writer now preserves byte order and ANI-B/ANI-D block family for
checked LB2-era trees (big-endian 2/4–7 and little-endian 1/2). Its detail-table
reader accepts the corresponding original layouts while retaining the same
timing, bounds, alias and source-identity checks. Checked big-endian LOTR trees
8/11 and Dimensions tree 17 are also readable and writable for supported body
tracks. Unobserved tree versions and ANI-E sampling remain refused.

Original-file codec checks passed on 44 edited records across those three games;
the largest integer-frame scalar error was 0.000071. Five records containing
nonpositive scales remained refused. In Blender 5.2.2, LB2 Batman's WALK
(little-endian tree 2 / ANI-B) and Run (big-endian tree 6 / ANI-B) both exported
a Head translation edit across three native detail tracks. Maximum edit-delta
matrix differences were 0.0000058 and 0.000014. The Face actor and the other 15
bank members stayed unchanged. Custom reload and unchanged re-export reproduced
the output bank exactly. No installed game files were changed by these checks.

The facial reader separately adds the observed 54-channel big-endian ANI-D/A4
profile. 366 originals passed independent scalar comparisons, including an
animated final channel in Bombur's fall-and-land clip. This does not add edited
facial export or prove model-target bindings.

These additions are not yet game-tested. See the plain-language
[animation support guide](../../docs/ANIMATION_SUPPORT.md) for workflow limits.

```text
python formats/cu3/scripts/test_an4_tree_profiles.py
python formats/cu3/scripts/test_an4_legacy_edit.py
python formats/cu3/scripts/test_an4_facial_channels.py
```

### Animation compression checks (October 21)

The active AN4 exporter now keeps the original raw or `Deflate_v1.0` storage.
This includes animations loaded from a PAK bank: an unchanged action exports
the original stored member bytes, and an edited action is recompressed when
its source was compressed. The source file or bank is unchanged.

`test_animation_export_storage.py` runs the actual exporter in Blender with
synthetic clips. Blender 5.2.2 passed unchanged, edited and stale-source checks
for all six combinations of bank/authored-loose/legacy-loose source and
raw/compressed storage. It verifies the edited translation after decoding,
exclusive output and restoration of the scene's frame/subframe.

```text
blender --background --factory-startup --python-exit-code 1 --python formats/character/test_animation_export_storage.py
```

The shared codec and writer tests also cover multiple compression blocks,
size limits, malformed input, exact source identity, and refusal to rewrite
older/little-endian AN4 layouts that the reader can inspect.

An original LMSH1 Captain America idle reproduced the old compression loss.
Its extra animation table also contains a reduced 41-bone track matching the
model's reduced-detail rig. Character 0.5.26 preserves this supported table and
rebakes the detail tracks against their own native skeletons. Unknown tables
remain unsupported. Restoring compression alone does not resolve every native
animation-writing limitation.

A private LMSH1 Captain America test now has user-confirmed game results.
His shield selects the combat bank's Shield_Idle, rather than the generic idle.
A head-tilt edit preserved both body detail levels, facial data and the other
41 members. Appending the edited member to the bank made the idle work but
left walking/running in rest poses and broke some combat animations. Rebuilding
the same 42 payloads in their original order, with four-byte alignment and at
least two zero padding bytes, worked correctly according to the user's retest.
An unchanged rebuild is byte-identical. The precise engine failure behind the
append method remains unproven; inspected generic loaders use explicit offsets.

Character 0.5.25 offers **Rebuild source PAK bank** for freshly imported bank
clips. Its writer accepts only the measured ordered layout, preserves member
metadata and compression, checks the whole source hash and validates every
stored member. It refuses unknown flags, spacing, aliases, changed storage and
oversized output. Synthetic tests cover growing/shrinking clips, multiple edits,
malformed streams and unchanged output. The Blender test also covers bank
publication and refusal when a different source-bank member has changed.

The game test used a narrow edit to existing native curves, not the generic
Blender rebaker. Do not omit extra tables merely to bypass refusal when
preparing a normal game replacement.

### Detail tracks and custom clips (0.5.26)

The writer keeps the original ANI-D block addresses, detail selector bytes,
aliases and opaque header metadata while appending rebuilt channel streams.
Reduced rigs are selected through the retained model's verified native skeleton
group, including their different parents and bind transforms. Fresh imports
record each bone's curve baseline so untouched channels retain their native
integer samples. Edits are applied relative to the imported Blender pose rather
than baking its original transform approximation back into the source.

Checks completed on October 21:

- Thirteen original records across LMSH1, LB3, Hobbit and Avengers passed decoded
  integer-frame comparisons and compression round trips. Maximum scalar error
  was 0.000327. Detail selectors and unrelated source bytes were retained.
- Ten malformed-input/edit probes were refused. ANI-E remains unsupported.
  Four Hobbit facial blocks retained their original bytes and their existing
  decoder refusals; this does not establish facial playback support.
- Blender 5.2.2 imported Captain America's original Shield_Idle, made an action
  copy, moved the Head keys, and exported the complete bank. All 229 frames
  carried the same edit through the full and reduced rigs within 0.000018 matrix
  error. The other 41 members were byte-identical. Loading that custom bank and
  exporting it unchanged reproduced the bank bytes. The installed game was
  untouched. The subsequent game test failed; see the correction below.
- Three synthetic Blender regressions cover editable custom copies, bank/loose
  custom loading, wrong actor/clip refusal, unchanged re-export, and one shared
  asset index for a two-file standalone animation import.

```text
blender --background --factory-startup --python-exit-code 1 --python formats/character/test_custom_animation_blender.py
```

The encoder bakes whole frames, not the original continuous curves. Fractional
samples differed by up to 0.282 radians in the Captain America check and 2.093
scalar units in another clip; Euler discontinuities may contribute. Integer
round trips do not establish matching motion between frames. New action slots,
clip lengths, native bones and edited face/attachment tracks remain unsupported.

### Collapsed idle correction (0.5.27)

The owner tested the 0.5.26 Blender-exported Captain America bank in LMSH1:
the idle collapsed the character into a line without crashing. This invalidates
any interpretation of the earlier decoded round trips as game compatibility.

Inspection of the LMSH1 decoder found two shared reader/writer errors. Flag
`0x10` selects indexed float constants. With both `0x10` and `0x20` clear,
constants are quantized unsigned 16-bit values, not floats. Clearing `0x20`
also requires one channel-control byte after each type table entry; those bytes
were missing. The writer now sets the float flag and writes the control table.
The reader handles all three constant encodings and both control encodings.

Five independent byte-fixture tests check literal, float and quantized integer
constants, float alignment after integer entries, interpolation controls, the
missing-flag failure and malformed table bounds. The old skeleton-transfer
fixture was also corrected to include its required external control bytes.

The corrected Captain America export passed a separate scalar decoder derived
from native access rules: 1,708,200 channel values across the full/reduced rigs
at one-eighth-frame intervals agreed within 1.8e-15. This is independent code,
not execution of the game or its machine code. Blender import, edit, bank export,
custom reload and byte-identical unchanged re-export also passed again. The
other 41 bank members remain unchanged. **That bank also failed in-game:**
the character became nearly invisible from shrinking and changed size between
animations. Scalar decoding did not exercise the game's loading step.
Recreate edited exports from the original source clip;
previous baked files may be rejected because their control tables are missing.

```text
python formats/cu3/scripts/test_an4_constants.py
```

### Native loading and inactive channels (0.5.28)

The LMSH1 animation loader swaps the bytes of scale pairs across the entire
range from the scale-table pointer to the key-data pointer. The previous writer
placed constants and channel types inside that range. They decoded correctly
offline but were corrupted during native loading. The writer now follows the
observed native order: constants, types and control bytes, scale pairs, keys,
then bone flags. The constant-pool extent ends at the type table.

An independent offline model of those native loading steps reproduces the
0.5.27 corruption: all 936 type words across the full/reduced rigs change, as
do all 124 float constants. The original and rebuilt 0.5.28 bank retain their
types/constants and consume the complete key streams. Sampling after that
conversion checked 1,708,200 channel values per bank at one-eighth-frame
intervals, agreeing with pre-load values within 1.8e-15. This models the loader;
it does not execute the game.

The exporter also preserves each bone's original active-channel flags. A head
edit no longer activates root transforms or scale on every bone. Changes that
would require activating a previously absent channel group are refused.
The original Captain America clip has scale active on only one bone, with
values near 1; there is no evidence for a blanket size multiplier. Whether
root activation independently contributed to the game failure is unconfirmed.

Blender 5.2.2 repeated the original Shield_Idle import, Head edit, full bank
export, custom reload and unchanged byte-identical re-export. All 229 frames
retained matching edit deltas across full/reduced rigs within 0.000018 matrix
error, and the other 41 bank members remained byte-identical.

On October 21, the owner confirmed Test 7 in LMSH1: Captain America's head moved
sideways as edited in Blender, and the other animations were normal. The
supplied screenshot shows the displaced head with the body at normal size.
This confirms the tested Shield_Idle edit and rebuilt combat bank in-game;
it does not establish every clip, distance-dependent detail transition or game.

Thirteen original-record codec checks across LMSH1, LB3, Hobbit and Avengers
also passed with the new table order and unchanged bone flags. Ten invalid
detail-table/source-identity probes were refused; ANI-E remains unsupported.

### File-discovery performance (0.5.26 / CU3 0.1.33)

Loose-file discovery now uses directory enumeration instead of resolving every
ordinary file individually. The measured LMSH1 tree returned the same 20,207
supported paths in 5.44 seconds versus 43.09 seconds before the change. These
are file-index timings on one workstation, not complete character import times.
Meshes, materials and Blender object creation still take additional time.

Archive indexes are reused within the process while their path, game profile
and file metadata match, with bounded cache size and separate extraction budgets.
Standalone animation batches reuse one provider. Seven portable index tests
completed with six passes and one unavailable Windows symlink-creation test;
the existing archive suite also passed. Source-identity, ambiguity and path
containment checks remain enabled.

### Model editing checks

Run `test_export_inventory.py` with normal Python for the assembly-loss tests.
The shared bundle-output suite also tests a Windows path longer than 260
characters, successful publication and cleanup after a forced verification
failure. Neither suite includes proprietary fixtures.

For your own original files, run the separate Blender checker in a fresh
background process:

```text
blender --background --factory-startup --python check_edited_blender.py -- cases.json new-output-folder
```

Each case supplies `source`, `assets` and `game`, as in `check_blender.py`.
Use `--addon-directory extracted-addon` to test a private unpacked candidate,
or omit it to test the single current build. `--features position,uv` selects a
smaller subset; the default checks all six supported edit classes. An optional
`--cache-directory` can reuse an existing extraction cache; outputs still go
to a fresh separate folder, and consumed source hashes are verified.

For every edit, the checker verifies changed decoded native data, unchanged
file size, topology and palettes, untouched original sources, and reimports
the loose character with the same mesh count and no additional attachment
omissions. It also rejects unsupported assembly/material/topology changes
before publishing output and checks an unchanged live-preview copy.

The October 15 original-file pass verified all six edit classes for these
samples in Blender 5.2.2:

| Game | Character | Decoded edits and loose reimport |
| --- | --- | --- |
| LEGO Marvel Super Heroes | Black Panther | Six classes passed; its pre-existing cape-top decoding omission remains |
| LEGO Batman 3 | Batman | Six classes passed |
| LEGO The Hobbit | Dwalin | Six classes passed |
| LEGO Marvel's Avengers | Captain America (Age of Ultron) | Six classes passed |

These 24 checks validate native editing and Blender reimport for the sampled
layouts. A final candidate check also passed, for each of these four games:
six unsupported-edit rejections before publication, another position edit and
loose reimport, and a byte-identical export from the live facial preview copy.
The final run used a longer output root to exercise Windows staging paths.

These are not in-game tests, whole-roster coverage or proof of native shader
fidelity. Game assets, exported sources and detailed local reports are kept
outside the public repository.
