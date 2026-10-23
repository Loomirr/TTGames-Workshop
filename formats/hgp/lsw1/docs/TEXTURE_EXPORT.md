# Replace an existing LSW1 texture

This source-tree tool extracts or replaces an embedded DDS in an **LSW1 PC
HGP**. It supports repainting existing textures without rebuilding the model.
It does not add texture slots, resize textures or encode PNGs into DDS files.

## Extract, edit and put it back

From the repository folder, using Python 3.10 or newer:

```text
python formats/hgp/lsw1/tools/texture_export.py inspect Character.hgp
python formats/hgp/lsw1/tools/texture_export.py extract Character.hgp --texture 0 --output face.dds
python formats/hgp/lsw1/tools/texture_export.py replace Character.hgp --source-sha256 HASH_FROM_INSPECT --texture 0 --dds face-edited.dds --output Character-edited.hgp
```

Choose the texture ID from `inspect`. Edit the extracted DDS with an editor
that preserves its header, format, dimensions and mip count. The first 128 DDS
bytes must match exactly; some editors rewrite otherwise harmless fields, which
this first writer deliberately refuses. Supported layouts are 2D DXT1, DXT3 and
DXT5 with all declared mip data. Every output must be a new file.

LSW1 stores padding after each DDS and after the texture allocation. Extraction
omits it; replacement preserves it in the HGP. UVs, alpha/depth flags, rigs,
materials and facial targets remain untouched. A donor texture's artwork will
not automatically fit another model's UVs.

## Evidence and limits

On 2026-10-23, inspection passed on 157 local originals: 153 had textures and
four had empty texture tables. All **1,281 DDS images** could be extracted and
replaced unchanged with byte-identical HGP output. A different same-header AAT
texture was written back, decoded and rendered in Blender 5.2.2 LTS. Every byte
outside that DDS, including padding, stayed equal; all decoded layers, bones
and materials were unchanged.

Five asset-free tests cover malformed tables, wrong fingerprints, payload/mip
sizes, incompatible headers, padding and byte preservation:

```text
python formats/hgp/lsw1/tests/check_texture_export.py
```

**In-game validation remains pending.** The installed addon has no texture export
button yet. See [material recoloring](MATERIAL_EXPORT.md) for palette edits and
[character editing](../../../../docs/CHARACTER_EDITING.md) for wider export limits.
