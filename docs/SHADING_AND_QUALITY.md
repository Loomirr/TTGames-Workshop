# Shading and mesh quality

Character **0.5.5** and CU3 **0.1.14** share the following corrections.
These are import and Blender preview improvements; they do not establish
exact game lighting or complete native shader reconstruction.

## Authored normals in facial previews

The live face clipping helper subdivides and removes hidden facial triangles.
Those operations were discarding custom corner normals and replacing them
with geometric normals. The helper now captures evaluated corner normals
before subdivision and restores them after clipping. Facial depth bias also
preserves those normals. The captured values include skin deformation.

This requires Blender's `GeometryNodeSetMeshNormal` node. It was verified in
Blender 5.2.2. Older Blender versions without that node retain the previous
normal approximation; successful addon installation alone does not verify
that this correction is available. Create a fresh preview to rebuild helpers
in an existing project. Source vertices, Basis, shape targets and bind data
are not changed.

Live clipping still approximates native depth-only rendering. Polygonal mask
edges can remain visible, even at the highest clipping setting. Use the
composed face preview for closer inspection. Exact shader lighting, all facial
expression timing and whole-roster fidelity remain incomplete.

## LMSH1 head printing

On the verified **MESH 169 / UMTL 176** shared minifigure layout, CD base-head
textures use UV0 for `HEAD_FRONT_GAME` role 1 and `HEAD_BACK_GAME` role 2.
The previously selected UV1 maps the cropped shared atlas and distorted these
textures. Side/rear comparisons reproduce the problem on Axel Alonso and Blade:
Axel's rear hair becomes a continuous print and Blade's rear tattoo appears
instead of being displaced onto the neck. This rule uses layout and material
role, not character names. Normal-map coordinates and later-game head mappings
retain their independently decoded bindings. Reimport to apply it.

Base-head printing is separate from animated facial details and depth masks.
Correcting the former does not resolve every facial shading or expression issue.

## N sidebar settings

Expand **TT Character > Import and preview settings**.

- **Mesh detail** defaults to **Highest detail**. File imports and the character
  browser use the nearest verified native LOD for the body and attachments.
  **Authored binding** retains the reader's initial clip for inspection.
  Costume/layer selection remains independent; alternate costumes are not LODs.
  Reimport after changing mesh, costume or attachment options.
- **Face clipping quality** controls live preview subdivision, defaulting to 4.
  Increasing it costs memory and playback time; it does not repair native meshes.
- **Use normal maps** and **Normal strength** affect viewing copies. Strength
  multiplies each imported normal node's original strength; 1 preserves it.
  Values such as 0.3 or 0.4 are useful comparisons requested in the issue, not
  verified game shader values. Linked procedural strengths remain intact.
- **Lit materials / Base color** compares lit surfaces with unlit base color, preserving alpha.
- **Color display**, **Exposure** and **Render samples** control the preview.
  Standard display, zero exposure and gamma 1 are defaults. Material Preview
  now uses the preview scene's lights and world instead of Blender's studio HDRI.

Create a character preview, adjust settings in that scene, then press
**Update preview settings**. The source scene and its material graphs remain
intact. These controls do not write native material changes on export. Raw
imports still need a preview helper for native depth-mask faces.

## Checks and limits

Synthetic Blender checks verify normal preservation before and after skinning,
unchanged source geometry, independent preview materials, reversible shader
links, strength restoration, scene lighting and highest-detail defaults.
Selected original-file checks cover 16 characters across LMSH1, LB3, The Hobbit
and Avengers, plus Blade for the reported head mapping. Unchanged native vertex
exports preserve the source bytes. A separate native LOD audit covers nine
observed tables across those four profiles. Unknown layouts are rejected;
there is no triangle-count guess or global mesh welding.

These checks are not in-game validation or certification of every character.
CU3 shares the normal-preservation and head-material fixes, but its stage,
lighting and scene reconstruction limits remain unchanged. TFA/DCSV remain
reference-inspection profiles. LEGO Fortnite material accuracy was not part
of this TT pass.

To run the portable viewing-copy regression after extracting the character ZIP:

```text
blender --background --factory-startup --python formats/character/check_preview_settings_blender.py -- --addon-directory <folder-containing-io_scene_tt_character>
```
