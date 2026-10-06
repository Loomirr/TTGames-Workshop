# TTGames Workshop — Master Roadmap & Progress Tracker
**Project:** TTGames-Workshop  
**Repository:** https://github.com/Loomirr/TTGames-Workshop  
**Roadmap updated:** October 6, 2026  
**Primary goal:** Build reusable, format-aware tooling that can correctly import, inspect, animate, edit, and eventually port assets across the full range of TT Games LEGO PC titles without relying on character-specific hacks.

---

## 1. Project Mission

TTGames Workshop should become a general-purpose research and modding toolkit for Traveller's Tales / TT Games LEGO titles.

The main priority is:

> **Get compatibility working across every TT Games LEGO PC release first, using reusable format support rather than one-off fixes.**

Once the PC compatibility pass is complete, research can expand more heavily into:

- Console versions
- Prototype and review/debug builds
- Handheld versions
- Cross-game character and face porting
- Cutscene reconstruction
- Native editing/export
- Historical format comparison

The guiding rule is that support should be based on **actual file-layout understanding and explicit version handling**, not on forcing one game's assumptions onto another game.

---

# 2. Current Progress

## Main character / animation addon

### Existing enabled PC profiles
These should be treated as the current supported baseline rather than re-added as new roadmap targets.

- [x] LEGO Marvel Super Heroes
- [x] LEGO Batman 3: Beyond Gotham
- [x] LEGO The Hobbit
- [x] LEGO Marvel's Avengers

Last pushed versions: **Character 0.5.5 / CU3 0.1.14**, commit `8487e64`.

Latest locally validated, packaged and installed versions: **Character 0.5.6 / CU3 0.1.15**. These newer changes are included in this source update.

### Completed implementation handoff work

- [x] ~~P1: Preserve attachment dependencies when an optional attachment fails.~~ Successful/shared dependencies survive rollback; failed resources are cleaned up.
- [x] ~~Record consumed source revisions independently of Blender image caches.~~ Model/definition and companion provenance now retains hashes and available archive spans.
- [x] ~~Reject changed or missing native-export companions before creating output.~~ CD/TEX/AS/PAK/loaded AN4 checks passed on copied fixtures.
- [x] ~~Validate and install the updated addons.~~ Four representative character imports, preview/no-op exports, two CU3 imports and repository checks passed. Existing Blender preferences were preserved.

See [the P1 checkpoint](docs/HANDOFF_P1_CHECKPOINT.md) for evidence and limits, and [the remaining handoff](TTGames_Workshop_Remaining_Handoff.md) for the next chat. These checks do not establish whole-roster fidelity, new game support or edited-file in-game validation. Handoff packet P1 is separate from the priority labels later in this roadmap.

Existing work includes varying amounts of:

- Installed-game archive browsing
- CD character definition parsing
- GHG/GSC model loading
- Native skeletons
- Meshes
- UVs
- Vertex colors
- Textures
- Materials
- Character attachments
- Costume/layer selection
- Facial shape targets
- ANI-D animation playback
- Facial BSA tracks
- Attachment animation tracks
- Loose native-source export
- Constrained native mesh edits
- Experimental native ANI-D writing

Whole-roster visual accuracy is **not** considered complete yet. Existing supported profiles should continue to improve as shared readers improve.

---

## Dedicated older-game support

### LEGO Star Wars: The Video Game (2005) — PC
- [x] Dedicated HGP model importer exists
- [x] Native skeleton handling
- [x] Corrected palette colors
- [x] Textures
- [x] Face alpha
- [x] Normal maps
- [ ] Remaining unsupported HGP/header variants
- [ ] Animation support
- [ ] Native model writer
- [ ] More exact shader reconstruction

This game should not need a second completely separate implementation if its existing importer can eventually be connected to the common Workshop UI/profile system.

---

## Cutscene / CU3 work

Current public CU3 work includes:

