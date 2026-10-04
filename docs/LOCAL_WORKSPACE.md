# Local workspace

Use ignored `local/` for game inputs, extracted assets, experiments and preview
scenes. A fresh clone includes the public tools and documentation, not these
private files. Each tool accepts user-supplied paths; this layout is optional.

| Local folder | Purpose |
| --- | --- |
| `research/cu3/` | Cutscene, facial target and NXG/DX11 investigations |
| `research/hgp/lsw1/` | Original 2005 PC HGP investigation |
| `research/an4/lmsh1/` | Original Marvel animation investigation |
| `research/nu20/lij1-xbox360/` | Xbox 360 prototype texture investigation |
| `previews/` | Viewing copies, renders and character galleries |
| `validation/` | Format, animation, material and package verification results |
| `private-projects/` | Asset-specific experiments and conversions |
| `build-cache/` | Local compiler and dependency caches |

Keep games and platforms separate within each format area. Preserve original
inputs and validated scenes; write edits and new preview passes to separate
outputs. Keep external research dependencies private and out of downloadable
builds. Never stage extracted models, textures, audio or Blender scenes.

Public changes belong in top-level `formats/`, `games/`, `tools/` and `docs/`.
Reviewed packages made from the project's source belong in `builds/`.
Historical checkouts under `local/` are reference copies, not the public source.

On a research workstation, `local/README.md` and `local/PATHS.json` record its
private project locations. Relocation inventories and integrity checks stay
under ignored `.migration/`. These records are not required to use the tools
and are not included in Git.
