# LSW1 PC shaders and material accuracy

The goal is to reproduce the original game's material calculations and render
states. Matching a texture in Blender is only one part of that work.

**Current research preview:** ordinary lighting, texture-specular, bump lighting,
plastic reflections and combined bump/reflection paths are implemented for the
checked layouts. [Try the reflection comparison](#reflections-and-combined-bump-lighting).
These are separate research scenes; full game-frame matching is still open.

## Pod energy beams: fixed opaque backing in 0.1.9

The black rectangle behind pod energy beams came from treating an additive
material as ordinary solid plastic. The original PC code selects **source alpha
plus the existing background** for material blend mode 2. Black adds nothing;
it must not cover what is behind the beam.

The addon now uses a transparent surface plus a camera-visible color contribution
for the observed ordinary mode-2 effect. Texture alpha and vertex opacity scale
that contribution. Eevee uses Blended rendering because its Dithered path drops
the glow when surface coverage is zero. The effect does not illuminate nearby
objects. Auxiliary bump/reflection materials also use mode 2, so they are
excluded from this simple preview rather than turned into glowing surfaces.

This fixes background coverage. **Native beam brightness, shader lighting,
reflections, animated texture coordinates and depth/sorting behavior are not yet
matched end to end.** Existing Blender scenes need a fresh import to receive the
new material. Solid viewport shading does not show these effects.

## Evidence from the executable

The original material-state branch at `0x00520F29` reads the low four bits of
the attribute word at material `+0x40`. For mode 2, it calls the render-state
wrapper at `0x00531A30` with these state/value pairs:

| Render state | Value |
| --- | --- |
| Alpha blending enabled (27) | True (1) |
| Blend operation (171) | Add (1) |
| Source factor (19) | Source alpha (5) |
| Destination factor (20) | One (2) |

These identifiers agree with Microsoft's [render-state definitions](https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3drenderstatetype)
and [blend-factor definitions](https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3dblend).
An isolated x86 check executed the original branch for modes 0, 1 and 2,
intercepting the state wrapper and checking its actual arguments. It did not
start Direct3D or render a game frame.

The original corpus has ten directly used mode-2 primitive parts, including pod
effects and a lightsabre part. All ten use effect ID 0, with no linked auxiliary
material. Many additional material-table entries use mode 2 for other shader
passes; the new preview does not replace those.

Twelve numerical render cases in Cycles and Eevee check black, zero opacity,
partial/full opacity and separate texture alpha against a known background.
Original Anakin and Sebulba pod renders were also inspected. Those checks verify
the Blender blending fix, not identical appearance in the game.

## Original compiled shader inventory

The executable contains compiled shader programs and constant tables. The new
Windows research tool found **294 program entries, representing 161 distinct
bytecode sequences**:

| Profile | Entries |
| --- | --- |
| Vertex shader 1.1 | 38 |
| Vertex shader 2.0 | 109 |
| Pixel shader 1.1 | 32 |
| Pixel shader 1.4 | 1 |
| Pixel shader 2.0 | 114 |

Windows' shader disassembler accepted these entries. Constant tables retain
names for shader inputs such as diffuse/specular samplers and specular strength.
This recovers shader assembly and metadata, **not the original HLSL source**.
The inventory currently requires a leading CTAB comment, so it does not prove
there are no other shader programs or fixed-function paths.

### Connecting materials to those programs

The inventory now also follows **136 observed effect registrations**, covering
**68 effect IDs and 88 effect blob locations (82 distinct contents)**. All 294 inventoried shader
entries fall completely inside those registered blobs. Each report entry keeps
the registration address, blob hash, candidate shaders, technique names and
input names. Several initialization paths register different blobs under the
same ID, so the tool retains all of them.

An HGP material's effect byte is not the final shader ID. The original selector
at `0x0052F300` also examines the geometry and current draw. An isolated check of
**6,144 combinations** now cover material bytes 0, 129, 135 and 145. The ordinary
branches return these effects:

| Draw condition | Selected effect ID |
| --- | --- |
| Rigid `0x59` geometry, ordinary blend modes | 9 |
| Rigid `0x59` geometry, blend mode 6 | 11 |
| Skin data present, or vertex type `0x5d`, without active morph weights and data together | 15 |
| The same skinning path, with both morph data and active morph weights | 19 |

These results apply to material effect bytes 0, 135 and 145 and lighting modes
0, 1 and 3 with advanced lighting disabled. Material overrides and the separate
multiple-render-target path are disabled. Byte 129 is described separately below.
Lighting mode 2 calls additional runtime helpers and is outside this check.
This is original-code execution with synthetic structures, not a captured draw.
In particular, having facial targets does not mean the morph shader is active.

For effects 9, 15 and 19, the observed registrations include vertex-shader-only
blobs, shader-model-1.1 variants and shader-model-2.0 variants. The last two
contain both `TECHNIQUE_TEXTURE` and `TECHNIQUE_NOTEXTURE`. The inventory identifies
programs inside each blob; it does not yet decode their individual pass bindings
or establish which initialization branch a particular game session uses.

### Color and opacity are separate calculations

The effect constructor maps `SEMANTIC_MATERIALCOLOR` to its parameter slot at
`+0x78`. Executing the original upload branch at `0x0052AC00` with an intercepted
effect setter verified **12 color/texture-handle cases**:

- Without a runtime texture, it uploads the material RGB unchanged.
- With a nonzero runtime texture handle, it uploads half the material RGB.
- In both cases, the uploaded fourth component is 1.

Runtime handle 0 means no texture. It must not be confused with texture index 0
in a serialized HGP, where the first embedded texture is valid.

Inspection of the shader-model-2.0 candidates for effects 9, 15 and 19 shows
three directional lights plus ambient light. Their textured pixel programs
multiply texture color, the supplied material color and lighting, then double
and clamp the result. The halving at upload therefore cancels the doubling of
material RGB. Applying only the pixel program's doubling would make a texture
too bright.

Opacity follows a different path: those vertex programs pass vertex alpha
through, and the pixel programs double and clamp it, also multiplying texture
alpha when textured. The untextured variant doubles only alpha. These are
assembly findings, **not yet a replacement for the addon's opacity preview**:
runtime vertex preparation, fixed-function variants, pass selection and blending
still need to be connected and compared with actual frames. The 157-model corpus
contains 1,268 used textured material records, all with white diffuse RGB, so it
does not provide a colored-texture example to validate tinting in-game.

## Controlled Blender shader experiment

There is now a separate render experiment for the ordinary shader-model-2.0
lighting calculation. It uses three directional lights and an ambient term,
preserves the supplied normal length, applies the verified material-color
upload adjustment, and reproduces the pixel program's RGB/alpha clamps. It also
supports the observed opaque, source-alpha and additive blend equations.

This experiment is **not enabled in the installed addon**. It does not replace
normal maps, reflections or other special effects with an ordinary material.
Those parts retain their existing importer preview unless a checked comparison
mode is explicitly selected. The effect-129 texture-specular and effect-135 bump
experiments below handle their candidates separately. Normal vectors are stored
explicitly for the selected
pose; moving bones afterward does not update those attributes. The animated-pose
workflow below therefore saves a separate frozen shader scene.

Validation on Blender 5.2.2 LTS:

- A separate arithmetic reference matched **7,680 pixel samples** from a CPU interpreter
  of fifteen original pixel-program entries: ordinary, texture-specular
  and bump candidates. These contain seven distinct pixel bytecodes. A further 512 samples
  checked the specular vertex lookup coordinates against the original rigid
  vertex program.
  Maximum pixel difference was below `5.1e-7`. This is an arithmetic comparison, not
  execution on the original GPU or verification of its partial precision.
- **118 rendered cases** passed in Cycles and Eevee within `0.003` per RGB channel.
  They cover short/non-unit normals, light direction, textured saturation,
  transparency, additive black, texture alpha applied before the alpha clamp,
  separate highlight saturation, lookup alpha independence, display conversion,
  posed normals, the explicit material-145 fallback and the bump-only path.
- Original Anakin pod comparisons applied the experiment to all 58 selected
  parts. Young Anakin applied it to one part and retained ten special-effect
  parts. Both before/after images were rendered and inspected, and separate
  Blender scenes were saved.

The model comparison uses chosen lights, not recovered level lighting. Its
required `--color-space` argument makes the color-space assumption explicit:
`linear` measures the arithmetic directly; `display` treats the shader's RGB
numbers as display values and converts them to Blender's linear output afterward.
The latter is a hypothesis for visual comparison, **not a recovered sampler or
framebuffer setting**. Blender then composites transparency in its own linear
space. Native blending space, vertex preparation, texture filtering, culling,
shadows and reflections remain unverified. A more saturated or flatter image
does not by itself prove greater game accuracy.

Run this in a fresh background Blender process. It writes `importer-preview.png`,
`shader-experiment.png`, matching `.blend` scenes and `report.json` into a **new**
directory. The two images use the same geometry and camera. The importer version
uses Blender lights; the experiment evaluates its own lighting expression from
the corresponding chosen directions and colors.

```text
blender -b --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tools/render_shader_comparison.py -- path/to/model.hgp path/to/new-comparison --color-space display
blender -b --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tests/check_shader_nodes_blender.py -- path/to/new-numerical-test
python formats/hgp/lsw1/tools/check_pixel_programs.py path/to/LEGOSTAR.EXE path/to/new-pixel-check
```

The pixel check uses the shader inventory's optional dependencies and keeps its
original disassembly inside the supplied private output directory. The render
experiment needs Blender and the repository source, without the executable or
additional research libraries. These scripts live outside the installable addon.

### Character highlights: separate texture-specular experiment

The original effect-129 selector, with advanced lighting disabled, returns
candidate 2 for rigid parts and 17 for skinned parts without active morphs.
Active morph data plus weights returns 0 in this branch; it is not silently
substituted with the ordinary morph shader. Together with the ordinary cases,
the native selector check now covers 6,144 synthetic combinations, including
the material-135/145 fallback branches and material 135 with bump enabled.

The parameter upload at `0x0052B0B4` reads the linked material's red component
and multiplies it by 0.1. Six intercepted original-code calls verify this. The
pixel program clamps twice the sampled lookup RGB times that strength, then
adds it to the diffuse result without clamping the sum. Lookup alpha does not
change surface opacity. The vertex program computes lookup UVs from the
transformed normal and a supplied four-row matrix, normalizing all four resulting
components before scaling XY into 0–1. UVs are computed per vertex, not from a
renormalized per-pixel normal.

To opt into this experiment, supply `--specular-matrix path/to/matrix.json` with
four arrays of four numbers. This is an explicit input hypothesis: runtime
matrix construction, advanced reflections, filtering and active pass selection
are still unresolved. The script flips the resulting V for Blender's image
coordinates. Do not describe these scenes as fully accurate game captures.

Original Clone comparisons cover all 17 selected parts with the ordinary path;
Stormtrooper covers all six with the texture-specular candidate. Use
`--preview-pose` for the reversible hand display correction in 0.1.10. Without
it these models retain their short native hand bind, exposing the known wrist
intersection. Other preview poses involving rotation are refused by this static
normal experiment.

### Shader inventory correction

The scanner now walks shader-model-2/3 instruction lengths and skips complete
comment blocks. END-looking values inside constant tables, embedded preshader
metadata or instruction operands no longer truncate the program. This recovers
97 additional entries: **294 entries and 161 distinct bytecodes** in total.
Legacy shader-model-1 scanning still uses a bounded scan and disassembler check.
A recovered program is not yet a reconstructed effect or a proven active pass.

The executable used for the native checks has SHA-256
`49f74d802596b72b8da24b76f98f249dfdb370d5607fa7e65e3a19beb833d473`.
Other versions are explicitly refused by these research tools. Original shader
assembly stays in the caller's private output directory.

```text
python formats/hgp/lsw1/tools/inspect_native_shaders.py path/to/LEGOSTAR.EXE path/to/new-private-shader-folder --disassembly
python formats/hgp/lsw1/tools/check_native_materials.py path/to/LEGOSTAR.EXE path/to/new-state-report.json
python formats/hgp/lsw1/tools/check_native_effects.py path/to/LEGOSTAR.EXE path/to/new-effect-report.json
blender -b --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tests/check_additive_blender.py -- path/to/new-render-test
```

The inventory needs Windows, `pefile` and the system `D3DCompiler_47.dll`.
The state/color and selector checks additionally need `unicorn`. These are optional research tools;
the Blender addon does not load the game executable or require those libraries.
Asset-free registration tests cover alternative blobs for one ID, malformed
ranges, object IDs, signatures and shaders crossing an effect boundary.

## What remains for a full match

1. Complete the verified ordinary-effect selection with runtime initialization,
   technique/pass bindings and special effects. An effect number or matching
   sampler name alone is insufficient.
2. Recover runtime constants, vertex colors, light inputs, texture transforms
   and multi-pass ordering, including normal/reflection and facial surfaces.
3. Extend the controlled ordinary-shader experiment to verified runtime inputs
   and special passes. Record engine behavior that Blender materials cannot match.
4. Compare game captures and Blender renders with matching models, poses,
   camera, textures and lighting. Check animated frames and transitions too.

AI assistance was used for implementation and original-code analysis. No
frame-matched full-shader fidelity result is claimed yet.

## Shader examples at animated poses

The renderer now accepts an explicitly reviewed ANI binding, described in the
[animation preview instructions](ANIMATION_RECORDS.md#try-a-reviewed-ani-playback-example).
Rigid normals follow the sampled attachment bone. Skinned normals use the weighted
pose-times-inverse-bind transforms. Their original length is retained rather than
renormalized. Two additional numerical cases per renderer check rigid rotation
and a two-bone blend. With the material-145 and bump cases, the controlled
Cycles/Eevee checks now total 118 after the reflection additions below.

These are frozen shader snapshots. The separate importer-preview scene keeps the
baked action for playback; the shader-experiment scene deliberately removes that
action because its normal and specular lookup attributes belong to one frame.
This avoids showing moving geometry with lighting frozen in the bind pose.
The normal transforms still need verification against captured runtime skinning
inputs; these tests check the stated experimental equations.

Clone's walking example applies the ordinary shader experiment to 17 parts.
The initial ordinary-only pass on Qui-Gon's walk covered two parts and retained
11 importer materials; Yoda's idle covered one part and retained ten. Their normal-map and special facial
materials are not silently treated as ordinary plastic. Lighting and the optional
specular matrix remain explicit hypotheses, not recovered level settings.

### R2-D2 and Gonk: ordinary fallback for material 145

Pass `--legacy-plastic` to explicitly enable the observed advanced-lighting-off
fallback for material byte 145. The original selector routes it through the
ordinary effects listed above. This comparison accepts only the already checked
lighting/blend modes, with no linked auxiliary or normal-map material. It does
not reconstruct the advanced reflection path or change the installed addon.
Material 135 is excluded from this ordinary fallback. Its separate opt-in bump
comparison is described below.

At sampled animation frames, the new comparison covers all 11 selected R2-D2
parts, seven Gonk parts (three retain importer materials), and all 111 Clone
Walker parts using the ordinary path. Rendered images were inspected. Camera
framing now uses evaluated geometry across the whole baked clip, keeping the
standing and moving model inside one stable view. Playback scenes still use
the importer materials; shader comparisons remain frozen snapshots.

### Face and clothing lighting: bump-only comparison

Add `--bump` to the research render command to enable material 135 with its
observed normal-map auxiliary. This uses the game's bump-only branch, with
advanced reflections disabled. Native selector checks cover 768 combinations
in this branch: rigid parts select effect 27, skin selects 43, and active morph
data plus weights selects 47. That pass brought the selector check to 3,840; the reflection pass below raises it to 6,144.

Six original pixel programs establish the lighting calculation:

- Decode the bump texture's RGB as `2 * RGB - 1`, without normalizing it. Its
  alpha does not control surface opacity.
- Dot that vector with three interpolated tangent-space light vectors, retaining
  their lengths. The vertex program normalizes these vectors before interpolation.
- Add the three positive light contributions and ambient light.
- For textured draws, clamp texture times uploaded material color **before**
  applying lighting, then double the result. There is no final RGB clamp here.
  This differs from the ordinary shader and can produce values above one.
- Double texture times vertex alpha; Blender surface coverage clamps that alpha
  to 0–1. The untextured shader already clamps its doubled vertex alpha.

The rigid and skinned compilations bind diffuse and bump samplers in opposite
orders. The original-program checks supply each texture to its declared sampler.
All 3,072 bump pixel samples matched within `5.1e-7`. A separate 512-input
comparison of the original rigid vertex program verifies basis projection and
normalization within `1e-6`, including its `tangent cross normal` bitangent.

**The game's tangent-generation routine is still unresolved.** The scene tool
uses Blender's MikkTSpace tangents generated in source coordinates and source
UVs as an explicit hypothesis. It transforms the tangent, bitangent and authored
normal separately, then stores the projected light vectors per mesh corner.
It does not substitute Blender's per-pixel Normal Map node. Asset-free Blender
checks cover the coordinate conversion, rigid/skinned basis agreement, temporary
mesh cleanup and refusal of zero authored normals. Unknown auxiliary layouts,
unsupported blend modes and active face shapes remain excluded.

On Blender 5.2.2 LTS, six new cases in each renderer bring the numerical suite
to **50 Cycles/Eevee cases at that stage**, all within `0.003` per RGB channel. The new original
examples were rendered and inspected with the same camera as their baseline:

| Example | Experimental materials | Retained importer materials |
| --- | --- | --- |
| Darth Maul | 3 bump, 5 ordinary material-145 fallback, 3 ordinary | 0 |
| Count Dooku | 3 bump, 5 ordinary material-145 fallback, 4 ordinary | 0 |
| Qui-Gon walking, frames 8 and 17 | 1 bump, 2 ordinary | 10, requiring other blend paths |

These counts describe selected mesh parts, not distinct shaders or full-game
coverage. The comparison uses chosen lights and display conversion. UV animation,
native tangent generation, advanced reflections, special blending and matching
game captures remain open. The installed addon stays on its existing materials.

```text
blender -b --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tools/render_shader_comparison.py -- path/to/DarthMaul.hgp path/to/new-maul-comparison --color-space display --bump --legacy-plastic
```


## Opaque parts and native face culling

The complete material-state routine (`0x520ef0`) confirms that **blend mode 10
is opaque**, like mode 0. It disables blending and fixed-function alpha testing.
Cached alpha fields are not evidence of an active cutout test. The lab now accepts
mode 10 without guessing an alpha threshold, including textures with zero alpha.

`--native-culling` applies the observed face-culling field. This is optional while
native draw ordering is unfinished. The state checker covers 128 combinations of
blend, cull and depth modes, with runtime overrides disabled. Depth-write modes
and special subtractive blends are recorded but not recreated by these nodes.

## Reflections and combined bump lighting

The original advanced-lighting paths now have separate implementations:

| Source material | Rigid / skin / active morph effect | Calculation |
| --- | --- | --- |
| 145 | 35 / 44 / 48 | Reflection added to base color, then lit |
| 135, bump enabled, nonzero reflection scalar | 31 / 45 / 49 | Reflection added after bump lighting |
| 135, bump enabled, zero reflection scalar | 27 / 43 / 47 | Bump-only lighting |

These selections pass the original x86 selector. The shader comparison excludes
active facial targets until their vertex preparation is verified. Original
pixel instructions for the morph variants are tested independently.

The reflection strength blends between two values using a smooth transition
near the surface's silhouette. Native uploads establish the parameters as
`(0.05 + minimum_scale * material_scalar, maximum_scale * material_scalar, 0.2, 0.8)`.
The scalar is at material `+0x60`; the two scale values are runtime globals.
The checker verifies 18 parameter uploads and six player/camera-position uploads.
The scene tool requires explicit scale values and player position in a JSON file;
it does not mistake the executable's initial values for captured level settings.

Several details matter for a match:

- Rigid ordinary reflections clamp textured output; skinned/morph reflections
  preserve values above one. Textured reflection gain differs from untextured gain.
- Combined bump/reflection output is not saturated. Its reflection uses the
  unbumped normal and is added after lighting. Effect 45 samples the opposite
  cube direction to effects 31 and 49; this difference is retained.
- Combined vertex programs normalize the normal before projecting the three
  lights into the tangent basis. Bump-only programs retain its original length.
- Reflection view vectors are normalized per vertex and again after interpolation.
  The rigid vertex tests supply explicit preshader constants; the preshader
  bytecode itself has not been executed in these tests.

The experiment accepts a complete single-level legacy DDS cubemap. It extracts
six 2D faces without changing their pixel blocks, then selects the face and UV in
nodes. The [DDS face order](https://learn.microsoft.com/en-us/windows/win32/direct3ddds/dds-file-layout-for-cubic-environment-maps)
and [Direct3D face-camera orientation](https://learn.microsoft.com/en-us/windows/win32/direct3d9/creating-cubic-environment-map-surfaces)
provide independent layout references. DXT1/3/5 and checked 24/32-bit BGR layouts
are supported; partial cubes, mip chains, padded rows and unknown layouts are
refused. Maximum face size is 2048, with a 128 MiB file limit. An explicitly chosen
equirectangular image can also be used as a test environment.

Create `reflection.json` beside your chosen environment file:

```json
{
  "environment": "negotiations_b_cube.dds",
  "minimum_scale": 0.0,
  "maximum_scale": 0.32,
  "player_native": [0, 0, 0]
}
```

These numbers reproduce the documented experiment, not recovered live game state.
`player_native` uses the game's Y-up coordinates. The environment path is relative
to this JSON file. The output report records its hash and the selected parameters.

```text
blender -b --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tools/render_shader_comparison.py -- path/to/model.hgp path/to/new-comparison --color-space display --bump --native-culling --reflection-profile path/to/reflection.json
python formats/hgp/lsw1/tools/check_reflection_programs.py path/to/private-shader-inventory path/to/new-reflection-report.json
blender -b --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tests/check_cubemap_nodes_blender.py -- path/to/new-cube-check
```

Validation on Blender 5.2.2 LTS:

- 6,144 reflection pixel samples across 12 original programs, plus 512 ordinary
  reflection and 512 combined-bump rigid vertex samples, match within `2e-6`.
- 118 material renders in Cycles/Eevee match the arithmetic reference within
  `0.003`; 36 additional renders check asymmetric cube-face orientation and axis
  centres. Bounding unused face UVs avoids a reproduced Cycles sampling crash.
- Original R2-D2, Darth Maul, Count Dooku, Qui-Gon and Yoda examples use all their
  selected parts, with no retained importer materials. This is part coverage in
  those examples, not a claim about every material in the game. All five saved
  shader scenes reopen with packed textures and reproduce identical PNG pixels.

The saved shader scenes are **frozen sampled poses**. The separate importer-preview
scenes retain their reviewed research animations. Reflections have been rendered
with an original Negotiations cubemap and explicit test lighting. Native tangent
generation, runtime light/camera selection, filtering, shadows, draw ordering,
animated UVs and facial passes still need matching game captures. The installed
addon remains unchanged by this research renderer.

## Native lighting inputs

The original upload routine at `0x52a936..0x52ac00` reads the light block
referenced by draw item `+0x34`. Its three directions start at block `+0x104`,
with a 12-byte stride. Three RGBA light colors start at `+0x128`, with a
16-byte stride; ambient RGBA is at `+0x158`. These are runtime structures,
not identified offsets in an HGP or level file.

The routine halves ambient and light RGB, leaves their fourth component alone,
and copies directions without normalization or coordinate conversion. Direction
uploads use a fourth component of one. The effect constructor identifies these
as `SEMANTIC_AMBIENTCOLOR`, `SEMANTIC_DIRLIGHT0..2` and
`SEMANTIC_COLORLIGHT0..2`. Sixty-four synthetic light blocks produced 448
matching uploads when executed through the original code, including its vector
constructor. Negative and greater-than-one colors were included; this stage
does not clamp or convert them to linear color.

The scene experiment accepts `--lighting-profile path/to/lighting.json`:

```json
{
  "ambient_rgba": [0.48, 0.48, 0.48, 1],
  "directions": [[0, 1, 0], [1, 0, 0], [0, 0, 0]],
  "colors_rgba": [[1.2, 1.16, 1.1, 1], [0.44, 0.5, 0.64, 1], [0, 0, 0, 1]]
}
```

These are **example inputs**, not recovered level settings. Directions use native
Y-up coordinates. The renderer converts them to Blender coordinates, preserves
their lengths, and applies the verified color upload rule. The report records
the profile and its hash. Without this option, the existing controlled test
lighting remains in use. Profiles require exactly three directions and colors;
non-finite values and files over 16 KiB are refused.

This closes the upload-conversion gap, not level lighting selection. Recovering
the light block for a particular character and frame, including any runtime
interpolation, still needs investigation. The importer baseline uses Blender
lights and remains approximate; the experimental materials use the explicit
shader vectors. The native upload checker and arithmetic regressions cover this
path without claiming a matching gameplay screenshot.

## Native tangent calculation

The triangle derivative routines reached from `0x547050` (rigid vertices) and
`0x5471e0` (skinned vertices) are now identified and checked independently.
Their executable bodies are at `0x3b38e13` and `0x3b5ad3c`. Both calculate
the usual position derivatives with respect to UV, with one significant fallback:
if the absolute UV determinant is at most the stored float near `0.0001`, they
use a reciprocal of one instead of dividing. The outputs are not normalized
by these routines.

`shader_tangents.py` implements this triangle calculation. The native checker
executes both original routines, restricts execution to their reviewed address
ranges, and compares the results. The current check covers 1,024 synthetic
calls, including mirrored and collapsed UVs, plus 12,288 calls using 2,048
triangles each from original Count Dooku, Darth Maul and Qui-Gon HGPs. Maximum
component error, relative to `max(1, abs(expected))`, was below `0.000002`.
This compares arithmetic, not GPU output.

```text
python formats/hgp/lsw1/tools/check_native_tangents.py path/to/LEGOSTAR.EXE path/to/new-report.json --model path/to/CountDooku.hgp
```

The caller at `0x547990` processes triangle-strip indices and stores a triangle's
normalized tangent into all three vertex slots, overwriting earlier values.
That observed assignment differs from Blender's tangent averaging. A further
128 tests execute the original strip loop for rigid and skinned layouts,
including repeated indices and untouched vertices. These tests intercept the
external normalization call using its unit-vector contract; they do not execute
the game's lazy-linked math DLL. Untouched scratch slots retain their previous
contents in the game and remain explicitly unknown in the reconstruction.

The call sites at `0x549170..0x549268` select material effect 135 and require the
bump setting. The research renderer now accepts **`--native-tangents`** for
single-primitive triangle strips. It keeps the original index order, normalizes
each triangle tangent, and assigns the last result to each vertex without
averaging or projecting it against the authored normal. Multiple primitives,
other index layouts and rendered vertices depending on untouched scratch slots
are refused by this option. Without it, the declared MikkTSpace path remains.

Dooku, Darth Maul and Qui-Gon's walk frame 17 were rendered with this option in
Blender 5.2.2 LTS, with no fallback materials. These are controlled-light examples,
not matched game captures. Active morph targets remain excluded: their shader
variant and tangent/view inputs need separate validation. This option changes
the research renderer, not the installed addon.

## Shadow receiver equations

Eight original pixel programs now have arithmetic comparisons, covering 4,096
samples, positive/negative projection W, and the secondary color target in the
four floor-level variants. The checker verifies projected texture coordinates
before sampling. The programs use a shadow map and a separate attenuation map.
Their receiver factor is `1 - 0.25 * (1 - shadow) * incidence * attenuation`;
nonpositive projection W disables attenuation. The textured program uses RGB
map components and saturates its doubled textured vertex color. The untextured
program uses red map components, leaves RGB unsaturated, and doubles/clamps
only alpha. The floor variants also copy their interpolated floor value into
the second color target.

```text
python formats/hgp/lsw1/tools/check_shadow_programs.py path/to/private-shader-inventory path/to/new-shadow-report.json
```

These equations do **not** yet establish shadow-map construction, filtering,
light-space matrices, receiver selection or pass ordering. No generic Blender
shadow has been substituted and described as a native match. Facial bump
materials benefit from the tangent experiment above; facial depth masks and
animated face shading remain separate unfinished work.

## Shadow resources and manual face-pose shading

The original resource routine at `0x4f7da0` is now exercised with intercepted
graphics calls. Thirty-six cases cover disabled rendering, empty caches,
partially cached resources and two requested depth sizes. It allocates a
512-by-512, one-level color texture (native format 21, usage 1) and a separately
sized one-level depth texture (format 75, usage 2), then obtains their level-zero
surfaces. Existing resources are reused. The checker assumes successful graphics
allocation; it does not emulate GPU allocation failure or render into those maps.

```text
python formats/hgp/lsw1/tools/check_native_shadow_resources.py path/to/LEGOSTAR.EXE path/to/new-resource-report.json
```

The ordinary active-face vertex shader at `0x6a389c` adds the supplied morph
displacement to the position **before skinning**, while transforming the authored
normal without recomputing it from the deformed face. The combined bump/reflection
variant at `0x693738` likewise retains the authored normal and tangent; it uses
the displaced, skinned position for reflection view vectors. Across 256 synthetic
cases, nine outputs per case match the original instructions within `0.000002`.
These tests include nontrivial skin matrices and fractional bone-index inputs.
The interpreter now handles relative constant addressing, `frc` and `mova`.

```text
python formats/hgp/lsw1/tools/check_face_vertex_program.py path/to/private-shader-inventory path/to/new-face-report.json
```

The research renderer accepts `--face-target 5 --face-weight 0.5` for a frozen,
manually chosen target pose. Weight must be between zero and one. Ordinary
active-face materials use the checked authored-normal path; other active-face
material effects are retained with an explicit reason. Three Qui-Gon examples
at weights zero, one-half and one were rendered and inspected in Blender 5.2.2
LTS with no fallback materials. The brows change position while the original
shading inputs remain intact. These examples are **manual poses, not decoded
game facial clips or a live animated shader implementation**.

The sampled Qui-Gon, Count Dooku and Yoda morph meshes have material depth mode
zero, which enables depth testing and writing in the checked native setter.
Most use source-alpha blending; one Yoda material uses opaque mode 10. This
evidence does not identify a separate depth-only facial pass. The lab's
transparent Blender surfaces do not yet reproduce native depth writes and draw
ordering, especially for transparent pixels. Shadow-map drawing and filtering,
facial occlusion order, native facial clip decoding and per-frame shading updates
remain unfinished; no later-game face compositor has been assumed to apply here.

## Shadow pass setup and live face previews

The shadow-resource checker also executes the original begin-pass segment
`0x3b62371..0x3b623fa` and end-pass routine `0x4f7500`. The nine setup calls save
the current targets, bind the shadow surfaces, save the color-write mask and
depth-write setting, disable color writes and enable depth writes. The depth
surface comes from the active light's configuration. This is not a color
silhouette pass. Ninety-six restoration cases check disabled/inactive paths,
invalid light indices, null/saved surfaces and different saved write states.
The original code restores the targets and write states and clears its active
shadow flag. Graphics calls and surface release remain intercepted: these checks
do not draw caster geometry or validate GPU depth samples.

The research renderer now accepts `--face-target 5 --face-preview-animation`.
It saves a playable scene with target weights zero, one and zero at frames 1,
9 and 17, and renders five example frames. The camera includes all 17 frames.
Ordinary face materials retain their authored normals as their vertices move,
consistent with the checked active-face vertex program. This mode requires a
fixed body pose and refuses unsupported material paths; it cannot be combined
with body ANI playback. Reflection and bump inputs on moving faces still need
their own live updates.

Qui-Gon and Count Dooku examples were rendered in Blender 5.2.2 LTS with no
fallback materials. Dooku still has visible artifacts around the eyes and mouth,
including at zero target weight; successful playback is not a facial rendering
fix. A saved-scene regression reopens each scene and checks
target values, actual vertex movement, return to Basis, unchanged topology and
unchanged authored shading vectors:

```text
blender --background --factory-startup --python-exit-code 1 --python formats/hgp/lsw1/tests/check_face_shader_playback_blender.py -- path/to/shader-experiment.blend 5 path/to/new-report.json
```

These are manually keyed native targets, **not imported game facial clips**.
Native facial depth ordering and actual shadow-map rendering remain unfinished.
The installed addon's materials and playback behavior have not changed.

## Queued alpha passes: correction to the depth interpretation

The general material setter temporarily disables alpha testing, but the queued
draw routine at `0x03B472FA` subsequently calls `0x00521610` before drawing and,
for eligible materials, `0x00521720` before a complementary draw. The native
material checker now exercises both helpers across 96 combinations of alpha
comparison, reference and secondary-pass mode. All comparisons passed.

Material bits 20–22 select the alpha comparison; bits 23–30 supply a reference
that the helper doubles. The second helper uses the complementary comparison.
Material word `+0x44` bits 0–1 control its write states: mode 0 disables color
and depth writes; mode 1 disables depth writes; mode 2 disables color writes
and enables depth writes; mode 3 writes RGB and disables depth writes. The draw
dispatcher restores the saved color/depth write states afterward. Opaque blend
mode 10 follows a separate single-draw branch.

The sampled Qui-Gon, Dooku and Yoda facial materials use alpha mode 5, reference
250 and secondary mode 1. Thus the earlier general-setter observation does not
mean every translucent facial pixel writes depth. The lab still lacks this
ordered two-pass rendering. These state checks are not GPU-rendering validation.

Dooku's decoded 128-by-128 facial texture itself contains the unusual hooked eye
shapes seen in the preview. That rules out attributing them solely to animation
binding; the intended final appearance still needs a matched native game frame.
Qui-Gon's original Walk ANI frame 8 was rendered and inspected with the existing
reviewed binding and no manually keyed facial targets. This is decoded body
motion under the lab's declared lighting, not proof of native facial playback.

The reusable `alpha_passes.py` reference now emits those two helper state lists;
the native checker compares them against 96 original-code executions. Its
restricted ordered-fragment experiment demonstrates low-alpha color blending
without depth writes, invisible depth writes in secondary mode 2, and RGB-only
writes in mode 3. Five asset-free tests include complementary comparisons over
all 256 alpha inputs. This is a per-fragment reference, not an implemented
Blender depth compositor: draw order, rasterized depth and quantized alpha are
explicit inputs. Out-of-range doubled alpha references are refused by that
experiment because device behavior has not been established.

For decoded facial frames rather than manual shape-key examples, use
the new [BSA preview workflow](FACE_PLAYBACK.md). It retains ordinary authored
normals on a fixed body; native depth ordering and shadows remain unfinished.