- [x] LEGO Marvel Super Heroes scene assembly
- [x] LEGO Batman 3 scene assembly
- [x] Actor hierarchy
- [x] Character/attachment loading
- [x] Source camera playback
- [x] Experimental stage geometry
- [x] Facial preview tools
- [x] CU3 name editing
- [x] Character-family replacement planning
- [x] TFA reference inspection
- [x] DCSV reference inspection
- [ ] Complete stage visibility
- [ ] Nested scenes
- [ ] Rigid props
- [ ] Original lighting
- [ ] Audio
- [ ] VFX
- [ ] Exact shader reconstruction
- [ ] Full ANI-E support
- [ ] Full later-game scene assembly

---

## Existing partial PC research

These are **not complete game profiles yet**, but the repository already contains useful research that should be built on rather than restarted.

### LEGO The Lord of the Rings
- [x] Installed archive indexing
- [x] HGOL 10 skeleton observed
- [x] Game-specific name-tree/storage handling
- [ ] MESH 48
- [ ] DISP 15
- [ ] Material table 150
- [ ] Full character profile

### LEGO Star Wars: The Force Awakens
- [x] CC archive indexing
- [x] MESH 175 research
- [x] HGOL 17 ROTV research
- [x] CU3 structural inspection
- [ ] DISP 33
- [ ] Material table 236
- [ ] ANI-E
- [ ] Remaining actor/model bounds
- [ ] Full character profile
- [ ] Full CU3 scene assembly

### LEGO Marvel Super Heroes 2
- [x] Full archive inventory
- [x] Sample ANI-D scalar pose research
- [ ] Newer HGOL 17
- [ ] DISP 34
- [ ] Material table 270
- [ ] ANI-E
- [ ] Newer character definitions
- [ ] Full character profile

### LEGO DC Super-Villains
- [x] CC archive indexing
- [x] Animation structure inspection
- [x] Partial CU3 support / structural inspection
- [ ] CD 38
- [ ] MESH 200
- [ ] Newer HGOL 17
- [ ] DISP 35
- [ ] ANI-E
- [ ] Full character profile
- [ ] Full CU3 scene assembly

### LEGO Star Wars: The Skywalker Saga
- [x] Container header inspection
- [ ] Archive/container implementation
- [ ] Model family research
- [ ] Character definitions
- [ ] Skeletons
- [ ] Textures/materials
- [ ] Animation
- [ ] Full profile

---

## Other existing Workshop research

These remain valuable but do not replace the PC compatibility goal.

### LEGO Indiana Jones 1 — Xbox 360 prototype
- [x] Prototype texture extractor
- [x] BC1/BC2/BC3/BC5
- [x] Float textures
- [x] Cubemaps
- [x] TEX/font handling
- [ ] Models
- [ ] Animations
- [ ] Replacement-container writer

### LEGO Marvel Super Heroes: Universe in Peril — 3DS
- [x] BTGA/PICA texture work
- [x] FUSE payload reader
- [ ] Wider handheld format support

### LEGO Fortnite
- [x] Separate static exported-asset profile
- [x] Recipe/material assembly
- [x] Optional installed-game extraction bridge
- [ ] Wider replacement-part support
- [ ] Static face atlas completion
- [ ] Shader accuracy

LEGO Fortnite is a separate Unreal/export pipeline and should not block TT-engine PC compatibility work.

---

# 3. Definition of "Game Compatibility"

A game should not be marked complete merely because one model loads.

Each new game profile should move through the same validation stages.

## Stage A — Archive / inventory
- [ ] Installed game can be indexed read-only
- [ ] File paths or hashes are resolved where possible
- [ ] Character definitions can be discovered
- [ ] Companion resources can be located automatically
- [ ] Version/layout inventory report can be generated

## Stage B — Structural format support
- [ ] CD definitions
- [ ] Primary model format
- [ ] GHG/GSC equivalents
- [ ] MESH variants
- [ ] DISP variants
- [ ] HGOL / skeleton variants
- [ ] Material tables
- [ ] Texture stores
- [ ] Attachment definitions
- [ ] Face-target records

