# Observed CU3 / AN4 / GHG layout

These are observations used by source version 0.1.6. The parser
and research readers cover more data than the Blender operator currently
applies. Complete cinematic reconstruction remains experimental.

Research updated: 2026-10-04. Local inputs: Steam PC LMSH1, Batman 3 and DCSV.
These are working observations, not a complete public CU3 specification.

## CU3 envelope — big endian

| Offset | Observed field |
|---|---|
| 0x00 | Declared file extent, or 0xFFFFFFFF; newer LB3 samples use file size minus four |
| 0x04 | Envelope marker 1 |
| 0x08 | Format version: 16, 17, 18 or 19 in the supported corpus |
| 0x0C | Cutscene frame count |
| 0x10 | FPS float, 30 in inspected samples |
| 0x14 | Unresolved field, commonly 0xFFFFFFFF |
| 0x18 | Embedded AN4 tree offset relative to data-blob start; zero with no actor tree |
| 0x1C | Actor metadata record count, including face/attachment nodes |
| 0x20 onward | Variable-length actor metadata records |

Observed actor record base stride: 44 bytes in versions 16–17 and 48 bytes
in versions 18–19, with additional bytes following a variant-count field.
Version 16 has a different float/count-field placement. Each record contains
a blob-relative AN4 node reference, matrix-table index, actor ID, rate/scale
and unresolved fields. The matrix index and actor ID are separate 16-bit
values, not one 32-bit matrix index.

After actor metadata is a big-endian blob size. The blob contains a
little-endian count and table of standalone ANI-D offsets. Embedded tree
placement comes from the envelope's explicit offset; assuming fixed alignment
or equating the tree offset with the offset-table length fails on some samples.
After the blob: big-endian string-table byte count, strings, big-endian matrix
count, and that many 16-float row-major matrices.

The remaining unaligned footer contains additional scene systems, ending
with an `ATSC` marker in the observed files. `cinematic.py` reads the observed
camera, shot-state and rigid tables; the Blender operator does not apply
them yet. Do not infer camera/rigid/locator meaning solely from an ANI-D
node count or its channel count.

## Embedded AN4 tree — little endian

Observed versions 13–16 use the same node/animation-record fields read here:

- 72-byte hierarchy nodes, with child count at +8, record count byte at +12,
  and child/data/name offsets at +20/+24/+28.
- Visibility animation reference at node +32, when present.
- Root string table and first child array at header +16/+20.
- Child name offsets are one-based references into the string table.
- 80-byte animation records: row-major matrix, string offset at +64,
  ANI-D offset at +68 and two 16-bit source range values at +72/+74.
- AN4 offsets are relative to the embedded AN4 root; the CU3 actor reference
  is relative to the containing data blob. Confusing those bases maps actors
  to unrelated nodes.

CU3 actors can contain multiple records. Source range and ANI-D `first_frame`
are not interchangeable. The prototype samples at the cutscene's original
zero-based time and imports onto Blender frames 1..N.

## ANI-D — little endian

The bytes `DINA` represent the numeric ANI-D magic in these PC embedded blocks.
Standalone gameplay AN4 files in our prior LMSH1 work were big endian, so
reusing that file reader unchanged is incorrect.

For the supported pose layout:

- Six channels per node: translation XYZ and Euler rotation XYZ in radians.
- Required format bits 0x20/0x40/0x80; quaternion flag 0x01 is rejected.
- Active translation/rotation groups use node-flag bits 0x02/0x01.
- Type 6 stores four interpolated quarter samples in a 32-bit packed group;
  type 7 uses eight bytes and 12-bit interpolation values.
- Type 14 is zero, 15 is one; observed embedded-constant types >=16 use the
  header minimum/scale when flag 0x20 is set. The research scalar path also
  supports referenced float constants when that flag is absent.
- Explicit compression timing at +72/+76 gives ratio and first source frame.
- Scalar interpolation is kept for translation. Rotation endpoint samples
  become quaternions, are harmonized, linearly blended and normalized. This
  follows our independently checked LMSH1 rotation path.

The research scalar path allows 1, 3, 6, 7, 9 and 10 channels with flag 0x80,
including type-8 step values. Type 8 stores byte indices into a signed 16-bit
integer constant pool, not literal visibility values. The integer count is
the header byte at +17. With external constants, the float pool begins after
that integer pool rounded up to four-byte alignment; assuming an unconditional
four-byte prefix reads the wrong floats.

