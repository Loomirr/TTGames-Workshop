# LMSH1 reflection-only cubemap materials

Some LMSH1 materials declare a single texture, in slot 8, with `reflection` 1 and
no UV pair enabled. Hulkbuster's back hatch (`LEGO_GoldBlowup:GoldShiny_Shader`)
is one; the shared gold brick base (`LEGO_GoldBlowup:LEGO_Base`) and magnetic or
bronze bases are others. Previously they had no colour source and rendered white.
They now get that texture as a reflection lookup: the cubemap is resampled into
one equirectangular image and sampled with Blender's reflection vector, driving
the material's base colour. This is a labelled preview approximation
(`tt_reflection_cubemap`), not the native shader.

The binding requires mesh version 169, material table 172/174/176/177,
`reflection` 1, a texture in slot 8 and no texture in any other slot, and the
texture must be a six-face legacy DDS cubemap. Materials that combine slot 8 with
diffuse or normal textures are not bound, because how the game mixes them is not
established.

## Evidence

A read-only survey of every installed LMSH1 `.ghg`/`.gsc` material that uses
shader type 17 or a slot-8 texture:

- Every slot-8 texture whose payload was available is a six-face DDS cubemap:
  `mordorgold_cubemap`, `goldhdr_cubemap`, `bronze_cubemap`, `magnowalk_cubemap`,
  `legoice_cubemap`, `generic_blurred_cubemap`, `bluesky_c00_cubemap` and others.
- Every material with a slot-8 texture declares `reflection` 1 (about 700 uses).
- Slot 8 is the only texture in 87 + 5 + 4 + 4 + 4 uses across tables 172-177,
  for example `LEGO_GoldBlowup:LEGO_Base`, `LEGO_Magnetic:LEGO_Base`,
  `LEGO_GoldBrick1:LEGO_Base` and `LEGO_Ice:LEGO_Underside_2x10P_Cull`.

With no enabled UV pair, such a texture can only be addressed by direction.
Faces are read in D3D order (+X, -X, +Y, -Y, +Z, -Z) and mapped with the
importer's game-to-Blender rotation (+90 degrees about X). That orientation is a
convention, not a measured result; on the blurred gold cubemaps a mirrored or
rotated face would barely show.

## Checks

- `formats/cu3/scripts/test_reflection_cubemap.py`: the binding gate (only slot 8,
  reflection flag, table/mesh pairs, no combining with other textures) and the
  resampler's layout and axis convention on synthetic one-colour faces.
- Existing material tests still pass; `tools/check_repository.py` and
  `tools/check_docs.py` pass.
- Blender 5.2.2, original files, locally built Character 0.5.19 against the
  committed one: Hulkbuster's back hatch changes from white to a reflective
  gold; front, back and side renders were inspected. Other parts are unchanged.

Not established: the native blend, intensity, Fresnel or roughness, the face
orientation, and materials that combine the cubemap with other textures.
Distributable ZIPs were not rebuilt.
