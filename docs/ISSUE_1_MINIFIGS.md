# Minifigure issue #1: patch scope

The [Broken Minifigs report](https://github.com/Loomirr/TTGames-Workshop/issues/1)
contains several separate problems and remains open. The latest source
follow-up is Character **0.5.9** and CU3 **0.1.18**. Historical original-file
results below belong to their stated versions; they do not certify the current
candidates. The supplied LMSH1/LB3 body variant arrays and Avengers index
extension now validate; fresh complete-character visual checks remain necessary.
See the [accuracy review](CHARACTER_ACCURACY_0.5.9.md).

## Shared import follow-up: 0.5.9 / 0.1.18

Four reproducible shared-code defects are corrected: filename-case-sensitive
facial grouping, whole-part loss of authored normals caused by one missing
direction, case-sensitive loose-animation sibling lookup, and a texture lookup
exception for explicitly selected models outside the asset root. See the
[implementation evidence and limitations](CHARACTER_ACCURACY_0.5.9.md).

These checks do not establish a fix for Vulture's eyes, Alfred's seam,
Hulkbuster's shoulder/hatch, or Tony/Mark 6 material remaps. The new native
variant reader resolves the supplied shared bodies using their complete counted
arrays and explicit remaps. Historical 0.5.6 selected its first compatible
skeleton; 0.5.7/0.5.8 rejected the different records. Version 0.5.9 identifies the
full-detail base through native routing, preserving each variant's own binds.
The additional Avengers index records are also now parsed within their verified
layout. Original character definitions, textures and animations were not included
in these samples, so complete import/render comparisons remain local follow-up.

## Earlier follow-up: preview crash and unresolved materials

The newer comments were reviewed individually, including their screenshots:

| Report | Current result |
| --- | --- |
| [Missing `Scene.tt_face_detail` during preview creation](https://github.com/Loomirr/TTGames-Workshop/issues/1#issuecomment-6007411466) | The same missing-property condition was reproduced with a synthetic model. Preview creation/application now restores missing definitions; the settings panel has a recovery button. Actual Blender 5.1.2 and 5.2.2 checks retain existing values, use defaults for new scenes, preserve source meshes/materials and verify failure cleanup. The reporter's original scene was not available, so the cause of its incomplete registration remains unconfirmed. |
| [Tony's arc reactor and Iron Man Mark 6 material remaps](https://github.com/Loomirr/TTGames-Workshop/issues/1#issuecomment-6007499311) | Open. The current shader consumes selected CD texture/tint fields; full material-remap semantics, metallic and emission reconstruction are not implemented. Reports now identify exactly which decoded declarations were used or left unapplied. |
| [Hulkbuster shoulder, white hatch and normal-map concerns](https://github.com/Loomirr/TTGames-Workshop/issues/1#issuecomment-6010525370) | Open. The screenshots establish the symptoms, not the required native shader or texture encoding. Reports retain surface-map selectors and distinguish a missing verified binding from a binding that failed to load/apply. |
| [Vulture eyes and facial layers](https://github.com/Loomirr/TTGames-Workshop/issues/1#issuecomment-6013025977) | Open. The image shows overlapping/displaced detail, but does not establish preview-helper state or expression timing. The comment's suggested General Ross case is not a verified reproduction. |
| [LB3 Alfred face and head-print discontinuity](https://github.com/Loomirr/TTGames-Workshop/issues/1#issuecomment-6015086753) | Open. Previewed facial layers and the stepped head-print seam need their exact original UV/material/animation evidence. The earlier LMSH1 head-print rule has not been applied to LB3 by analogy. |

A separate source inconsistency is fixed: `SpiderFace` was included among
facial meshes but omitted from the live helper's mask/depth grouping. The live
and composed paths now use the same predicate. Synthetic Blender checks compare
equivalent `SpiderFace` and `FACE_*` objects before and after a shape-target
change, including evaluated vertices, polygons, corner normals, copied helper
references and unchanged source data. This does not establish that the fix
resolves Vulture or Alfred.

The material diagnostic is an inventory of renderer omissions. It does not
guess native enum meanings, enable another normal encoding, lower the default
normal strength, weld vertices or change preview depth bias. Use the
[read-only material inspector](DIAGNOSTIC_TOOLS.md) to inspect matching model/CD
declarations without importing a skeleton.

## Historical LOD and arm-print correction

Character **0.4.3** and CU3 **0.1.10** addressed the reproduced LOD selection and
LMSH1 arm print UV problems. Reimporting rebuilds these parts; existing blends
are not automatically rebuilt. Preserve edited scenes before reimporting.

## Corrected

- The reporter's newer example identifies **LMSH1 Whiplash**. Character 0.5.2
  and CU3 0.1.11 additionally load its hair's declared packed DXT5 normal map.
  This is gated to the observed MESH 169 / UMTL 176 surface0 format 5 layout,
  texture slot 6 and native UV selector 4. Tangent X comes from alpha, Y from
  green and Z from blue; the normal image is treated as non-color channel data.
  Other surface encodings remain unsupported. Before/after composed renders
  show recovered hair grooves; the source geometry and native normals remain
  intact, and unchanged native export still has zero patched vertex bytes.
- Static hair and hats were using the first, far-distance display clip.
  The model builder now selects the nearest/highest-detail clip from the
  native, consecutive LOD table. It validates finite descending distance
  thresholds ending at zero, clip bounds and supported draw commands.
  It does not choose meshes by their names or triangle counts.
- LMSH1's shared MESH 169 / UMTL 176 arm materials use **UV0** for CD prints.
  The previous blanket GAME-material UV1 rule hid or misplaced those prints.
  Left/right native role IDs 24/5 and the verified layout gate this exception.
  Torso/head mappings and the other games retain their existing selection.
- The reporter confirms that hip/arm material swapping was already fixed
  in 0.4. Native material role IDs still resolve their respective CD slots.

Source UV coordinates, vertex order, triangles, shape targets, bones and bind
transforms are preserved. Stage draw pools retain their existing interpretation;
the new LOD selection runs only when constructing character/model specials.

## Evidence

Observed accessory draw counts before and after native LOD selection:

| Original file | Previous triangles | Nearest LOD triangles |
| --- | ---: | ---: |
| LMSH1 `HAIR_PEAKED_NXG.GSC` | 412 | 666 |
| LMSH1 `HAIR_SHORTTOUSLED_NXG.GSC` | 484 | 1,116 |
| LB3 `HAIR_KISSCURL_DX11.GSC` | 118 | 1,800 |
| LB3 `HAT_BATMAN2014_DX11.GSC` | 244 | 856 |
| Hobbit `HAIR_HOBBIT_NXG.GSC` | 84 | 778 |

An original-file Blender comparison of Storm reproduces the misplaced arm
printing with UV1 and reveals the shoulder print using UV0. Binary fixtures
cover NXG/DX11 LOD table positions, native clip order, unchanged first-clip
bindings for stage inspection, malformed thresholds and unknown commands.
Material fixtures keep the LMSH1 exception separate from later DX11 roles.
These are decoder/import/render checks, not a new in-game validation.

The packaged character addon was checked on Storm, Wolverine, Magneto,
Batman, Superman, Bilbo and Captain America in Blender 5.2.2. Each loaded a
declared idle clip and exported an unchanged native source bundle. Imported
positions and triangle order match the selected source part; custom normals
match authored directions within one degree of Blender's normal encoding.
The native normal buffers remain byte-identical on unchanged export. Storm's
already unsupported UMTL 172 hair is reported separately and remains missing;
the arm comparison covers her imported body. Storm, Wolverine and Batman
composed renders were inspected. These are selected samples, not a roster audit.

At that checkpoint, the manual repository suite passed 188 tests. Hidden GUI/package checks and
Blender regressions for normals, static stages and facial clip state also pass.
CU3 0.1.10 was checked through the normal import operator on LB3's
`2BATCAVEFIGHT_HUB_INTROC2_NXG.CU3` and LMSH1's `STARKTOWER_INTRO_NXG.CU3`.
Both assembled their expected actor instances, source cameras and packed
textures from read-only installed archives. These import checks do not establish
complete scene or shader fidelity.

## Still being investigated

- **Head textures/faces:** Whiplash is now reproduced; its raw facial
  surfaces overlap without the native depth-mask approximation, while the
  composed result still lacks complete facial/expression fidelity. Animated facial detail meshes, base head
  printing and depth-only masks are different systems. Faces still need the
  live/composed preview helpers and the native shader remains approximate.
  Storm's skinned hair additionally needs the currently unsupported UMTL 172
  material reader; the higher static-accessory LOD fix does not enable it.
- **X-axis mirroring:** no global X reflection has been added. Geometry,
  skeletons, animations, attachments, cameras and export transforms must agree.
  An asymmetric character and a named clip/reference are needed to establish
  which stage of this conversion is incorrect.
- **Area-weighted normals / merging:** the importer already applies authored
  native vertex normals. Duplicate positions can deliberately carry different
  normals, UVs and weights. Automatic welding changes topology and native face
  targets; replacing authored normals can erase intentional hard edges.
  A visible seam example is needed before changing this behavior.

The black points and lines over the reporter's body are Blender rig overlays.
Disable viewport overlays to inspect the surfaces, or create the separate
character preview. This does not repair the underlying facial shader limits.

The issue remains open for these unresolved items. The current candidate's
ownership/archive restrictions must also be considered when retesting these
historical rendering corrections.

## Follow-up: four-game face and skinned-detail reports

Character 0.5.3 and CU3 0.1.12 address the follow-up screenshots of Axel Alonso,
Thrain, Alfred and Captain America AOU. Fixes cover the shifted Avengers texture
list, native alpha cutouts, solid face printing versus masked facial details,
and verified Hobbit/LB3 packed normal maps. The sampled body LOD tables already
select their highest-detail parts; no speculative LOD or topology change was made.
See the [evidence and limits](FACE_ACCURACY_0.5.3.md). These local checks do not
close the remaining fidelity or mirroring reports, and are not in-game validation.

## Follow-up: head printing and normal strength

The next update reports broken Axel Alonso and Blade base-head textures and
suggests normal strengths of 0.3 or 0.4. Character 0.5.5 / CU3 0.1.14 correct
the verified LMSH1 head-print UV layout, confirmed by side and rear comparisons.
They also preserve custom normals lost by facial preview helpers. The character
sidebar offers a viewing-copy normal-strength multiplier; the suggested values
are comparisons, not established native shader values. See
[shading evidence and remaining limits](SHADING_AND_QUALITY.md).
