# Extraction and editing workflow

The goal is a game-folder workflow: select your game files, import a character
or cutscene, inspect/edit it, and write supported edits to a new native file.
The current public tools do **not** yet implement that whole chain. Start with
LMSH1 PC NXG and LB3 PC DX11; extensions alone do not identify a layout.

## Dependency audit

| Operation | Public implementation | Remaining dependency or limitation |
| --- | --- | --- |
| Installed-game companion loading | `archive_assets.py`, `archive_v5.py`, `archive_compression.py` | Observed LB3 -6 and LMSH1 -5 DATs; requested actor, registry and stage companions cached outside the installation |
| CU3 hierarchy, actor names, supported ANI-D motion and visibility | `formats/cu3/Addon/io_scene_lego_cu3/{cu3,cinematic}.py` | Unsupported descriptors fail; DCSV ANI-E playback remains disabled |
| Native character skeleton | `formats/cu3/Addon/io_scene_lego_cu3/skeleton.py` | Observed HGOL v10/v16 only; this is not a mesh reader |
| Face target data and curves | `formats/cu3/Addon/io_scene_lego_cu3/morph.py` | Part/vertex metadata still comes from companion extraction; numeric target IDs retained |
| Material depth flags | `formats/cu3/Addon/io_scene_lego_cu3/material_flags.py` | Needs verified material offsets; does not discover complete material records |
| Geometry, stream offsets and skin palettes | `native_mesh.py`, `native_display.py`, `native_model_blender.py`, `native_layers.py` | Observed MESH 169/175 and DISP 18/21/23/32; CD layer-special selection; remaining layouts and visual correctness need work |
| Character definitions and texture inventories | `definitions.py`, `native_materials.py`, `texture_store.py`, `costume_materials.py` | Observed CD/UMTL/TXTS layouts; shared slots and full layered shaders remain incomplete |
| Face GHG target writing | `face_edit.py`, `face_edit_blender.py`, `face_edit_ui.py` | Verified companions; existing Basis/topology/IDs and supported encoding only; edited files need game tests |
| Longer actor/object names and character-family replacement | CU3 CLI/GUI and relocation writer | Reparse + unchanged animation-byte checks; one LB3 replacement confirmed in-game |
| Scene configuration | `scene_configuration.py`, `scene_inputs.py` | Exact primary/shared stage associations and simple root-resource replacements; other registry commands remain unapplied |
| Cutscene assembly | `scene_assembly.py` and the default Blender import mode | Supported actors, attachments, materials and cameras; full shaders, faces and game fidelity remain incomplete |
| Recovered static environments | `stage_geometry.py`, `stage_blender.py` | Verified static draw bindings and native matrices; named specials excluded; visibility/render controls approximate; nested scenes, props, source lighting, audio and VFX remain incomplete |
| Live viewing of those scenes | `face_live.py`, `playback_ui.py` | Camera-dependent mask approximation, not exact TT depth-only rendering |
| Original LSW1 models | `formats/hgp/lsw1/` | Independent 2005 PC reader, not evidence for NXG/DX11 layouts |
| LIJ1 prototype and 3DS textures | Their format folders | Separate platform/layout gates; no shared byte-order assumption |

The standalone readers/writers should remain usable without Blender. Blender
operators handle scene construction, controls and display. No public tool
requires a particular person's folders, a character-specific private project,
an AI runtime, or a bundled external extractor.

## Current import workflow

Select an extracted CU3 file in Blender, leave **Assemble available scene assets**
and **Detect from CU3** selected, and provide the installed LB3/LMSH1 folder or
an extracted asset tree. The addon keeps separate game-folder preferences and
builds a new scene plus a report of missing or unsupported systems. The CU3
file contains animation and references; its meshes and textures are separate
companions. Press Space in the prepared camera viewport to preview without F12.

**Recovered static environment (experimental)** is enabled by default. It
loads supported primary and shared GSC resources named by the selected
cutscene's registry entries. Disable it for actor-only inspection. Stage
geometry uses native matrices and material indices, but its visibility and
render passes remain approximate. The preview's inspection light does not
reconstruct source lighting. Exact, unchained character replacements from the
same configuration select root resources; other commands remain in the report.

Installed-game loading extracts only requested companions into an external
cache, with bounded decoding and cached-file hashes. Game archives stay
read-only. See [archive loading](../formats/cu3/docs/ARCHIVE_ASSETS.md).

## Next reconstruction milestones

1. Broaden verified native model/material layouts using unrelated cutscenes.
2. Verify static stage visibility/render controls, then resolve nested scene
   origins, rigid props and their visibility/animation.
3. Improve facial depth, layered shaders, shared textures and expression timing.
4. Decode source lighting, sound and effects, and compare actual shots with
   game playback. Data consistency and complete actor counts are not fidelity.

TFA and DCSV currently remain reference/research profiles. TFA's successful
archive and CU3 inventories, and its two private rig examples, do not establish
character mesh, camera or full-scene support.

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
