# LEGO Batman 2 vehicles: collision groups and LOD remaps

Builds on [LB2_GEOMETRY.md](LB2_GEOMETRY.md) and
[LB2_OLDER_VERSIONS.md](LB2_OLDER_VERSIONS.md). LB2 vehicles and some creatures
are counted HGOL 9 variant groups: a base rig and one or two LOD rigs. Two checks
refused them.

## 1. Collision groups in the base trailer

The variant trailer starts with an auxiliary array. The reader required it to be
empty, and in every LMSH1, LB3 and later group it is. In LB2 the base rig of 48
models fills it with **collision shapes**, up to 12 KB:

```
u32 group count
group:
  u32 0
  u32 type                      0 = hulls only, 1 = primitive (+ hulls)
  14 x f32                      type 1 only; kept, not interpreted
  u32 hull count                type 0: at least 1
  hull:
    u32 face count
    face:   f32 normal[3], u32 corner count
    u32 corner count            = sum of the faces' corner counts
    corner: f32 position[3], u32 (the hull's face count again)
  u8 joint                      the joint the group rides on
```

Evidence:
- In all 48, the parse ends exactly where the known trailer fields start (two
  zero words, bounds, zero vector, threshold 0, identity joint map).
- Each group's joint byte names the part it belongs to:
  `WheelPosFL/FR/RL/RR` and `Body` (taxi, bus, police cars), `wheelPos_F/R` and
  `body` (Batcycle, motorbikes), `Forks` (forklift), `bucket` (Joker's digger),
  `wingL/wingR` (hoverboard).
- Normals are unit length. The taxi's wheels are octagonal cylinders (8 four-corner
  sides and 16 triangles: 80 corners, radius 0.084); its body is a 6-face box.
- Type 1 groups sit on wheel joints (`cat_bike`, `motorbike`, `daisycar`,
  `ambulance`). Their 14 floats hold a radius-like value (0.021 on bikes, 0.052 on
  the daisy car); their meaning is not decoded.

`native_variants.py` reads this for HGOL 9 only and keeps it as the base trailer's
`collision` list. Every other version still refuses a nonzero array, and records
without collision keep their existing identity (the key is added only when
present). Out-of-range joints, unknown group types, empty type-0 groups,
non-unit normals, corner sums that disagree and corner fields that differ from the
face count are refused.

## 2. LOD remaps paired with another joint

Each LOD rig maps every base draw to the LOD draw that replaces it. The selector
refused a rigid draw whose LOD partner rides on a different joint. In 32 LB2 and
16 LMSH1 models such pairs exist (92 and 43 pairs), always between interchangeable
or merged parts:
- mirror twins: Batmobile `wing_R` with `wing_L`, Batwing `Missile_L` with
  `Missile_R`, ambulance `DoorFL` with `DoorFR`, police car `wiperL` with `wiperR`;
- wheels: `wheelPos_FL` with `wheelPos_RR`, Batcycle `wheelPos_F` with `wheelPos_R`;
- repeated parts: Batcopter `blade1` with `blade3`, dodgem `missileA` with `missileD`;
- merged joints in a simplified LOD: the lion's `Neck2` draw with `Head`, the Venus
  flytrap's `stem4X` with `Stem4Y`.

The remap is used for diagnostics only; the importer imports the base rig. These
pairs are now kept as `rigid_remap_differences` in the selection evidence, like the
existing `cross_layer_remaps`, instead of refusing the model. Every other check of
the group (complete ownership, palettes, joint maps, duplicate targets) still
applies.

## 3. Older skeletons: HGOL 8

19 LB2 `.ghg` stopped at the skeleton with an unverified HGOL version: 15 are
HGOL 8, three HGOL 6 (`pig`, `face_male`, `phantom_minifig`) and one HGOL 5
(`ufo`). HGOL 8 has the HGOL 9 layout (name table, joints, binds, points of
interest, no length-prefixed block, layer metadata and layers):
- every HGOL 8 skeleton (21 candidates) ends where HGOL 9 ones do, followed by
  the same zero words, and sits in the same `5LVI` wrapper;
- bind matrices, display ownership and skin palettes pass the existing checks;
- in Blender the T-rex fossil (53 joints), the penguin creature, Penguin's
  umbrella and Robin's acrobat zorb assemble correctly.

One difference: an HGOL 8 variant trailer has **no terminal byte**. The next
counted HGOL follows the metadata map at once (police cruiser A: its second and
third rigs start straight after the map), and the group ends with the HGOL 9
fence.

HGOL 8 is now accepted with that layout, and its variant groups with that
trailer. 10 models load: the T-rex, `super_test`, Robin's zorb, the penguin
creature and umbrella, the backpack hose, the wind-up teeth, two Joker-robot
parts and `minikit_6243`. Of the other five HGOL 8 files, three stop at
material tables 56, 61 and 105 (the jetpack, the flight cape, the security
camera). Two stay refused because the file contradicts itself: police cruiser
A's middle LOD and the old super minifig list their joints in another order
(the cruiser's four wheels) while their joint map claims the identity mapping.
HGOL 5 and 6 are not decoded.

## Results

- **LB2 `load_model`, all 1,259 `.ghg`/`.gsc`: 1,160 load**, up from 1,094
  (1,150 with sections 1 and 2, 10 more with HGOL 8).
  - 44 load with collision on the base rig (4 of the 48 stop at other checks).
  - 32 load with remap differences.
- **LMSH1 vehicles: 75 of 101 load**, up from 59. Among them the X-Jet, the
  Fantasticar, the S.H.I.E.L.D. Helicarrier, Stark's and Doom's jets, the police
  car and the school bus.
- **Regression:** 629 models (260 LMSH1, 200 LB3 and 120 LB2 at random, plus all
  LMSH1 vehicles), skeleton identity, selection, part and vertex counts hashed
  before and after: 42 change, all from refused to loaded. No model that loaded
  before changed.
- **Blender 5.2.2**, Character add-on built from this branch, `.ghg` imported
  directly: the Batmobile (both wings in place), Batwing, taxi and Batcycle (LB2),
  the X-Jet, Fantasticar, police car and Stark's jet (LMSH1) import with complete,
  correctly placed geometry.
- `formats/cu3/scripts/test_lb2_vehicles.py`: hull and primitive groups read to the
  standard fields; no collision keeps the existing fields; seven kinds of
  inconsistency refused; HGOL 10 still refuses a nonzero array; an HGOL 8
  trailer ends without the terminal byte. All other
  `test_*.py` in `formats/cu3/scripts` and `formats/character` pass, including the
  two Blender ones and `test_native_variants.py`.

Not checked: anything in the game. Not done: the collision shapes are read but not
imported into Blender; the type-1 primitive's 14 floats are not interpreted.
