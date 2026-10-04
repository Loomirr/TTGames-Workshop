# Native colors and Blender

The HGP reader stores the original diffuse RGB floats at material offset
`0x54`. They are not estimated from a texture or recolored by character name.

In the local original-PC sample, 4,187 of 4,314 RGB channel values on used
materials fall on byte-normalized palette values within rounding tolerance.
Solid brown materials, for example, store `(0.4, 0.2, 0)`, or `(102, 51, 0)`
in display RGB, close to the brown pixels in the companion DDS printing.
This is the observed palette/texture convention used by this importer.

The old importer assigned those floats directly to Blender's material sockets.
Blender interprets those inputs in scene-linear space, whereas its sRGB image
nodes decode texture colors first. A raw value of 0.4 therefore displayed near
0.665 in a neutral Standard preview, instead of near 0.4. Brown plastic could
look yellow and skin or green parts looked much paler beside the printing.

0.1.3 converts constant RGB channels with the sRGB transfer function before
assigning Base Color and the material's viewport diffuse color. Original
texture files/pixels are unchanged, and their image role is explicitly sRGB.
Normal-map image copies remain Non-Color. Alpha is not gamma-converted.

Material metadata retains `lsw1_diffuse_srgb`, `lsw1_diffuse_linear` and
`lsw1_colour_version` for inspection. Vertex colors are not guessed as plastic
colors: the inspected buffers include constant gray or black values that are
not a safe replacement for the native material palette.

## Checking colors

Use Material Preview or Rendered mode. Solid mode's material color is a single
swatch and cannot show the printing. For a neutral comparison with image RGB,
use Standard view transform, no look, exposure 0 and gamma 1; lights and
reflections still change the final rendered appearance. The importer does not
change an existing scene's color-management settings.

AgX and other view transforms are legitimate scene choices, but their rendered
appearance is not a direct RGB screenshot comparison. Original game lighting,
specular effects and every material effect are still approximate.

Re-import with 0.1.3 to create corrected materials. Preserve edited scenes as
separate copies; this version does not rewrite existing user materials.

## Validation

The Blender test checked 139 readable original PC HGPs and 1,827 materials:
521 colored untextured records, 1,203 textured records, 314 alpha links and
139 normal-map links. It compares the material constants with Blender's native
`Color.from_srgb_to_scene_linear()` conversion and verifies actual node/image
roles. Ten headers remain unsupported. This is not a new universal header reader.

The private visual comparison uses the same meshes, textures, native rigs,
normal maps, camera and lights for the previous and corrected color behavior.
It is a Blender comparison, not frame-matched in-game validation.

Run the source check with your own inputs and a new report path:

```sh
blender -b --factory-startup --python tests/check_colours_blender.py -- path/to/hgps path/to/new-report.json
```

Blender's [color-management manual](https://docs.blender.org/manual/en/4.2/render/color_management.html)
and [developer color-management notes](https://developer.blender.org/docs/features/render_pipeline/color_management/)
describe the distinction between encoded byte images and scene-linear values.
