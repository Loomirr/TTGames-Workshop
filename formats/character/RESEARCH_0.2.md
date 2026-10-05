# Character workflow validation, 4 October 2026

The Blender addon still targets the observed **PC LMSH1 and LB3** character
layouts. Other game profiles below are read-only research/inventory support.

## Working workflow

- Character CD definitions lead to typed animation-set references. AS sets
  recursively contribute shared, combat, ability and conditional actions.
- Schema v25 entries contain ANI4 file/actor/range fields directly. LB3 v29
  entries place those fields in nested `Character Anim Entry Core` objects.
  Nested GAMEANIMDATA objects must not inherit their enclosing entry's schema.
- An original Python TT deflate reader handles `Deflate_v1.0`, including the
  custom block tags and stored-block layout. Decoded bytes matched the reference
  extractor exactly for five LB3 clips and all 27 Wolverine default-bank members.
- Original 0x1234567A PAK member directories are bounded and read without an
  external executable. Animation payloads are decoded when selected.
- Body actions and uniquely compatible attachment actions can play together.
  Native names, skeletons, rest transforms and source geometry are retained.
- Separate viewing scenes use the existing camera-dependent facial mask helper.
  Their meshes are independent copies; source scenes remain available.

Wolverine's checked catalog contained **520 action entries**; Batman cutscene's
contained **497**. These counts include aliases, disabled entries and conditional
sets. They are not counts of visually verified clips or guaranteed gameplay
actions. Ambiguous/missing references remain in the Text Editor reports.

Blender 5.2.2 checks loaded three clips for each character, evaluated finite
poses/mesh coordinates at start, middle and end, switched body/attachment actions,
saved viewing scenes and inspected rendered front views. Green Lantern and
Spider-Man were also assembled, with three loaded clips each and inspected
front previews; their catalogs contained 496 and 571 entries in that check. Batman run/walk can
reference a gameplay cape with a different skeleton from the cutscene cape;
those mismatches are reported and skipped. Body sampling does not establish
complete attachment or shader fidelity.

## Additional installed-game probes

| Game | Archive family | Model findings | Animation findings |
| --- | --- | --- | --- |
| Avengers | CC40TAD v1 / -8, 10-byte name records | Main minifig MESH 175, HGOL 17, DISP 32; observed material table 235 exceeds the current shader reader | AN4 18 / ANI-D; three Captain America bank samples produced finite scalar poses |
| The Force Awakens | CC40TAD v2 / -8, 12-byte name records | Main minifig MESH 175, HGOL 17, DISP 33; newer display ranges require decoding | Observed AN4 19 / ANI-E; some paired/QTE trees also fail current record bounds checks |
| DC Super-Villains | CC40TAD v2 / -12, 64-bit path hashes and offsets | Main minifig MESH 200, HGOL 17, DISP 35; newer geometry/skeleton layouts remain unsupported | AN4 20 / ANI-E, including 65-joint body samples; structural inventory only |

Character schema v31 and animation-set v30/31 primitive fields were read from
Avengers/TFA samples. DCSV character schema v38 remains gated. Inventory does
not enable importing or playing all characters from these games. ANI-E sampling
is still rejected explicitly. Unknown versions and ambiguous paths remain errors.

The research inspector records filenames and actual rejection reasons so new
installs can be compared without guessing support from `.GHG` or `.AN4` alone.

## Export status

Exports target a separate loose-file tree, never DAT archives. The addon copies
native model, definition, texture and animation sources, and can patch supported
existing face targets through the hash/layout-validated writer. No-op facial
exports were byte-identical in LB3 and LMSH1 Blender checks.

General mesh/topology, UV, skin, material and AN4 action encoding is still absent.
Copied source animations do not contain edits made to Blender actions. Existing
RLE face runs cannot be split by the constrained writer. Export manifests and
the operator's warning identify those limits.

## Remaining accuracy work

Native shader layers, original lighting, facial shape-weight timing, IK, gameplay
events/root-motion policy, conditional state transitions, variant cape rigs and
newer game readers still need validation. Camera-dependent raycast clipping is
a preview approximation; camera view is required. Arbitrary viewport orbit is
not the game's depth test. No new in-game replacement or exported-edit test was
performed for this version.

## Format references

Container/compression conventions were researched against Luigi Auriemma's
[TTGames extraction script](https://aluigi.altervista.org/bms/ttgames.bms) and
the public [QuickBMS TT deflate reference](https://github.com/LittleBigBug/QuickBMS/blob/master/src/included/undflt.c).
The reader is original Python; neither reference decoder binaries nor game
engine source are bundled. Standard Huffman/length-distance conventions are
described in [RFC 1951](https://www.rfc-editor.org/rfc/rfc1951).
