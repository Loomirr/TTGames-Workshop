# Extraction and editing workflow

The goal is an asset-root workflow: select your game files, import a character
or cutscene, inspect/edit it, and write supported edits to a new native file.
The current public tools do **not** yet implement that whole chain. Start with
LMSH1 PC NXG and LB3 PC DX11; extensions alone do not identify a layout.

## Dependency audit

| Operation | Public implementation | Remaining dependency or limitation |
| --- | --- | --- |
| CU3 hierarchy, actor names, supported ANI-D motion and visibility | `formats/cu3/Addon/io_scene_lego_cu3/{cu3,cinematic}.py` | Unsupported descriptors fail; DCSV ANI-E playback remains disabled |
| Native character skeleton | `formats/cu3/Addon/io_scene_lego_cu3/skeleton.py` | Observed HGOL v10/v16 only; this is not a mesh reader |
| Face target data and curves | `formats/cu3/Addon/io_scene_lego_cu3/morph.py` | Part/vertex metadata still comes from companion extraction; numeric target IDs retained |
| Material depth flags | `formats/cu3/Addon/io_scene_lego_cu3/material_flags.py` | Needs verified material offsets; does not discover complete material records |
| Geometry, stream offsets and skin palettes | `native_mesh.py`, `native_display.py`, `native_model_blender.py` | Development source; observed MESH 169/175 and DISP 18/21/23/32; visual correctness remains under investigation |
| Character definitions and texture inventories | `definitions.py`, `native_materials.py`, `texture_store.py`, `costume_materials.py` | Observed CD/UMTL/TXTS layouts; shared slots and full layered shaders remain incomplete |
| Face GHG target writing | `face_edit.py`, `face_edit_blender.py`, `face_edit_ui.py` | Verified companions; existing Basis/topology/IDs and supported encoding only; edited files need game tests |
| Longer actor/object names and character-family replacement | CU3 CLI/GUI and relocation writer | Reparse + unchanged animation-byte checks; one LB3 replacement confirmed in-game |
| Cutscene assembly | Development `scene_assembly.py` plus private inspection scenes | Public mode assembles supported actors/cameras only; private scenes also have selected environments/audio, with substantial fidelity issues |
| Live viewing of those scenes | `face_live.py`, `playback_ui.py` | Camera-dependent mask approximation, not exact TT depth-only rendering |
| Original LSW1 models | `formats/hgp/lsw1/` | Independent 2005 PC reader, not evidence for NXG/DX11 layouts |
| LIJ1 prototype and 3DS textures | Their format folders | Separate platform/layout gates; no shared byte-order assumption |

The standalone readers/writers should remain usable without Blender. Blender
operators handle scene construction, controls and display. No public tool
requires a particular person's folders, a character-specific private project,
an AI runtime, or a bundled external extractor.

## Next extraction milestone

The first two steps below now have development readers and 31 local geometry
comparisons. Definition/material assembly is being checked in Blender; the
visual problems in the previews still prevent calling the workflow complete.

1. Discover bounded native part tables and vertex/index stream records directly
   from supported GHG versions, independently of legacy logs.
2. Keep geometry, descriptor and index byte orders separate. Validate stride,
   ranges, per-stream offsets, draw ranges, palettes and weight indices.
3. Import one complete character directly from GHG and compare source counts,
   geometry, skinning and highest-detail/display selection against the existing
   verified companion. Include its complete face/attachment context.
4. Add material/texture discovery and several unrelated characters before
   making asset-root cutscene assembly the default.

Expose a shared result with game/layout, source hashes/offsets, native part and
material IDs, bones/rest data, texture references and explicit missing or
unsupported dependencies. Preserve native data; do not silently substitute a
similar character, another game's reader or a guessed skeleton.

## Editing milestones

Face editing currently changes existing target coordinates only. New Basis,
topology, targets or unsupported RLE storage require separate verified writers.
Cutscene replacement remains independent of face editing and animation
retargeting. A new animation writer needs an unchanged no-op first, then
decoded-pose comparisons and an explicit game test; Blender playback alone is
not evidence that an exported native animation will work.

Preview controls, viewport modifiers and timeline sampling do not become game
animation data. Original root movement, instance visibility, native target IDs,
rest transforms, bone order and attachments must survive extraction. Gameplay
events and inferred loop labels should not be invented.

## Verification and packaging

Use source/binary, Blender, visual and game checks as separate categories.
Keep game files, scenes, audio, previews and private manifests under ignored
`local/`. Packages contain our source-built tools and permitted dependencies
only. Commit/push when requested; there are no scheduled checks.
