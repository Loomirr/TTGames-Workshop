# Minifigure issue #1: patch scope

The [Broken Minifigs report](https://github.com/Loomirr/TTGames-Workshop/issues/1)
contains several separate problems. Character **0.4.3** and CU3 **0.1.10**
address the reproduced LOD selection and LMSH1 arm print UV problems.
Reinstall the new ZIP and reimport the character; existing blends are not
automatically rebuilt. Preserve edited scenes before reimporting.

## Corrected

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

- **Head textures/faces:** the report needs exact character names and a
  screenshot showing the failure. Animated facial detail meshes, base head
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

The issue remains open for these unresolved items. The confirmed fixes can be
tested independently in the latest character and cutscene downloads.
