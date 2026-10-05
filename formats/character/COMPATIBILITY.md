# PC character compatibility, 5 October 2026

Version 0.4.1 focuses on the PC NXG/DX11 games. Handheld character support is
separate work and is postponed. Shared file extensions do not imply shared
binary layouts. The Blender game selector offers LMSH1, LB3, The Hobbit and Avengers;
the other profiles below are inspection tools, not complete importers.

## New working coverage

- The Hobbit installed archives use a verified parent-index -5 variant. Its
  v27 definitions, MESH 169/170, DISP 24/26 and HGOL 12/16 resources now assemble
  characters with their native skeletons, attachments and declared animation sets.
- Native material footer role IDs select costume texture slots. A fixed role
  lookup was assigning several arms incorrectly; both arms now use their own
  authored slots instead of guessing from material names.
- Standalone character imports default to the explicit gameplay costume layer
  mask. The file importer also offers cutscene layers or authored flags. This
  restores attachments such as Gandalf's hat. CU3 assembly keeps its existing
  authored layer policy.
- HGOL 15 and the observed ROTV version 17 layout, several older material tables,
  high attachment layer bits and empty customization slots are handled explicitly.
  Other version 17 layouts are still rejected.
- LB3 face targets have variable-length companion arrays. Reading a fixed
  length shifted subsequent targets, rejecting valid faces. The reader now
  validates each array length and continuation marker. Zero-length padding runs
  do not consume vertices, and total decoded vertex counts still must match.
- LOTR's name-tree tags and storage flag fields are handled by its own archive
  profile. Separate path hashes, bounds and node references remain checked.
- LMSH2 archive inventory is available. Sample files include both ANI-D and ANI-E;
  successful ANI-D scalar sampling does not establish character playback support.

## Validation

All 170 portable checks pass, including independently constructed archive,
skeleton, display, material-role and facial target fixtures. Package integrity
checks confirm the ZIP contains tools and documentation, with no game assets.

Full installed-roster preflights were run with the current readers:

| Game | Definitions checked | Parser-ready |
| --- | ---: | ---: |
| LMSH1 | 467 | 342 |
| LB3 | 361 | 280 |
| The Hobbit | 417 | 375 |

These are character definitions across minifig, small, bigfig and creature
families, including alternate and inherited definitions. They are not counts
of unique playable characters. Parser-ready means the probed primary model
and immediate attachment models passed the audit. Recursive attachment assembly,
texture conversion, shader appearance, facial timing and animation playback
need separate Blender checks. Missing companions, ambiguous references and
unsupported native records remain failures rather than selecting arbitrary data.

Blender 5.2.2 checks imported Bilbo, Gandalf, B66 Catwoman, Wolverine and B66
Alfred, loaded idle/run/walk for each, sampled start/middle/end poses and mesh
coordinates, and saved private preview scenes. Front renders were inspected.
The initial 0.3.0 check reported missing conversion metadata for Gandalf's cape;
0.3.1 fixes that store layout. Some shaders, surface smoothing and face masking
remain approximate. No new in-game export
test was performed. Facial shape targets are readable, but cutscene target-weight
timing is still incomplete.

## Other installed PC games

| Game | Confirmed inspection | Current import blockers |
| --- | --- | --- |
| Avengers | Character import and ANI-D playback enabled; CC index, MESH 175, HGOL 17 ROTV, DISP 32, UMTL 229/232/234/235, TXTS 14 | UMTL 228, some target blocks/skin palettes, missing or ambiguous companions, unknown shader flags and runtime attachment layers |
| The Force Awakens | CC archive index, MESH 175, HGOL 17 ROTV | DISP 33, material table 236, ANI-E sampling and some actor bounds |
| DC Super-Villains | CC archive index and animation structure | CD 38, MESH 200, newer HGOL 17, DISP 35 and ANI-E |
| LMSH2 | Full archive inventory; sample ANI-D scalar poses | Newer HGOL 17, DISP 34, material table 270, ANI-E and newer definitions |
| Lord of the Rings | All installed archive indexes; HGOL 10 skeleton | MESH 48, DISP 15 and material table 150 |
| The Skywalker Saga | Container header inspection | New container and model families; no enabled profile |

The local folder labelled Ninjago contains Star Wars III assets and an
uninstaller identifying that game. It was not counted as a verified Ninjago
installation. Neither game gets a Blender support claim from that folder name.

## Reproduce the checks

Run from the repository root with your own game and a cache outside the game:

```powershell
python formats/character/audit_characters.py HOBBIT "D:/Games/LEGO The Hobbit" "output/hobbit-roster.json" --cache "cache"
python formats/character/inspect_game.py LMSH2 "D:/Games/LEGO Marvel Super Heroes 2" "output/lmsh2.json" --cache "cache" --samples 5
python tools/check_repository.py
```

Use `--limit 20` on the roster audit for a quick subset. Reports require a new
output filename. Installed archives are read only; requested companions are
cached separately. Blender checking is manual through the packaged addon or
`check_blender.py` with user-supplied case paths.

Set `"check_unpacked_roundtrip": true` on a CD case in that Blender check's
JSON input to export a fresh native source bundle and verify reimported mesh
counts through the unpacked provider. This flag checks no-op vertex patches
and character assembly, not every declared animation or shader.