Nine-channel tracks have scale XYZ in channels
6–8, activated by node flag 0x08. Some other layouts remain unsupported.
Node flag 0x10 cancels cumulative parent scale in source axes, before
translation and Blender basis conversion. Bone bind flag 0x20 and the ANI
header's constant-layout flag 0x20 belong to separate flag fields. Parent
scale cancellation prevents the inflated parts seen in earlier imports.
Scalar decoding alone doesn't establish scene meaning.

## Scene movement and visibility

The outer AN4 node can carry actor placement as well as visibility. The addon
applies decoded group/base transforms separately from the skeletal action.
Source position is reflected through Z and Euler axes use (-rx, -ry, +rz)
before Blender's basis conversion. Sampling uses source zero-based time
`(frame - first) * ratio`, with Blender frame 1 corresponding to source 0.

Seven-channel placement tracks have visibility at channel 6; ten-channel
tracks have it at channel 9. Six/nine-channel tracks have no explicit boolean
and remain visible unless their parent hides. Visibility combines with parent
visibility and is baked as constant hide curves for the instance and children.
These distinctions fixed incorrect overlaps between separate Batman/Robin
shot instances. Typed camera conventions still need game-side comparison.

## Typed footer research

After the scene-vector table and global camera fields, observed camera records
are 56 bytes for CU3 versions 17–18 and 64 bytes for version 19. The reader uses
matrix index +0, standalone ANI reference +2, flags +6, film height/width +8,
focus matrix +16 and lens +26. Following camera records are three state tracks
containing float key times and byte values; the first selects the camera.

The observed rigid table begins 35 bytes after these state tracks. Its count
is followed by 20-byte records: outer string reference, matrix index,
standalone ANI reference, flags and extra fields. Camera convention and
cutscene instance placement need further validation against game playback.

## Growing instance names

`name_editor.py` edits actor names and animation-record names in the embedded
AN4 tree, plus rigid-object names in the outer string table. Actor and record
string references are one-based; outer rigid string references are zero-based.

To avoid shifting opaque animation data, it copies the complete embedded tree,
appends new NUL-terminated ASCII strings and relocates that tree to the end of
the data blob with 8-byte alignment. The tree extent, outer root reference and
actor metadata's blob-relative tree references are updated. Original blob
bytes stay intact, including the old tree and standalone animation table.

Rigid names are appended to the outer string table and their individual
references are patched. Blob/string lengths and the declared file size are
updated while preserving the original size convention. This grows the file
by a copied tree when actor or record names change; it isn't an in-place
same-length substitution.

The output is reparsed and its timeline, hierarchy, matrices and original
numerical animation bytes are checked. Repeat edits and independent edits
of shared strings were tested. Structural name-growth checks passed on 446
actor-bearing CU3 files across versions 16–19. The 255-byte name limit is an
editor policy, not a proven game limit. Runtime loading and any other script
references still need separate testing.

The character planner matches root names after an authored `InstanceN_`
prefix. It allocates unique replacement names within that family and preserves
animation-record labels. In `2BATCAVEFIGHT_INTRO`, both normal Batman roots
share numeric actor ID 1, but Robin, Alfred and tentacles also use the inner
animation label `Instance1_Batman_Cutscene`. That label is therefore not a
reliable character-resource key. The runtime role of the numeric ID remains
unverified. Shared-reference planning is exposed as an optional research scope.

## DCSV: structural support only

The observed DCSV CU3 version word is `0x8000001e` (v30). An extra big-endian
word at +12 shifts the frame count, FPS, tree offset and actor count by four
bytes compared with v19. Values 0 and 1 are accepted for that extra word.
When it is 1, an additional count and array of big-endian references follow
the actor metadata and precede the blob-size field. Their semantics are
unknown; actor-name edits preserve them and their order unchanged.

Embedded AN4 trees use version 20. Some records have a zero animation pointer;
these are inventoried as static records without sampling the tree header as
animation data. ANI-E blocks use `EINA` bytes. The reader exposes their bounded
header fields but explicitly refuses sampling; sharing some ANI-D header
offsets does not prove the curve encoding has the same meaning. DCSV footer
camera and rigid-object readers are also disabled pending verification.

In the 324-file corpus, 297 parse structurally. The 27 rejected metadata
layouts remain unsupported. Longer actor names were tested on 216 actor-bearing
files with the original blob, footer and optional references preserved. There
is no claim of DCSV Blender animation or in-game compatibility yet.

## Archive formats and the installed character-swap experiment