Unknown variants should **fail explicitly**, not silently use the closest known layout.

## Stage C — Blender character assembly
A representative character must import with:

- [ ] Correct body geometry
- [ ] Correct native skeleton
- [ ] Correct transforms
- [ ] Correct UVs
- [ ] Correct authored normals
- [ ] Correct vertex colors
- [ ] Correct body-part/material assignments
- [ ] Correct textures
- [ ] Correct attachments
- [ ] Correct LOD choice
- [ ] Correct costume/layer flags
- [ ] Correct face geometry/shape targets

## Stage D — Animation
- [ ] Animation catalogue discovery
- [ ] ANI-D where applicable
- [ ] ANI-E where applicable
- [ ] Root movement
- [ ] Attachment animation
- [ ] Facial animation
- [ ] Cape/secondary rig handling
- [ ] Events reported instead of discarded silently

## Stage E — Accuracy validation
Test at minimum:

1. Standard minifigure
2. Character with hair/hat
3. Character with cape
4. Character with multiple attachments
5. Character with facial animation
6. Non-standard body type if the game contains one
7. Creature/bigfig/small character where applicable

A parser audit is useful, but **parser-ready does not mean visually accurate**.

## Stage F — Editing/export
This can follow import compatibility rather than blocking every game.

- [ ] Byte-identical no-op round trip
- [ ] Safe position edits
- [ ] UV edits
- [ ] Vertex-color edits
- [ ] Normal edits
- [ ] Existing skin-weight edits
- [ ] Face-target edits
- [ ] Animation edits
- [ ] Material/texture editing where understood
- [ ] In-game test

---

# 4. Core Architecture Work Before Mass Game Expansion

## 4.1 Universal Game Profile Registry
Create one central profile system instead of scattering game-name checks throughout readers.

Each profile should describe things such as:

- Archive family
- Endianness
- Character-definition versions
- MESH versions
- DISP versions
- HGOL versions
- UMTL/material versions
- TXTS versions
- Face-target format
- Animation family
- CU3 versions
- Path/hash behavior
- Known special flags
- Supported capabilities

Example concept:

```text
GameProfile
 ├─ archive
 ├─ character_definition
 ├─ mesh
 ├─ display
 ├─ skeleton
 ├─ materials
 ├─ textures
 ├─ face
 ├─ animation
 ├─ cutscene
 └─ capabilities
```

Game profiles should select **verified format implementations**, not contain character-specific workarounds.

---

## 4.2 Version-Gated Shared Readers

Refactor the major systems around explicit format versions:

- Mesh reader
- Skeleton reader
- Display table reader
- Material reader
- Texture reader
- Character definition reader
- Attachment reader
- Face target reader
- Animation reader
- Archive reader
- CU3 reader

Where two games really share a format version, they should use the same implementation.

Where they differ, branch by the actual record/layout version rather than by arbitrary character names.

---

## 4.3 Compatibility Diagnostics

Every failed import should report:

- Game profile
- File
- Format type
- Version
- Offset
- Expected structure
- Observed structure
- Whether failure occurred in geometry, material, skeleton, face, attachment, or animation parsing

Add a **Generate Compatibility Report** option so problem characters become useful reverse-engineering samples.

---

## 4.4 Regression Corpus

Maintain a private/local validation manifest containing representative characters from every supported game.

For every sample store:

- Game
- Character
- Body family
- Model versions encountered
- Material versions
- Skeleton version
- Texture-store version
- Face format
- Attachments
- Animation types
- Expected mesh counts
- Expected bone counts
- Known warnings

Run the same validation suite after every shared-reader change.

---

# 5. PC Compatibility Roadmap

The following list intentionally excludes the games already enabled in the main character addon from being treated as brand-new targets:

- LEGO Marvel Super Heroes
- LEGO The Hobbit
- LEGO Batman 3
- LEGO Marvel's Avengers

LEGO Star Wars: The Video Game already has a dedicated PC HGP importer and should be integrated/hardened rather than restarted.

---