The loose-source exporter copies original definitions and texture companions.
Version 0.4.0 also patches supported existing vertex attributes and face targets;
the separate experimental ANI-D writer exports an active native clip.
Version 0.4.1 enables the constrained facial writer for verified MESH 169/170/175
targets. See the [workflow](README.md) and
[earlier animation research](RESEARCH_0.2.md).

## Version 0.3.1 follow-up

The typed TXTS 1/12 conversion-metadata string can have length zero. The reader
now advances from that explicit length and validates the following ROTV marker,
rather than searching the payload for CONVDATE. Empty metadata no longer hides
valid DDS entries. Nonempty metadata still requires the verified prefix.

Gandalf, Thorin, Killer Croc and Hulk were imported in Blender 5.2.2 with three
clips each and checked for finite poses and evaluated mesh coordinates. Front
previews were inspected; embedded cape and bigfig textures are loaded. This is
additional sample coverage, not a claim that all characters or shaders are exact.
The shared reader has 148 portable checks; two package-retention tests separately
verify numeric version selection and preservation of historical builds.

A cached-store audit checked 105 files: 91 typed TXTS 1/12 stores passed,
including 20 with empty conversion metadata. Thirteen TXTS 14 stores and one
version 0 store remain rejected. This checks inventory/DDS boundaries, not
full shader reconstruction or rendering of every texture.

## Version 0.4.0

Avengers now imports configured characters with native skeletons, costume
textures, attachments and searchable ANI-D animation catalogs. A full installed
roster preflight checked **882 definitions; 821 are parser-ready**. This count
checks model dependencies, not all textures, recursive assemblies or clips.
UMTL 228 remains gated; unknown version/layout records still fail explicitly.
UMTL 229 shader booleans remain opaque. Modern untextured face materials use
their authored vertex colors for inspection, with a report warning. No shader
fidelity claim follows from matching record boundaries.

Blender samples include Captain America, Thor, Hawkeye, Black Widow, Iron Man
Mark 7 and Hulk AOU. Character assembly, declared catalogs and playable clips
were checked; six front previews were inspected. Original lighting, layered
shaders, face target timing, gameplay transitions and all roster variants are
not fully reproduced. Avengers CU3 assembly is not enabled by this change.

A raw Captain America front render exposed overlapping teeth and mouth surfaces:
depth-only facial masks were hidden without compositing. The composed face
preview now enables those masks in a separate pass. A close-up render removes
the overlap; live clipping still leaves edge artifacts. An asset-free Blender
check verifies a hidden mask becomes a holdout, reveals the underlying surface
in the composed image, and leaves source vertices and target values unchanged.
This is a rendering check, not full Avengers face-shader or timing validation.

For LMSH1 Wolverine, LB3 B66 Catwoman, Hobbit Bilbo and Avengers Captain America,
source bundles were exported and imported through the unpacked provider. Mesh
counts and a native clip survived. No-op native mesh files were byte-identical;
position, half/float UV and vertex-color edits decoded in place. Source hashes
remained unchanged. This validates representative loose trees, not a full dump
of every installed game or every DLC collision.

Edited six-channel ANI-D rotations round-tripped in Blender for Wolverine,
Catwoman and Bilbo, with sampled maximum pose matrix errors below 0.00004.
The nine-channel scalar encoder has portable checks. Captain America's tested
idle preserved unchanged bytes, but modified export was rejected at Spine2
because the recovered Blender pose contains shear. No approximate matrix was
silently substituted. Shear/reflection or degenerate scale are rejected. Auxiliary tables require
explicit omission for modified clips. No new in-game export test was performed.
General topology, material-node and skeleton writers remain
unfinished. See [editing limits and instructions](README.md).

## Version 0.4.1

Custom normals were assigned before smooth-face flags, changing Blender's fan
interpretation after encoding. The builder now sets smooth flags first. An
asset-free non-coplanar triangle fixture compares imported normals with the
decoded direction, below one packed-normal byte step. Its source positions
remain unchanged. The imported corner baseline keeps untouched exports exact
despite Blender's normal encoding precision.

Packed normal and existing skin-palette edits have independent byte fixtures
for MESH 169/170/175, including incorrect sums, influence counts, unknown palette
bones, normal padding and shared-buffer aliases. Blender checks exported and
reimported edits for Wolverine, B66 Catwoman, Bilbo and Captain America. No-op
models stayed byte-identical and source hashes stayed unchanged. An Avengers
Black Widow bracelet GSC also passed no-op copy, normal patch and reimport;
its zero-normal surface remains gated for editing.

Hobbit MESH 170 facial target writing now requires a bounded full mesh and exact
native target-part membership. Independent dense/run fixtures verify no-op and
edited writes. Decoded checks on 48 cached Hobbit face assets preserve original
bytes for no-op exports, and preserve geometry and every non-offset byte for
target edits. Sources remain unchanged. This does not enable stream growth,
new targets or facial animation timing.
Bilbo's MESH 170 target edit also exported from Blender and reimported with
unchanged Basis and topology. The independent Face Target Writer 0.1.2 package
passed a decoded Bilbo edit without depending on the full checkout.

Native source exports now reject changed rest bones and unsupported material,
image or loaded-animation edits rather than silently exporting their original
data. Skin edits retain each existing palette, four byte influences and a 255
weight total. Topology, new palettes, native bounds, tangent rebuilding,
material/texture encoding, general skeleton edits and animation bank repacking
remain unfinished. Nine-channel edited animation still has the shear limit
described above. These are decoded/Blender round trips; no new in-game test was
performed and no game has a complete fidelity claim.