The observed LB3 archive index is `-6`, little endian. File records are
16 bytes: offset-high (u32), stored size (u32), raw size (u32), then a u24
flags field and offset-low byte. The physical file offset is
`(offset_high << 8) + offset_low`. Path hashes use the observed 32-bit
TT FNV parameters. The read-only reader also recognizes DFLT/ZLIB chunks;
LZ2K and other compression require a separate extractor.

DCSV uses `.CC40TAD` version 2 / index kind -12: big-endian tables, 64-bit
file offsets and 64-bit FNV hashes (basis 0xcbf29ce484222325, prime
1099511628211). Every decoded path must match a real file-table hash and all
entries must map. The installed main archives GAME and GAME0–8 were indexed;
all 324 discovered CU3 files were in GAME4. Other index kinds remain unverified.

A private LB3 installation experiment appends an uncompressed replacement CU3
to GAME0.DAT, then repoints exactly its existing 16-byte file-table entry,
using the correct offset split and new stored/raw sizes. Original archive
data and path hashes remain intact. The full archive was backed up and all
original bytes compared after installation: only that index entry differs.
Restore verifies the installed archive before replacing it from the backup.
This installation experiment is documented here; the local game-specific
installer and its backups are not part of the public addon.

The first experiment targeted three Batman instances in the Batcave intro.
It was restored, and the current test targets all ten Batman instances in
`CUT/TITLES/TITLES_START_NXG.CU3`, the opening title sequence that leads into
the menu. CU3 animation bytes and inner record labels were retained. The
installed payload and archive references were verified, and the user reported
on October 3 that Batman was fully replaced with Green Lantern in the opening
cutscene. This validates the tested renamed CU3 and installation method. It
doesn't establish the runtime role of numeric references, compatibility of
every replacement rig/attachment, or DCSV editing in-game.

## Source skeletons

- LMSH1 NXG `LOGH`/HGOL v10 uses name-table offsets and 82-byte joint records.
- Batman 3 DX11 HGOL v16 uses `ROTV` array markers and inline length-prefixed
  joint names. Orientation, locator, parent and flag fields follow each name.
- Both tested main minifig bodies contain 63 source joints with matching names.
  That does not permit substituting rest matrices or mapping by bone count.
- Parent hierarchy and local/inverse-world bind matrix counts are validated.
- Blender bone poses are derived with `convert_local_to_pose` against source
  rest matrices; raw local Euler angles are never pasted onto Blender bones.

The GHG reader supports only the observed skeleton versions above. It does
not import GHG mesh/material blocks. Different attachment/face skeletons must
be supplied separately rather than mapped onto the body.

## Renderer compatibility

Batman 3's installed NXG and DX11 executables both reference `_nxg.cu3`.
Its main CU3 files have that suffix even when the companion minifig model is
`SUPER_MINIFIG_DX11.GHG`. This is evidence for these installed builds, not a
guarantee that all NXG/DX11 games share one complete cutscene layout.

## Discrete outer scene controls

Some LB3 outer ANI-D records use flags `0xAC`, one node with node flags zero,
and nine or ten channels: six type-14 channels, one or two type-8 channels,
then two type-10 channels. In this exact observed layout, the extra channels
are stepped integer controls. They use four bytes per key group and indexed
16-bit constant-table entries; they are not the scale channels of a skeletal
nine-channel transform. Other type-10 layouts remain rejected.

Across 68 records, 77,924 frames decoded within the declared buffers. Slot 6
was boolean in 64 records and is accepted as visibility there. Four records
had non-boolean values, including 25 and 125; their meaning is unresolved and
source visibility is rejected rather than inferred. Other integer controls
are retained without assigning resource or gameplay semantics. Disable source
visibility to inspect a compatible skeletal pose independently.

This fixes reproduced skeletal import failures in `15FORTRESS_MIDTRO1D`
and `16GAME_OUTROE`. The unsuffixed `15FORTRESS_INTRO` and `16GAME_OUTRO`
files inspected here contain no actors. Their animated lettered segments
need to be selected separately; automatic sequence assembly is not implemented.

## Next decoding targets

1. Expand typed scene associations to remaining locator and event records.
2. Verify camera transform/FOV/focus conventions, shot selection and actor
   visibility against game playback, including cutscene instance origins.
3. Resolve model references through cutscene/character definitions and load
   matching GHG/GSC meshes, skeletons and materials.
4. Extend attachment/facial systems after the scale/constant-table fixes.
5. Resolve remaining DCSV metadata and verify ANI-E pose decoding before enabling playback.
6. Confirm character/object replacements in-game and develop a portable archive installer.
7. Implement and validate custom animation writing, including source bone ordering,
   key compression, constants, timing, record references and the inverse Blender pose conversion.
