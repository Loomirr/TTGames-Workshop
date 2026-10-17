# LEGO Marvel Super Heroes: DISP 17 and 22, material table 169

LMSH1 vehicles, animals and some accessories use three section versions the
readers refused. Each turns out to be a neighbour's layout.

## DISP 17 = DISP 16

16 LMSH1 models (`chars/`) have DISP 17. Read as DISP 16, every one of them
decodes: commands, clips, the 2- and 4-byte arrays, then **three per-clip arrays
whose counts must equal the clip count** (the DISP 16 check), then the named
instances. Read as DISP 18 (which has no such arrays) they fail at the instances
(range counts, invalid clips, string addresses). DISP 17 now takes the DISP 16
path, including that check.

## DISP 22 = DISP 21

11 models have DISP 22. They decode with the shared DISP 18-24 path; as 21 and
as 23 the results are the same (7 load at once, 4 then stop at the variant remap
check). DISP 22 is now accepted on that path.

## LOD tables

`model_bindings` selects the nearest LOD only for display versions it has seen
with LOD tables. DISP 17 and 22 models carry the same far-to-near tables
(thresholds strictly decreasing to 0, consecutive clips, `0xb3` draws), so both
are added to that list. DISP 23 stays outside it.

## UMTL 169 = UMTL 168

15 LMSH1 models have material table 169, among them the cat, dog, gorilla and
squirrel, Deadpool's Vespa, the Marvel kart, the pizza bike, the S.H.I.E.L.D.
drone and crane and the Vulture's wings (the pigeon and seagull swarms then stop
at their position-less meshes). Read as 168, all 15 tables decode,
with 168's checks passing (version 2, shader version 4, vertex albedo 0/1, valid
UV sets) and plausible footers (cull 0, filter 3, write mask 15, alpha test
mode 8). As 163, 172 or 174 the shader prefix fails. 169 now uses 168's prefix,
footer and the same preview notes.

UMTL 166 (11 models, among them the bicycle, golf cart and goblin glider) fits
none of 163, 168 and 172 and stays refused.

## Results

- `load_model` over all 466 LMSH1 `chars/` models: **404 load**, up from 384. No
  model that loaded before changed (skeleton identity, selection and part
  count hashed).
- LMSH1 vehicles: 72 of 101, up from 59. Most of the rest (21) stop at the
  variant remap check, which PR #23 relaxes for mirror twins.
- 629 random LMSH1, LB3 and LB2 models: 18 refused before now load, 16 refused
  ones now stop at a later check, none that loaded changed.
- Blender 5.2.2, Character add-on built from this branch, `.ghg` imported
  directly: the cat, Deadpool's Vespa, the news van and the Vulture's wings
  assemble correctly.
- `formats/cu3/scripts/test_lmsh1_display_versions.py`: DISP 17 reads exactly
  as 16 and enforces its auxiliary counts; 22 reads as 21; 19 and 20 stay
  refused; LOD tables of 17 and 22 select the nearest clip, 23 is still refused.

Not checked: anything in the game.
