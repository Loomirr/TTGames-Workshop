# LEGO Star Wars: The Video Game (2005) — original PC release

Use the [HGP Blender importer](../../formats/hgp/lsw1/README.md), version 0.1.10.
It imports supported native meshes, skeletons, vertex weights, original normals,
embedded textures, corrected native palette colors, face alpha and linked normal maps.
Version 0.1.7 also imports [native facial shape targets](../../formats/hgp/lsw1/docs/FACE_TARGETS.md)
for manual Blender poses. Game facial clips and native face export remain open.
Version 0.1.8 adds [exact character TXT layer lists](../../formats/hgp/lsw1/docs/CHARACTER_LAYERS.md):
506 valid original sets passed Blender checks; 14 invalid original sets were
reported separately.

This reader is specific to LSW1. LSW2 and The Complete Saga are different layouts
and are not substitutes for LSW1 research samples.

LSW1 PC is the active starting point of the [era plan](../../docs/ERA_DEVELOPMENT.md).
The model reader is only one part: ANI/BSA animation, CUT scenes, definitions,
levels and native editing/export still require work. The plan records the full
installer inventory and current sample coverage.

The [ANI/BSA record tools](../../formats/hgp/lsw1/docs/ANIMATION_RECORDS.md)
now inspect original animation records and edit an existing channel while
preserving time records, lookup tables and unknown bytes. Checks accepted
870 ANI and 617 BSA files; one historical ANI with a non-finite value remains
rejected. This is source-level editing research. Separate preview tools now bake explicitly
reviewed ANI/HGP pairs into Blender actions; examples include Clone, Qui-Gon,
Yoda, Gonk, Clone Walker and R2-D2. Parent-scale compensation now preserves the
sampled Gonk and Clone Walker poses, with saved/reopened Blender checks.
Automatic clip ownership and facial playback remain open.
Scalar evaluation also matched 340,724 samples against the isolated native
routine within the documented tolerance. Binding clips to rigs and faces remains
unfinished.

The [LSW1/TCS script comparison](../tcs/scripting/LEGACY_COMPARISON.md) separately
checks original PC command bindings and inherited script text. It includes
native lookup and isolated handler emulation, not gameplay validation or a
complete LSW1 scripting guide.

## Shader and facial completion

The [shader research notes](../../formats/hgp/lsw1/docs/SHADERS.md) document
compiled programs recovered from the original executable and the verified
additive blend-state branch. Version 0.1.9 fixes the opaque backing behind pod
energy beams in Blender; it does not yet reproduce the full game shaders.
The research inventory now connects 68 effect IDs to 88 candidate blob locations
(82 distinct contents).
Original-code checks verify 6,144 ordinary/specular/bump/reflection selector cases, 12 material-color
uploads, six specular-strength uploads, 18 reflection-parameter uploads and six view-position uploads. Runtime pass selection, vertex preparation and frame-matched lighting
remain open; these research additions do not change the installed preview.
A separate Blender shader experiment now reproduces the ordinary, texture-specular, bump and reflection pixel lighting
equations with explicitly chosen inputs. It passed 118 numerical material cases and 36 cube-orientation cases
and produced original-model comparisons. It remains a research scene generator;
native runtime inputs and full visual fidelity have not been established.
An explicit advanced-lighting-off comparison now covers material 145 on R2-D2
and Gonk. The bump-only comparison now covers Maul and Dooku, with an explicit
tangent-generation assumption. Advanced plastic and combined bump/reflection
comparisons now use an explicitly selected original cubemap. Native tangent
generation, runtime lighting, facial passes and frame-matched shading remain unfinished.

Version 0.1.10 adds a [reversible hand preview correction](../../formats/hgp/lsw1/docs/HAND_PREVIEW.md)
for six original Clone-family rigs. Full game animation binding remains open.

This edition must separately pass **1:1 shader matching, face reconstruction,
facial animation and native facial/material export**. These remain open goals;
see the [per-game checklist and required evidence](../../docs/VISUAL_AND_FACE_COVERAGE.md).
