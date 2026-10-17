# LEGO Batman 2 PC: experimental character profile

Builds on the LB2 model readers in [LB2_GEOMETRY.md](LB2_GEOMETRY.md) (pull request #14). This adds an
experimental `LB2` character profile to the Character add-on, so an LB2 `.cd` can be imported from an installed
game folder or an extracted tree. As first written this was static import only; LB2's animation sets were added
later ([LB2_ANIMATION.md](LB2_ANIMATION.md)). CU3 cutscenes are still not decoded.

## What changed

- **`profiles.py`:** `LB2` = NXG renderer, `_NXG` models, MESH 48 for both `.ghg` and `.gsc`. MESH 46/47 and
  other versions are refused by the existing profile check.
- **Importer and add-on:** `LB2` is accepted by `import_character` and listed in the game menu, marked
  experimental.
- **`costume_uv_index`:** for MESH 48 the costume prints use UV pair 0. Every costume-role part of LB2's
  shared minifigure (`HEAD_FRONT_GAME`, `BODY_FRONT_GAME`, `LEFTARM_GAME`, ...) carries exactly one UV pair.
- **LB2 material prefix:** `uvSets` is an empty list instead of `None`. Same meaning (no verified UV pairs),
  but the existing material report expects a list.
- **Untextured LB2 materials** (faces, cowls, hair) use the source vertex colours doubled, as a labelled
  inspection approximation (`tt_lb2_vertex_colour_scale`). Doubling an sRGB value is about 2^2.2 in Blender's
  linear light; the colour attribute itself is unchanged. Evidence: the white details of `face_batman` and
  `face_joker` (teeth, occluders) peak at 127, never above; Batman's cowl is 16.
- **Embedded textures** (`texture_store.read_embedded_texture_store`): LB2 models have no `.nxg_textures`
  companion; a model's own textures (hats, helmets, props, big figures) live inside it. The `HGXT` list names
  each texture, and entries without a name have no image (LB2 starts most lists with three dummy lightmaps).
  The named entries' DDS images follow, contiguous and in list order. Each entry is 16 bytes, a u32 name length,
  the name and 4 bytes in `HGXT` 10; version 9 entries add 37 bytes after the first 16, starting with the
  image's width and height, and end with 14 bytes. The width and height must match the DDS header.
  `model_texture` uses this store for MESH 48, and the own-texture branch uses UV pair 0 there.
  - Over all LB2 models, 1,046 lists read (827 version 10, 219 version 9), with 17,903 images.
  - Refused: 16 level files whose water texture uses a DDS FourCC the existing reader rejects, and list
    versions 5-8 (MESH 46/47 models).

The textured roles need no new rules. The definitions' `Character Texture` roles bind through the existing
costume path: body front and back, arms, hands, hips, legs and head prints.

## Checks

- **All 213 minifigure definitions** under `chars/minifigs`, imported in one Blender 5.2.2 session from the
  extracted tree:
  - 198 import, with no material left unresolved.
  - 15 are refused by existing checks: 14 definitions in stream versions 18/22/23/24, and `super_test` (MESH 47).
  - 32 of the imported characters skip at least one attachment (35 skipped in all): 28 attachment definitions
    in stream version 23/24, 6 hats with MESH 47 or an older material table, and 1 missing female face
    resource.

- `formats/cu3/scripts/test_lb2_profile.py`: the profile accepts only MESH 48 `_NXG` models, and costume
  prints use UV pair 0.
- `formats/cu3/scripts/test_lb2_textures.py`: named `HGXT` 9/10 entries map to contiguous images in order,
  unnamed entries keep their index without an image, and version 9 sizes must match. A size mismatch, a gap
  between images, a missing image and list version 8 are refused.
- Blender 5.2.2, original files, locally built Character add-on: Batman, Joker, Robin and Superman import with
  correct print textures and colours (black cowl, green hair, white hands); Catwoman, Lex Luthor and Killer
  Croc likewise. Mad Hatter's hat takes its green, price-tagged texture from the hat model's embedded image. Installed-game import was checked
  for file lookup: the archive provider extracts `batman.cd`, `super_minifig_nxg.ghg` and `face_batman_nxg.ghg`
  from the game's `.DAT` files.
- **LMSH1 regression:** Vulture's import with this build matches the committed Character 0.5.19: identical
  parts, materials and report, and an identical render.
- `tools/check_repository.py` and `tools/check_docs.py` pass.

## Known gaps

- **Capes** lie flat behind the figure in the bind pose; LB2's clips now pose them ([LB2_ANIMATION.md](LB2_ANIMATION.md)).
- **Faces** show all expression layers, as a plain LMSH1 import does; the existing face previews apply.
- **Definitions** in stream versions 18-24 and **older models** (MESH 47, material tables 106-123) were
  added later: [LB2_OLDER_VERSIONS.md](LB2_OLDER_VERSIONS.md). Material tables 52-58 stay refused.
- **Not attempted:** cutscenes, facial animation, native shading, export back into LB2. (9-curve animation blocks
  play through the character importer: [LB2_ANIMATION.md](LB2_ANIMATION.md).)