# Milestone 0.6 — Finish the Already-Started PC Profiles

These provide the highest leverage because useful reverse engineering is already present.

## 0.6A — LEGO The Lord of the Rings
- [ ] Finish MESH 48
- [ ] Finish DISP 15
- [ ] Finish material 150
- [ ] Character browser
- [ ] Attachments
- [ ] Faces
- [ ] Animation catalogue
- [ ] Representative Blender validation
- [ ] Enable profile

## 0.6B — LEGO Star Wars: The Force Awakens
- [ ] DISP 33
- [ ] Material 236
- [ ] ANI-E investigation
- [ ] Remaining HGOL/model variants
- [ ] Faces
- [ ] Attachments
- [ ] Representative Blender validation
- [ ] Enable profile
- [ ] Promote CU3 from reference inspection toward scene assembly

## 0.6C — LEGO Marvel Super Heroes 2
- [ ] New HGOL 17
- [ ] DISP 34
- [ ] Material 270
- [ ] Newer definitions
- [ ] ANI-E
- [ ] Faces/attachments
- [ ] Representative Blender validation
- [ ] Enable profile

## 0.6D — LEGO DC Super-Villains
- [ ] CD 38
- [ ] MESH 200
- [ ] HGOL 17 variant
- [ ] DISP 35
- [ ] Materials/textures
- [ ] ANI-E
- [ ] Faces
- [ ] Representative Blender validation
- [ ] Enable profile
- [ ] Promote CU3 beyond reference inspection

**Milestone result:** the partially researched PC titles become actual selectable character profiles.

---

# Milestone 0.7 — Classic PC Generation

Use format-family similarities so each solved layout helps several games.

## Wave 1 — Early TT LEGO family
- [ ] LEGO Star Wars II: The Original Trilogy (2006)
- [ ] BIONICLE Heroes (2006)
- [ ] LEGO Star Wars: The Complete Saga (2007)
- [ ] LEGO Indiana Jones: The Original Adventures (2008) — PC
- [ ] LEGO Batman: The Videogame (2008)

### Goals
- Archive profiles
- Character browsing
- HGP/GHG/GSC relationship mapping
- Skeleton differences
- Texture/material differences
- Character assembly
- Animation format mapping
- Shared classic-era reader wherever genuinely possible

The existing LSW1 HGP work should become the starting reference for this generation.

---

## Wave 2 — 2009–2012 engine evolution
- [ ] LEGO Indiana Jones 2: The Adventure Continues (2009)
- [ ] LEGO Harry Potter: Years 1–4 (2010)
- [ ] LEGO Star Wars III: The Clone Wars (2011)
- [ ] LEGO Pirates of the Caribbean: The Video Game (2011)
- [ ] LEGO Harry Potter: Years 5–7 (2011)
- [ ] LEGO Batman 2: DC Super Heroes (2012)

LOTR is handled in Milestone 0.6 because it already has partial repository research.

### Important target
Document exactly where the older classic formats transition into the later NXG families now handled by the modern character addon.

---

# Milestone 0.8 — Remaining 2014–2019 PC Games

Existing supported games from this era remain regression targets but are not duplicated below.

## 2014–2016
- [ ] The LEGO Movie Videogame (2014)
- [ ] LEGO Jurassic World (2015)

TFA is handled in Milestone 0.6.

## 2017
- [ ] LEGO Worlds
- [ ] LEGO City Undercover
- [ ] The LEGO NINJAGO Movie Video Game

LMSH2 is handled in Milestone 0.6.

## 2018–2019
- [ ] LEGO The Incredibles
- [ ] The LEGO Movie 2 Videogame

DCSV is handled in Milestone 0.6.

### Goal
By the end of 0.8, every pre-Skywalker TT Games LEGO title released for Windows should at minimum have:

- A real game profile
- Archive/inventory support
- Character browsing
- Correct representative character assembly
- A known animation-support state
- Explicit unsupported-layout reporting
- A compatibility report

---

# Milestone 0.9 — Modern PC Branches

