# Native facial rendering — experimental

The game's face meshes include surfaces that write depth without writing
colour. Rendering those as ordinary polygons creates rectangles; dropping
them exposes teeth and mouth interiors outside the intended openings.

The native material footer reader identifies `colourWriteMask=0` directly.
Its layout was checked against the installed LB3 material reader and local
UMTL 174–202 files. It handles the removed `SortAfterDeferred` byte, the later
fixup flags, the removed shine-sort field, and bounded variant references.
The final record requires the observed trailer marker. Unknown layouts fail.

## Inspect native material flags

You need your own GHG/GSC and material record metadata from extraction.
The metadata is a JSON array with `offset`, `name` and `index` entries.
The addon does not yet produce complete companion mesh metadata automatically.

```sh
python scripts/inspect_material_flags.py source.GHG source.materials.json new.flags.json
```

The tool protects the input files and existing output files. It reads material
flags, not an entire GHG, and does not install anything into the game.

## Blender preview

Research companion meshes retain `source_model`, `source_part`, `SourceColor`
and the decoded `tt_colour_write_mask` properties. The N sidebar's **TT
Cutscene → Native facial preview** panel can prepare an unconfigured scene
containing those verified meshes. Scene objects must not be shared with another
scene, and an existing compositor is preserved by refusing the operation.

The preview renders solid surfaces and facial details in separate view layers.
Native zero-colour helpers use Holdout in the facial pass; an Alpha Over
compositor places that pass over the solid head/environment. The masks affect
camera rays only and do not cast shadows. A small post-skinning normal offset
approximates TT's depth bias without changing Basis or target coordinates.

**Press F12 to see the composed result.** Solid, Workbench and ordinary material
preview cannot reproduce this depth-only operation. The private V5 files open
with a packed still for immediate inspection. That still is not a cached movie.
Their source watch scenes retain editable camera cuts and audio; rendering
scene strips during playback can be slow. Older cached videos remain old previews.

Version 0.1.6 also offers a [separate live viewing copy](LIVE_PLAYBACK.md).
It uses source-camera raycasts to clip masked facial detail after morph/skin
evaluation in EEVEE. This does not reproduce the exact two-pass operation,
but permits camera-view playback and scrubbing without F12. The source
compositor, stored mesh coordinates and native target export bindings remain.

Live setup now also applies the composed preview's small post-skin depth
offset to its zero-colour facial raycast targets. Without it, coplanar mask
surfaces exposed repeated teeth and mouth interiors in the LMSH1 Stark Tower
example. This remains an explicit rendering approximation: eye/brow clipping
and fine mouth edges still differ from game rendering. Preview modifiers change; source Basis coordinates and topology remain intact.

The revised private V6 viewing copies render new Cycles/compositor movie caches
from those repaired source stages, with recovered audio and editable scenes
retained. A separate inspection scene drives matching face parts together with
Target/Strength controls. Its copied meshes, keys and rigs are independent of
the original cutscene tracks. This is a viewing workflow, not new game-side
facial animation export or a solution to the remaining camera/VFX issues.

`material_preview.attach_normal_map` supports RGB and the observed alpha-X
normal packing, with a selectable green-channel flip. The research builder
checks the native texture slot, channels and texture name before applying it.
Texture packing, layer blending and exact TT lighting still need more work.

`attach_vertex_albedo` and `attach_vertex_opacity` use explicitly decoded
shader flags and the recovered `SourceColor` attribute. Albedo is multiplied
with the existing base-color input; already connected vertex-color graphs are
preserved. Vertex opacity multiplies existing texture alpha only for verified
blend surfaces that do not ignore vertex opacity. The private V7 live stages
use this to restore varying albedo on texture-backed Hulk materials and fades
on cloud/light-ray surfaces. Guessed constant palettes are not multiplied by
native tint a second time. Exact TT lighting/blend equations remain research.

Shader check using a Cycles albedo bake and EEVEE opacity renders:

```sh
blender --background --factory-startup --python-exit-code 1 --python scripts/check_material_preview_blender.py -- --output-dir path/to/writable/checks
```

## Static targets

Blender 5.2.2 creates new shape keys with value 1 in our checked runtime.
`add_shape_keys` now explicitly creates an unmixed Basis and sets each target
to zero. This prevents all expressions from stacking on static companions.
Confirmed BSA animations then drive those weights; no speech weights are
invented for static companions.

Manual regression check:

```sh
python scripts/test_material_flags.py
blender --background --factory-startup --python scripts/check_face_preview_blender.py
```

V5 close-ups are much cleaner, but full shot alignment, exact shaders,
procedural sand, some facial control timing and VFX remain incomplete. This
does not establish a universal face importer or an in-game face writer.

## Current pass separation (0.1.12)

Verified alpha-cutout printing and unbiased legacy solid face surfaces remain
with the body. Mouth/eye detail uses the masked pass. Root-linked body meshes
also become depth holdouts, preventing differently shaded rectangular patches.
Preview offsets use native draw order for coplanar masked surfaces, after
skinning; they approximate depth bias and are not decoded game shader values.
The live helper uses the same classification. Reimport and create a new preview
to obtain source metadata needed by these changes. See the
[four-game checks](../../../docs/FACE_ACCURACY_0.5.3.md).
