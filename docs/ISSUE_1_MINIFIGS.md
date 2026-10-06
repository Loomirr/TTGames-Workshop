# Minifigure issue #1: patch scope

The [Broken Minifigs report](https://github.com/Loomirr/TTGames-Workshop/issues/1)
contains several separate problems. Character **0.4.3** and CU3 **0.1.10**
address the reproduced LOD selection and LMSH1 arm print UV problems.
Reinstall the new ZIP and reimport the character; existing blends are not
automatically rebuilt. Preserve edited scenes before reimporting.

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

The manual repository suite passes 188 tests. Hidden GUI/package checks and
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

The issue remains open for these unresolved items. The confirmed fixes can be
tested independently in the latest character and cutscene downloads.

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