These should remain architecturally separate where the engine/data model has fundamentally changed.

## LEGO Star Wars: The Skywalker Saga (2022)
- [ ] Complete container/index research
- [ ] Character asset discovery
- [ ] Models
- [ ] Skeletons
- [ ] Materials/textures
- [ ] Faces
- [ ] Animations
- [ ] Blender profile
- [ ] Validation

Do not force older GHG/NXG assumptions onto this generation.

---

## LEGO Harry Potter Collection (2024 PC remaster)
- [ ] Compare remaster assets against original Years 1–4
- [ ] Compare remaster assets against original Years 5–7
- [ ] Determine whether it is:
  - compatible data with new packaging,
  - revised native TT formats,
  - or a separate remaster pipeline
- [ ] Add collection/remaster profile
- [ ] Confirm both halves
- [ ] Validate remaster-specific textures/materials

---

## LEGO Batman: Legacy of the Dark Knight (2026)
- [ ] Keep as a modern/specialized profile rather than pretending it uses the classic TT binary stack
- [ ] Inventory UE5 asset families relevant to characters
- [ ] Character definitions/data assets
- [ ] Skeletal meshes
- [ ] Materials
- [ ] Textures
- [ ] Morph targets/faces
- [ ] Animations
- [ ] Equipment/accessory relationships
- [ ] Build reusable import/inspection bridge
- [ ] Keep LOTDK-specific modding experiments separate from general TT-native readers where appropriate

Existing LOTDK work can inform this, but reusable Workshop code should stay format-oriented.

---

# Milestone 1.0 — All TT LEGO PC Games Baseline

**Target:** every applicable TT Games / Traveller's Tales LEGO Windows release has a documented compatibility profile.

For each game, the compatibility matrix should show:

| Area | State |
|---|---|
| Archive/index | Supported / Partial / Unsupported |
| Character definitions | Supported / Partial / Unsupported |
| Mesh | Supported / Partial / Unsupported |
| Skeleton | Supported / Partial / Unsupported |
| Materials | Supported / Partial / Unsupported |
| Textures | Supported / Partial / Unsupported |
| Faces | Supported / Partial / Unsupported |
| Attachments | Supported / Partial / Unsupported |
| ANI-D | Supported / N/A / Partial |
| ANI-E | Supported / N/A / Partial |
| CU3 | Supported / N/A / Inspection |
| Native export | Supported / Constrained / No |
| In-game validation | Yes / Partial / No |

### 1.0 rule
A title can reach the PC compatibility baseline before arbitrary native editing is solved, but **visual character import must be genuinely usable and format limitations must be explicit**.

---

# 6. Accuracy Pass Across Existing and New Games

After basic PC coverage is broad, perform a cross-game accuracy sweep.

## Geometry
- [ ] Wrong body-part variants
- [ ] Duplicate LODs
- [ ] Missing accessories
- [ ] Mirrored geometry
- [ ] Incorrect draw groups
- [ ] Bad bind transforms
- [ ] Bigfig/small/creature edge cases

## UV / texture
- [ ] Wrong texture role
- [ ] Arm/leg print channels
- [ ] Mirrored prints
- [ ] Alpha cutouts
- [ ] Packed normal maps
- [ ] Shared texture pages
- [ ] Palette/indexed color systems

## Materials
- [ ] Native material role IDs
- [ ] Transparent/cutout surfaces
- [ ] Vertex-color-only materials
- [ ] Metallic/special surfaces
- [ ] Emissive materials
- [ ] Depth-only face masks
- [ ] Game-era shader flags

## Faces
- [ ] Correct face mesh
- [ ] Correct face attachment
- [ ] Correct target count
- [ ] Correct target vertex mapping
- [ ] Teeth/mouth depth handling
- [ ] Facial animation timing
- [ ] Cutscene-only FACE resources

## Attachments
- [ ] Hair
- [ ] Hats
- [ ] Helmets
- [ ] Capes
- [ ] Backpacks
- [ ] Weapons/tools
- [ ] Character-specific props
- [ ] Animated attachments

