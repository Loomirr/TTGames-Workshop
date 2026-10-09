# Coverage: what was checked, on what, and what was not

Builds: Steam PC releases of LEGO Batman: The Videogame (app 21000), LEGO Indiana Jones: The Original
Adventures (32330) and LEGO Star Wars: The Complete Saga (32440). Every count below was measured over every
matching file extracted from those installs. These are decode and export checks only: **nothing writes game
files, nothing was validated in game, and exported clips and models were not judged by eye** unless it says so.

| Check | TCS | Indiana Jones 1 | Batman 1 |
| --- | --- | --- | --- |
| Archive entries named and extracted at the stated size | 12,459 of 12,459 (7 archives, index -3) | 9,465 of 9,465 (4 archives, -2) | 10,375 of 10,375 compared (7 archives, -2; 270 level entries not compared) |
| `.gsc` + `.ghg` files that parse | 1,477 of 1,477 | 1,015 of 1,015 | 939 of 940 |
| Meshes that decode without error | 153,367, 0 errors | 78,706, 0 errors | 31,933, 0 errors |
| Mesh uses whose material's vertex size matches the mesh | all (354,059 across the three games) | | |
| `.an3` files that decode | 2,911 of 2,911 | 2,524 of 2,524 | 2,578 of 2,578 |
| `.cu2` files that read; character skeleton tracks; root tracks | 205; 1,944 of 1,944; 1,943 of 1,943 | 112; 1,438 of 1,438; 1,414 of 1,414 | 135; 1,362 of 1,362; 1,130 of 1,130 |
| `.giz` files with every byte accounted for | 248 of 251 | 103 of 103 | 171 of 171 |
| Pickup tables read; pickups; of which valid | 248; 14,919; 14,829 | 103; 8,291; 8,291 | 168; 10,701; 10,701 |
| Animation export, default roles, sample of 20 / 20 / 22 characters | 157 clips | 125 clips | 162 clips |

Also checked: 12 random scenes exported to glTF and validated structurally; 62 character exports per mode
imported into Blender 5.2 running without a window, with actions equal to clips and finite poses; every
script's command line run once.

## Things in the files themselves, not reader faults

- Three TCS `.giz` files are all zeros or cut off, and three more hold records overwritten by unrelated data
  or zeroed. Those 90 pickup records are returned with `valid: false`.
- A few hundred meshes have very large coordinates (for example a cube from -50,000 to +50,000) or odd UVs
  on untextured materials, and some normals are zero-length in the file.
- Texture entries with no data are the five face entries that follow a cubemap.
- One Indiana Jones scene (`outtakes_losttemple_outrowin_pc.gsc`) holds only its description, with no
  textures or buffers.

## Known wrong or unverified

- `an3.py` on LEGO Marvel Super Heroes `.an4`: key type 7 is decoded wrongly and the frame count is taken
  from the key-count field. The TTGames-Workshop project's reader is the one to use there.
- Cutscene frame rate: `fpsec` in the script beside the cutscene, else the header value at 0x5C, else 30.
  The default of 30 is inferred from sound-file lengths, not read from any file. One header value (37.5) is
  not understood.
- Animation clips whose node count differs from the skeleton's map node i to bone i. A wrong bone order
  would pass every check run here.
- `.cu2` version 516 rests on a single small file.
- `.giz` pickup version 5 rests on one non-empty file; a non-empty version 6 table is rejected.

The detailed write-ups, with evidence per claim, are in `docs/reports/`.
