# Classic PC readers: LEGO Batman 1, Indiana Jones 1, Star Wars: The Complete Saga

Read-only Python readers and exporters for the 2007 to 2008 PC generation: `.DAT` archives, NU20 scenes and
models, AN3 animation, CU2 cutscenes, GIZ gizmo placement and the plain-text GIT puzzle logic.

Contributed by Gibby from [tt-oldera-tools](https://github.com/stryderjoe/tt-oldera-tools), which remains the
upstream; this folder is a snapshot of its commit `fae9794`. MIT licence, see [LICENSE](LICENSE). AI was used
for the code, research and testing.

**Builds investigated:** Steam PC releases only.

| Game | Steam app | Archive index version |
| --- | --- | --- |
| LEGO Batman: The Videogame | 21000 | -2 |
| LEGO Indiana Jones: The Original Adventures | 32330 | -2 |
| LEGO Star Wars: The Complete Saga | 32440 | -3 |

No other platform or edition was looked at. This is separate from the original 2005 LEGO Star Wars reader in
[formats/hgp/lsw1](../hgp/lsw1/README.md) and from the Xbox 360 prototype work in
[formats/nu20/lij1-xbox360](../nu20/lij1-xbox360/README.md); nothing here was tested on those files.

## Status

Decode and export only. **Nothing here writes game files, nothing was validated in game, and exported models
and clips were not judged by eye.** Counts are files that decode, over every such file of the three installs;
[docs/COVERAGE.md](docs/COVERAGE.md) says exactly what was checked.

| Tool | Reads | Batman 1 | Indiana Jones 1 | TCS |
| --- | --- | --- | --- | --- |
| `ttdat.py`, `lz2k.py`, `extract_game.py` | `.DAT` archives, LZ2K (own decompressor) | 10,645 entries listed | 9,465 of 9,465 extracted | 12,459 of 12,459 extracted |
| `nu20.py`, `gltf_export.py` | `.gsc` / `.ghg`: textures, meshes, materials, skeleton; glTF 2.0 | 939 of 940 | 1,015 of 1,015 | 1,477 of 1,477 |
| `an3.py`, `anim_export.py`, `skeleton_export.py` | `.an3` (tags `4INA`, `5INA`, `6INA`, `8INA`); skeleton and clips as glTF | 2,578 of 2,578 | 2,524 of 2,524 | 2,911 of 2,911 |
| `cu2.py` | `.cu2` cutscenes, versions 516 to 520: cuts, cameras, character tracks | 135 of 135 | 112 of 112 | 205 of 205 |
| `giz.py` | `.giz`: framing, pickup tables (versions 4, 5, 7), fixed-size records of some sections | 171 of 171 | 103 of 103 | 248 of 251 |
| `git_study.py`, `level_anatomy.py` | `.git` flow-box puzzle logic | yes | yes | runs, output not reviewed |

Version handling: `ttdat.py`, `cu2.py` and `giz.py` reject versions they have not been checked on. `nu20.py`
accepts container versions 1 to 4 and reports per mesh when a layout is not understood.

`ttdat.py` also lists and extracts LEGO Batman 2 (index -4) and LEGO Marvel Super Heroes (-5) archives. `an3.py`
contains an `An4Set` class for Marvel `.an4` files: **do not use it**, its key type 7 decoding is wrong; the
reader in [formats/an4/lmsh1](../an4/lmsh1/README.md) is the correct one.

## Use

Python 3.10 or newer; `numpy` and `Pillow` (`matplotlib` only for the two preview scripts). The scripts sit
flat in `tools/` and import each other from there. Each prints its usage when run with no arguments. You supply
your own game files; all paths are arguments.

```text
python tools/extract_game.py "<install folder>" <absolute output folder>
python tools/nu20.py export <file_pc.gsc or .ghg> <out folder>
python tools/gltf_export.py <file_pc.gsc> <same out folder>
python tools/anim_export.py <extracted character folder> <out folder> [--all] [--multi]
python tools/cu2.py info <file.cu2>
python tools/giz.py pickups <file.giz> [out.json]
```

## Notes

- [docs/FORMATS.md](docs/FORMATS.md): layouts as far as they are worked out.
- [docs/GAME_NOTES.md](docs/GAME_NOTES.md): what the data files say about cameras, AI scripts, puzzles.
- [docs/reports](docs/reports/README.md): working reports with the evidence per claim.

The notes sometimes name scripts that exist only in the upstream repository (Marvel-era readers, exe and HUD
study aids); they were left out of this snapshot on purpose.

## Known limits

- TCS: three `.giz` files are empty or cut off in the game data; one older Batman model file is not read.
- `.giz` variable-length sections (obstacles, build-its, breakables) are framed but not decoded.
- Animation clips whose node count differs from the skeleton's map node i to bone i; unverified by eye.
- Cutscene frame rate falls back to an assumed 30 when neither the script nor the header gives one.
- Not read: `.ai2`, `.spl`, `.gin`, particles, camera data in `_cam_pc.gsc`.

References: NU20 field offsets and AN3 header fields follow the community documentation in BactaTank Classic /
EasyAN3 (AlubJ); unlz2k and nublender were consulted as documentation. No code from them is included.