---

# 7. General Cross-Game Face Transfer System

The requested face ports should be used as **regression targets for a generic face transfer system**, not implemented as isolated hardcoded conversions.

## Goal

Create a pipeline:

```text
Source Face
   ↓
Decode native source mesh + target data
   ↓
Normalize into a game-independent face representation
   ↓
Map/retarget onto destination face topology
   ↓
Encode using destination game's native format
   ↓
Validate
```

The intermediate representation should preserve where possible:

- Basis vertices
- Native target IDs
- Morph deltas
- UVs
- Normals
- Vertex colors
- Material slots
- Facial mask roles
- Bone/attachment transform
- Metadata needed by destination format

---

## Requested Ninjago → TFA face project

Source: **The LEGO NINJAGO Movie Video Game**

Research/port:

- [ ] FACE_KAI
- [ ] FACE_JAY
- [ ] FACE_ZANE
- [ ] FACE_LLOYD
- [ ] FACE_COLE
- [ ] FACE_NYA

Destination: **LEGO Star Wars: The Force Awakens**

Potential destination bases to evaluate:
- Anakin
- Rey
- Other TFA faces with the closest topology/target layout

### Required research
- [ ] Determine Ninjago FACE model format/version
- [ ] Determine TFA destination FACE topology and target layout
- [ ] Compare vertex order/count
- [ ] Compare target IDs/count
- [ ] Compare masks/material roles
- [ ] Determine whether direct target transfer is possible
- [ ] If topology differs, build deterministic retargeting instead of hand-editing six characters
- [ ] Validate one source/destination pair
- [ ] Run the same converter on all six ninja faces

**Success condition:** once the format pair is understood, a new Ninjago face should be transferable without adding character-name-specific code.

---

## Requested LB3 → DCSV face projects

### Dark Knight Joker
- [ ] Source: Joker face from LEGO Batman 3
- [ ] Destination: Joker face in LEGO DC Super-Villains

### Robin → Damian Wayne
- [ ] Source: Robin face from LEGO Batman 3
- [ ] Destination: Damian Wayne face in LEGO DC Super-Villains

### Required generalized work
- [x] ~~Decode verified LB3 face-target layouts~~ — existing layouts only; broader coverage and cutscene target timing remain unfinished.
- [ ] Complete DCSV face model support
- [ ] Build topology/target compatibility report
- [ ] Retarget if topology differs
- [ ] Preserve DCSV-native container structure
- [ ] Write safe destination-format output
- [ ] Re-read exported result
- [ ] In-game test

These two ports should become the acceptance test for **LB3 → DCSV face conversion**, not two special cases.

---

# 8. Prototype / Historical Build Research
**Start major work here after the PC compatibility baseline is complete**, except when a prototype directly helps solve an active PC format.

## Prototype inventory supplied for research

### LEGO Star Wars II
- [ ] Original Xbox — July 24, 2006 prototype

### LEGO Star Wars: The Complete Saga
- [ ] Wii prototype — date currently unknown

### LEGO Indiana Jones: The Original Adventures
- [x] Xbox 360 April 23, 2008 prototype texture research already exists
- [ ] Expand into model/animation comparisons

### LEGO Indiana Jones 2
- [ ] Xbox 360 — October 6, 2009 prototype
- [ ] Wii — August 10, 2009 prototype
- [ ] Wii — August 17, 2009 prototype

### LEGO Harry Potter: Years 1–4
- [ ] Xbox 360 — May 6, 2010 prototype
- [ ] Nintendo DS — unknown-date prototype
- [ ] Nintendo DS — June 24, 2010 prototype
- [ ] Nintendo DS — July 31, 2010 debug prototype

### LEGO Pirates of the Caribbean
- [ ] Nintendo DS — February 7, 2011 debug prototype

### LEGO Batman 2
- [ ] April 19, 2012 debug/review build

### The LEGO Movie Videogame
- [ ] Xbox 360 — December 12, 2013 prototype

