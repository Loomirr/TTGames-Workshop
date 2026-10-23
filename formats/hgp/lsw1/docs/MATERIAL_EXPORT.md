# Recolor an LSW1 character and save an HGP copy

This source-tree tool changes existing native material colors in **LEGO Star
Wars 1, PC**. It is a first step toward character export, not a Blender model
exporter. It does not add character slots, bones, meshes, hair or textures.

## Try it

Use Python 3.10 or newer from the repository folder:

```text
python formats/hgp/lsw1/tools/material_export.py inspect path/to/Character.hgp
```

The output lists zero-based material IDs, their RGB values and a source SHA-256
fingerprint. Choose the material you want to recolor, then use that fingerprint:

```text
python formats/hgp/lsw1/tools/material_export.py recolor path/to/Character.hgp --source-sha256 HASH_FROM_INSPECT --material 0 --rgb 0.125 0.75 0.25 --output path/to/Character-edited.hgp
```

Choose a new output filename. Existing files are never overwritten. Import the
edited copy into Blender to check which surface changed. Material 0 is only an
example: a material can be shared across multiple parts and detail layers.

RGB values are the native palette values from 0 to 1, **not Blender's linear
color values**. Texture colors still multiply the material color; this does not
repaint a texture or change its alpha. Shader flags, depth behavior, auxiliary
materials and texture links remain untouched.

## What has been checked?

On 2026-10-23, 157 local original PC HGP files passed:

- Reading the observed contiguous material block layout.
- Writing unchanged colors with byte-identical output.
- Recoloring material 0 and reading the expected RGB values back.
- Comparing every decoded layer, mesh, skeleton and embedded texture unchanged.
- Checking that every byte outside the selected 12-byte RGB field stayed equal.

A separate Qui-Gon Jinn example recolored material 2 to green. Its exported HGP
was imported and rendered in Blender 5.2.2 LTS with the research shader renderer.
The inspected image shows green clothing with the original head and hair; only
four bytes differed from the original HGP. This is a rendered export check, not
proof of native game shading or gameplay behavior.

Four asset-free tests cover unchanged output, exact field edits, wrong source
fingerprints, invalid colors/IDs, malformed material tables and existing-output
protection:

```text
python formats/hgp/lsw1/tests/check_material_export.py
```

The writer accepts the specific contiguous 0xb4-byte material record layout
observed in those originals. It rejects other layouts; it does not establish
that an arbitrary file with a matching header is a valid complete model.
**In-game export validation remains pending.** Keep the source and edited copy
separate when testing. No installed game files are changed by this tool.

## Next steps toward new characters

Part replacement needs a model writer that can rebuild geometry, material and
texture references, bone palettes, facial targets and every affected layer.
Added bones also need verified animation binding. Registering a new selectable
character is a separate definition/slot task. These remain unfinished; a
successful recolor does not prove those workflows.

See [character editing](../../../../docs/CHARACTER_EDITING.md) for the other
games' export limits and [shader research](SHADERS.md) for preview differences.
