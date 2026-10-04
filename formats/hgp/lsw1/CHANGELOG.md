# Changelog

## 0.1.3

- Convert native display RGB palette colors into scene-linear material inputs,
  correcting washed-out or shifted solid plastic beside the original textures.
- Explicitly retain sRGB base textures and separate Non-Color normal images.
- Preserve original and converted diffuse values as material metadata.
- Add a user-input Blender color/material-role check and color handling notes.
- Check 1,827 material records across 139 readable original PC HGP files.

## 0.1.2

- Recognize `TT1_Hi` and `TT1_MediumRes` as primary body detail layers, fixing incomplete automatic imports of Zam Wesell and Boss Nass.
- Allow optional accessory layers in the Python importer without duplicating shared geometry.
- Add a gallery builder with twelve additional characters and Young Anakin's separate hair layer.

## 0.1.1

- Decode native one-based auxiliary-material links and assign recognized normal maps automatically.
- Use Non-Color normal images while retaining separate base-colour colour-space roles.
- Preserve reflection-pass distinctions, native vertex normals and alpha-mode material connections.

## 0.1.0

- Initial original LSW1 PC character importer with native bones, weights, UVs and packed textures.