### LEGO Star Wars: The Force Awakens
- [ ] Nintendo 3DS — April 27, 2016 prototype

### Steam LEGO beta collection
- [ ] Inventory available beta branches/builds
- [ ] Hash/version each build
- [ ] Compare format-version changes against retail
- [ ] Identify removed/changed assets and debug metadata

---

## Prototype comparison workflow

For every prototype:

1. Record game/platform/build date.
2. Hash the source image/build.
3. Inventory archives.
4. Generate format-version histogram.
5. Compare retail vs prototype:
   - archive structure
   - character definitions
   - models
   - skeletons
   - materials
   - textures
   - face targets
   - animations
   - CU3/cutscene structures
6. Identify debug strings and unused format fields.
7. Document anything that explains currently unknown retail fields.
8. Never modify the original sample.
9. Keep proprietary game assets outside Git.

---

# 9. Console / Handheld Compatibility — After PC

## Higher-value console branches
- [ ] Original Xbox
- [ ] Xbox 360
- [ ] PlayStation 2
- [ ] PlayStation 3
- [ ] GameCube
- [ ] Wii
- [ ] Wii U
- [ ] PSP

Focus on formats that can improve understanding of PC versions or expose earlier/later forms of the same structures.

## Handheld branches
- [ ] Nintendo DS
- [ ] Nintendo 3DS
- [ ] Game Boy Advance

Handheld versions should remain a separate compatibility track because they often use substantially different engines/assets.

The existing 3DS BTGA/FUSE research is the starting point.

## LEGO Dimensions
- [ ] Add as a dedicated console-only research target
- [ ] Do not include it in the PC completion percentage
- [ ] Compare its late-era formats with Jurassic World / Avengers / TFA where useful

---

# 10. Testing Strategy

## Per-game smoke test
For every enabled profile:

- [ ] Archive opens
- [ ] Character list populates
- [ ] Search works
- [ ] Standard minifigure imports
- [ ] Accessory character imports
- [ ] Face target character imports
- [ ] Animation loads
- [ ] Preview scene builds
- [ ] Report contains no silent parser fallback

## Whole-roster audit
Run a parser preflight across every discovered character definition.

Report separately:

- Parsed
- Missing dependency
- Unsupported layout
- Ambiguous reference
- Unsupported texture/material
- Unsupported skeleton
- Unsupported face
- Unsupported attachment

Never combine these into a misleading "working character" count.

## Visual validation
Save local/private comparison renders for representative samples.

Track:
- geometry
- print alignment
- colors
- normals
- transparency
- masks
- attachments
- expression
- pose

## Export validation
Where writers exist:

1. No-op export.
2. Reimport.
3. Compare native bytes or decoded structures.
4. Apply one constrained edit.
5. Reimport.
6. Test in game where practical.

---

# 11. Repository Organization Goals

Suggested long-term layout:

```text
formats/
    archive/
    character/
    mesh/
    skeleton/
    material/
    texture/
    face/
    animation/
    cu3/

games/
    <game profile + game-specific notes only>

tools/
    inspectors/
    converters/
    validators/
    gui/

docs/
    compatibility/
    formats/
    prototypes/
    roadmap/
```

Game folders should document and configure format combinations.

Format implementations should live in reusable format modules whenever practical.

---

# 12. Documentation Goals

For every newly supported layout, document:

- Format name
- Version
- First confirmed game
- Other confirmed games
- Endianness
- Header
- Record structure
- Unknown fields
- Validation checks
- Known edge cases
- Writer state
- Example hashes/metadata without distributing game assets

Create machine-readable compatibility data so the GUI and README can be generated from the same source.

---

# 13. Priority Order

## P0 — Do not regress existing support
- LMSH1
- LB3
- Hobbit
- Avengers
- LSW1 dedicated importer
- Current CU3 tools
- Existing LIJ1 prototype texture work

## P1 — Finish already-started PC support
1. LOTR
2. TFA
3. LMSH2
4. DCSV

