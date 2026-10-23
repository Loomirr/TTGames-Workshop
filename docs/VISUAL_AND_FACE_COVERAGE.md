# Shader and facial accuracy by game

The target for every game is **1:1 recreation of its shader behavior, faces and
facial animation**, plus editing and export back to its native formats. These
are required parts of the [era completion plan](ERA_DEVELOPMENT.md), not optional
polish after model import. Development remains Early Classic, NXG, DX11, NTT,
then Classic. Fortnite remains deferred.

## What each game must pass

| Completion item | Required work and evidence |
| --- | --- |
| **Shader matching** | Read the actual shader/material variants, parameters, texture and UV bindings, color conversions, vertex colors, normals and tangents. Reproduce applicable lighting, reflections, transparency, alpha cutouts, depth/stencil masks, draw order, culling, emissive effects and animated material parameters. Compare rendered output against the game across material variants, viewing angles, lighting conditions and detail levels. |
| **Face reconstruction** | Recover face geometry or printed/texture-based faces, Basis and expression targets, IDs, normals, UVs, materials, masks, attachment transforms and visibility rules. Check eyes, pupils, highlights, brows, mouth, teeth and other parts the game actually uses, including interactions with heads, hair and hats. Verify each detail level's part membership and equivalent expressions. |
| **Facial animation** | Decode and bind the game's actual facial controls, whether shapes, bones, textures or another mechanism. Verify blinks, eye movement, expressions and speech where present; interpolation, timing, loops, transitions and synchronization with body animation, audio and cutscenes. Distinguish a valid constant expression from missing or unmatched tracks. Compare both decoded controls and rendered frames. |
| **Native editing/export** | Round-trip supported material and facial data without losing IDs, unknown fields, extra keys, masks, references or detail levels. Verify edited expressions, facial clips and material settings in-game, including transitions and unrelated actions. New targets, clips or materials require the corresponding native tables and definition links; they are separate tests from editing existing entries. |

Check minifigures, bigfigures, creatures, unusual heads and costume variants
where the game contains them. Test gameplay and cutscene paths separately.
Mark a feature **not applicable** only after documenting that the particular
game/platform/release does not use it. Missing samples mean **unverified**.

## What “1:1” means here

Shader equivalence and a matching final frame are separate checks. First compare
the material's inputs and render behavior. Then compare complete frames with
matched geometry, camera, pose, textures, lights, environment, resolution and
color/post-processing settings. Record the game build, rendering backend,
settings, compared frames, image differences and any accepted numerical tolerance.
An unexplained visible difference keeps the relevant item open.

A Principled BSDF approximation, a Solid viewport screenshot or matching shape
weights alone cannot establish 1:1 rendering. If Blender's renderer cannot
represent a native pass exactly, document that limitation and investigate a
custom shader/pass or rendering path. Keep an approximation clearly labelled;
do not silently count it as exact support. Preserve native data separately from
Blender viewing helpers so an approximation does not become an export change.

## Per-game completion list

**Open** means the full requirement above has not been demonstrated for that
game. It includes games with working partial features; it does not mean no work
exists. These are completion targets, not a replacement for the
[current import/export support table](../README.md#game-and-file-support).
No row currently establishes complete 1:1 coverage.

Split each row into exact platform, release, file layout and shader variants as
samples are inventoried. Keep separate evidence for each of the four columns.
Every new game added to the project must receive these same completion items.

| Game / platform scope | Shader matching | Face reconstruction | Facial animation | Native facial/material round trip |
| --- | --- | --- | --- | --- |
| LEGO Star Wars 1, PC | Open | Open | Open | Open |
| LEGO Star Wars II, PC | Open | Open | Open | Open |
| LEGO Batman 2, PC | Open | Open | Open | Open |
| LEGO Marvel Super Heroes, PC | Open | Open | Open | Open |
| LEGO The Hobbit, PC | Open | Open | Open | Open |
| LEGO Batman 3, PC | Open | Open | Open | Open |
| LEGO Marvel's Avengers, PC | Open | Open | Open | Open |
| LEGO Star Wars: The Force Awakens, PC | Open | Open | Open | Open |
| LEGO DC Super-Villains, PC | Open | Open | Open | Open |
| LEGO Marvel Super Heroes 2, PC | Open | Open | Open | Open |
| LEGO The Lord of the Rings, PC | Open | Open | Open | Open |
| The LEGO Movie Videogame, PC | Open | Open | Open | Open |
| LEGO Star Wars III, PC | Open | Open | Open | Open |
| LEGO Jurassic World, PC | Open | Open | Open | Open |
| The LEGO Ninjago Movie Videogame, platform/release inventory pending | Open | Open | Open | Open |
| LEGO Dimensions, per-platform inventory pending | Open | Open | Open | Open |
| LEGO Star Wars: The Skywalker Saga, PC | Open | Open | Open | Open |
| LEGO Star Wars: The Complete Saga, PC | Open | Open | Open | Open |
| LEGO Batman 1, PC | Open | Open | Open | Open |
| LEGO Indiana Jones 1, PC | Open | Open | Open | Open |
| LEGO Indiana Jones 1, Xbox 360 prototype | Open | Open | Open | Open |
| LEGO Marvel Super Heroes: Universe in Peril, Nintendo 3DS | Open | Open | Open | Open |
| LEGO Fortnite, separate/deferred | Open | Open | Open | Open |

Console, handheld, prototype and patched versions do not inherit a PC pass.
This list covers the project's currently listed games; other titles and releases
must be added during the full era inventories rather than assumed equivalent.

## Existing evidence to build on

- [LSW1 material, normal and face-alpha work](../formats/hgp/lsw1/README.md) and
  [ANI/BSA record preservation](../formats/hgp/lsw1/docs/ANIMATION_RECORDS.md).
  [Native facial shape import](../formats/hgp/lsw1/docs/FACE_TARGETS.md) now covers
  the observed position-target layout. Record edits and manual poses do not yet
  establish facial clip binding or playback.
  [Original PC shader analysis](../formats/hgp/lsw1/docs/SHADERS.md) now inventories
  197 compiled program entries and verifies ordinary additive blending; the pod
  backing fix has numerical Blender render checks. Full shader matching is open.
- [LSW2 HGP shapes, animation and experimental export](../formats/hgp/lsw2/README.md).
  Full original-file retesting and in-game export checks remain outstanding locally.
- [LB2 facial research](LB2_FACES.md) and
  [shared shader/face-preview improvements and approximations](SHADING_AND_QUALITY.md).
- [Selected LMSH1, LB3, Hobbit and Avengers facial playback checks](FACE_PLAYBACK_2026-10-21.md).
  These compare target values and evaluated movement; they do not certify shaders
  or facial export.

For every future pass, link the implementation and tests, identify the exact
original samples privately, retain rendered comparisons, and record in-game
results separately. Partial evidence advances a task without closing the whole row.
