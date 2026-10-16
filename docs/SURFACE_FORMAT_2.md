# LMSH1 surface format 2: RGB normal maps

LMSH1 materials with `surfaceMapMethod` 1 and `surfaceMapFormat0` 2 now bind
texture slot 6 as an ordinary tangent-space normal map (X red, Y green, Z blue),
using UV selector pair 4, like the existing format 5 binding. The gate is
mesh version 169 with material tables 172, 174, 176 and 177, the only pairs
the LMSH1 character audit reports (467 definitions, 402 parser-ready). The
texture must be the embedded DXT1 image; anything else is refused and reported.
Format 0 remains unbound. Other games and pairs are unchanged.

## Evidence

A read-only survey of every installed LMSH1 `.ghg`/`.gsc` material with a
slot-6 surface map, decoding the referenced texture from its companion store:

| Surface format | Encoding | Channel means (R, G, B, A) | Texture names |
| --- | --- | --- | --- |
| 5 (already supported) | DXT5 | about (12-54, 126, 211-229, 125) | normals with X in alpha |
| 2 | DXT1, every sampled use | about (126-130, 127-131, 191-230, 255) | `*_nrm`, `*_norm`, `*_normal` only |
| 0 | mostly DXT1 | mixed | normals, but also `arms_template`, `lego_white`, `alpha.nut`, `handlegrip_diff` |

Outside the material-remap libraries, every format 2 slot-6 texture in the
survey is named as a normal map (hair, ropes, props, level surfaces), including
the skinned hairs `hair_mediumwavy_normal`, `hair_bushylong_normal`,
`hair_ponytaillong_normal`, `hair_longcurlymiddle_normal`,
`hair_elvenlongmale_normal` and `hair_bowlcut_normal`. Format 0 is not enabled
because its slot 6 also holds non-normal textures; the base minifig body, for
example, declares format 0 with `arms_template` there. Storm's hair
(`skinnedhair_storm`, UMTL 172) is format 0 with `stormhair_normal`, so it still
imports without a normal map.

Green orientation was checked rather than assumed. For a map derived from a
height field, the slopes implied by X and Y are consistent (near-zero curl) in
only one Y orientation. On 40 format 5 maps and 40 format 2 maps, the same
orientation was the consistent one in 38 and 36 of them. The existing format 5
path's green handling therefore applies unchanged; only X moves from alpha to red.

## Checks

- `formats/cu3/scripts/test_material_flags.py`: format 2 binds as RGB for the
  four gated tables; it is refused for other mesh/table pairs; format 0 stays
  unbound in tables 172/174; the existing format 5 cases are unchanged (41 tests).
- `tools/check_repository.py` and `tools/check_docs.py` pass.
- Blender 5.2.2, original files, a locally rebuilt Character 0.5.19 package
  compared with the committed one: Black Widow (`skinnedhair_mediumwavydarkorange`)
  and Sif (`skinnedhair_mediumwavy`) hair materials change from no normal binding
  to `RGB normal`; front, back and side renders were inspected and show the
  strand grooves. Geometry is untouched; only the material node graph changes.

Not established: in-game shader equivalence and native normal strength, other
games' use of format 2, and the meaning of format 0. Distributable ZIPs were
not rebuilt for this change.