## P2 — Expand shared PC compatibility
1. Classic 2006–2008 family
2. 2009–2012 family
3. Movie 1 / Jurassic World
4. Worlds / City Undercover / Ninjago
5. Incredibles / Movie 2

## P3 — Modern PC branches
1. Skywalker Saga
2. Harry Potter Collection remaster
3. Legacy of the Dark Knight

## P4 — Generalized cross-game porting
- Ninjago faces → TFA
- LB3 Joker → DCSV Joker
- LB3 Robin → DCSV Damian
- General character/face transfer framework

This work may begin earlier when it directly validates a newly completed game profile.

## P5 — Prototype research
- Console prototypes
- Steam betas
- Retail/prototype format diffs

## P6 — Broader console/handheld support
- Xbox/X360/PS2/PS3/GCN/Wii/Wii U/PSP
- DS/3DS/GBA
- LEGO Dimensions

---

# 14. Proposed Release Milestones

## 0.6.x — Partial PC profiles become real profiles
- LOTR
- TFA
- LMSH2
- DCSV
- GameProfile/version registry improvements

## 0.7.x — Classic PC expansion
- LSW2
- BIONICLE Heroes
- TCS
- LIJ1 PC
- LB1
- LIJ2
- HP1–4
- LSW3
- POTC
- HP5–7
- LB2

## 0.8.x — Remaining legacy Windows titles
- LEGO Movie
- Jurassic World
- Worlds
- City Undercover
- Ninjago Movie
- Incredibles
- LEGO Movie 2
- Accuracy sweep across existing supported profiles

## 0.9.x — Modern PC support
- Skywalker Saga
- Harry Potter Collection
- LOTDK reusable Workshop bridge
- Cross-generation format abstraction cleanup

## 1.0 — All TT LEGO PC compatibility baseline
- Every applicable Windows TT LEGO title represented
- Machine-readable compatibility matrix
- Representative character validation for every profile
- Unknown layouts explicitly reported
- No character-name-specific compatibility hacks in shared readers

## 1.1+ — Deep research / porting era
- General face transfer
- Wider native writers
- Prototype comparisons
- Console profiles
- Handheld profiles
- Expanded CU3 reconstruction
- Animation/event writing
- Cross-game character conversion

---

# 15. Immediate Next Tasks

1. [x] ~~Establish baseline regressions for LMSH1/LB3/Hobbit/Avengers.~~ Character 0.5.6 representative import/preview/no-op export checks passed; this is not a complete roster audit.
   
Next implementation packet: **P2 — shared-source edit conflicts and staged output publication**, followed by **P3 — archive preflight and bounded framing**. See the remaining handoff before expanding format coverage. Both are still unfinished.

2. [ ] Create the central GameProfile/capability registry.
3. [ ] Convert current per-game/version branches into reusable version-gated readers where possible.
4. [ ] Add a compatibility-report generator.
5. [ ] Finish LOTR's known blockers.
6. [ ] Finish TFA's DISP/material/ANI-E blockers.
7. [ ] Finish LMSH2's newer HGOL/DISP/material blockers.
8. [ ] Finish DCSV's CD/MESH/HGOL/DISP/ANI-E blockers.
9. [ ] Promote those four games into selectable profiles once representative Blender tests pass.
10. [ ] Start the classic-generation sweep using LSW1 as the earliest reference point.
11. [ ] Add Ninjago as a full profile before attempting the six requested Ninjago → TFA face conversions.
12. [ ] Use the Ninjago/TFA and LB3/DCSV ports to drive a generic face-transfer format instead of one-off converters.
13. [ ] Do the large prototype/console sweep only after the PC compatibility matrix is substantially complete.

---

# 16. End Goal

TTGames Workshop should eventually be able to answer:

> "What game is this asset from, what exact TT format versions does it use, can the Workshop decode it accurately, can Blender reproduce it correctly, and can the data be safely converted or written back?"

without needing a new character-specific patch every time.

The project should grow by understanding **formats and format families**, with individual characters serving as validation cases rather than becoming the architecture.
