# LEGO Marvel Super Heroes: DISP 17 and 22, material tables 166 and 169

LMSH1 vehicles, animals and some accessories use four section versions the
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

## UMTL 166 = UMTL 168 less one byte

11 models have table 166 (the bicycle, golf cart, goblin glider, Mr Fantastic's
guitar and teapot and others). Their names sit one byte earlier than in 168/169
(962 against 963 from the record start), while the version word, the UV sets
(+120) and the shader version (+320) and colour space sit where 168 has them.
The texture IDs start at +398 against +399. So the missing byte lies between
the colour space and the IDs, inside the bytes 168 also leaves opaque.

With 168's prefix one byte shorter, all 11 tables read. Their texture IDs run in
order through each file (`TTShaderMaterial1` 0, decals 1, `TPage_LEGO_Hard`
2 and 3), and the footers give cull 0 (one 1), filter 3, write mask 15.

## UMTL 164: measured, not enabled

Table 164 (5 models: snake, penguin, rat, lizard tongue, skunk-tail backpack)
is 168 with one byte less inside the opaque flag block (shader version at +319)
and one less after the colour space (texture IDs at +397, names at +961), and
its footer has 15 tail flag bytes where 168 has 16. Read that way (the 15 bytes
kept opaque, vertex albedo not read) all 5 load, with plausible footers and
tail bytes of 0/1. It is **not enabled here**: `test_material_flags.py`
requires 164 to stay refused, so the choice is yours.

## MESH 161 with morph targets: measured, not enabled

Seven LMSH1 models stop at 'MESH 161 target streams are not verified': the fish,
goat and pig, the Iron Spider and Sandman-goon faces, and `super_city` /
`super_city_remap`. Their morph parts are skinned and store positions as
float3 (type 3), where the MESH 161 skin check expects half floats (type 6);
their unmorphed parts use half floats. With both gates opened, the existing
target reader decodes them (dense and run-length targets, 1 to 21 per part, the
target-table boundary matching) and the buffer references after them resolve
with one base; 6 of the 7 load (`super_city` then stops at a joint map). Not
enabled here: `test_mesh_edit.py` requires a MESH 161 skin and face fixture to
stay refused.

## Results

- `load_model` over all 466 LMSH1 `chars/` models: **414 load**, up from 384. No
  model that loaded before changed (skeleton identity, selection and part
  count hashed).
- LMSH1 vehicles: 79 of 101, up from 59. Most of the rest (21) stop at the
  variant remap check, which PR #23 relaxes for mirror twins.
- 629 random LMSH1, LB3 and LB2 models: 26 refused before now load, 8 refused
  ones now stop at a later check, none that loaded changed.
- Blender 5.2.2, Character add-on built from this branch, `.ghg` imported
  directly: the cat, Deadpool's Vespa, the news van, the Vulture's wings, the
  bicycle, the goblin glider and Mr Fantastic's guitar assemble correctly.
- `formats/cu3/scripts/test_lmsh1_display_versions.py`: DISP 17 reads exactly
  as 16 and enforces its auxiliary counts; 22 reads as 21; 19 and 20 stay
  refused; LOD tables of 17 and 22 select the nearest clip, 23 is still refused.

Not checked: anything in the game.
