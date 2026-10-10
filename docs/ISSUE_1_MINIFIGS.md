# Minifigure issue #1: patch scope

The [Broken Minifigs report](https://github.com/Loomirr/TTGames-Workshop/issues/1)
contains several separate problems and remains open. The latest source
follow-up is Character **0.5.14** and CU3 **0.1.23**. Nine complete character
samples have now been imported and rendered across four game profiles, and two
cutscene actor/camera assemblies checked. These checks establish recovery from
the recent import regressions, not resolution of every visual report. See the
[recovery evidence and limits](RECOVERY_2026-10-07.md). Historical results below
belong to their stated versions.

## Original-material investigation: October 7

The installed LMSH1 definitions confirm that Tony Stark and Iron Man Mark 6
reference separate `Material_Remap` resources. Tony declares
`MAT_TONYSTARKGLOW_FRONT`; Mark 6 declares front, back and leg replacements.
The corresponding GSC material tables decode. The current Blender shader
uses their verified common additive mask, but does not reconstruct the full
replacement shader. Re-extracting the ordinary body textures alone will not
implement those replacements. Their texture selectors,
UV controls and shader properties need to be interpreted together; a material
name containing "GLOW" is not sufficient evidence for an emission formula.
The read-only [material inspector](DIAGNOSTIC_TOOLS.md) now accepts an explicit
replacement library. Original Tony and Mark 6 comparisons retain three
same-named records per declared replacement rather than arbitrarily choosing
the first. Their extracted texture inventories were inspected separately:
Mark 6 includes a reactor mask and BRDF maps, while Hulkbuster's gold resource
includes a cubemap. This explains why treating every binding as ordinary
albedo is insufficient; the native shader formulas remain unverified.

The three same-named replacements are not interchangeable decoded records:
both original libraries differ in `numBones`, `skinned`, `fastBlend`,
`disableFresnel` and native variant-chain pointers. The inspector now lists
these differences explicitly. Matching a material name alone must not select
the first record as a fully reconstructed replacement shader.

Character 0.5.12 / CU3 0.1.21 recover the observed common additive layer for
MESH 169 / UMTL 176 replacement resources. Every exact-name candidate must
agree on slot 1 and UV pair 1, with the observed glow/additive controls.
Conflicting bindings are refused; no full replacement shader is selected.
Original Tony Stark and Mark 6 before/after renders were inspected. Tony's
previously missing cyan reactor is now visible, and Mark 6's reactor receives
its white additive layer. Both unchanged native-export checks passed, including
the consumed replacement resource and texture-store dependencies.

The preview uses unit emission strength. Native brightness/exposure, metallic
and BRDF reconstruction remain incomplete. Gold replacement layers and unknown
version/control combinations are not interpreted through the additive rule.

Character 0.5.14 / CU3 0.1.23 additionally recover observed untextured additive
vertex-color surfaces in MESH 169 / UMTL 177 and MESH 175 / UMTL 202. The
predicate requires the decoded additive/glow controls, vertex albedo and no
layer-0/1 texture. Before/after original Hulkbuster, Mark 6 and LB3 Batman
renders show their eyes/reactor retaining the additive color under shading.
A separate linear emission bake verifies the recovered color multiplication.
All three no-op native exports passed. Environment/shaded glow, refraction,
metallic layers and other layout/control combinations remain separate.

The current GitHub screenshots were inspected directly. Vulture and Alfred's
own idle clips also passed import, facial-preview rendering and no-op export.
Those sampled frames do not prove the reported eye issue resolved throughout
their animation ranges. Alfred's side hair-print step reproduces, and alternate
head UV sampling does not repair it. No blanket UV or transparency adjustment
has been made for these remaining reports.

A separate cross-profile check inspected 79 costume-texture uses on LMSH1
Wolverine, LB3 Alfred, Hobbit Thrain and Avengers Captain America AOU. All
sampled texture alpha channels were fully opaque. This does not support a
blanket transparency change as a fix for these faces; it also does not establish
the alpha semantics of other textures or profiles. Base-head prints, animated
facial details and depth-only surfaces must still be checked independently.

Character 0.5.11 / CU3 0.1.20 enable the existing packed-normal binding for
MESH 169 / UMTL 177. Hulkbuster's shoulder and body materials declare format 5,
texture slot 6 and UV pair 4. Both original maps have zero red, tangent X in
alpha and the same neutral green/blue/alpha pattern as the independently
inspected Hulk and Colossus UMTL 176 maps. An earlier investigation note
mistakenly described Hulkbuster's normal encoding as format 0; that was not
the cause. Format 0 remains unsupported.

Before/after Hulkbuster renders show recovered panel and groove detail, with
15 material uses bound to normals. Source geometry remains unchanged and
native no-op export has zero patched vertex bytes. This is a Blender rendering
and export check, not in-game shader equivalence. Other mesh/table combinations
and surface encodings remain gated. The gold hatch's cubemap shader, reported
shoulder spot, Vulture's eyes and Alfred's head-print seam remain open.

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

## Repeated preview copies and live cutscene quality

Character 0.5.14 preserves facial and attachment animation links when making
a viewing copy from an existing viewing copy, including a composed preview
from a live preview. Previously the second copy reset the target weights and
could not find the original linked meshes by their intermediate copied names.
Links now retain scene-local ancestry, and ambiguous matches are rejected.
Source meshes, shape keys and animation bindings are unchanged.

The asset-free regression reproduces the dropped facial actions before the
fix and checks nested copies, clip switching, attachment links, source
isolation and ambiguous ancestry after it. Original animated close-up renders
cover Wolverine, Vulture, Alfred, Thrain and Captain America AOU in both live
and composed modes at three frames. These expose remaining expression/depth
limitations; passing import checks does not mean every face is accurate.

CU3 0.1.23 uses the highest existing clipping-detail setting when assembling
a cutscene or making its live viewing copy, matching character previews.
Lower detail remains available in the live-copy operator for faster playback.
This reduces polygonal clipping edges; it does not reconstruct the native
facial shader or correct unresolved expression timing.
