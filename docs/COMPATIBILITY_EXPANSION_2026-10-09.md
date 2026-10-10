# Compatibility expansion, 9 October 2026

Character 0.5.16 and Cutscene 0.1.25 add classic PC inspection. This is a step
toward wider import coverage, not a complete LB1/TCS character or cutscene
importer. The [README matrix](../README.md#game-and-file-support) separates
full-file inspection, partial Blender assembly and unsupported layouts.

## New entry points

- Character addon: LB1/TCS raw GHG/GSC inspection, including installed-DAT or
  extracted `CHARS` browsing. Reports and hides unresolved rigid pieces;
  native skinning, bind records, UVs, normals and embedded DDS are retained
  for supported draws. Costume/visibility alternatives can overlap. AN3
  playback and classic native export are not enabled.
- Cutscene addon: separate CU2 reference scene importer. Static actor/object
  placements, camera reference empties and shot markers; no assembled models,
  animated camera/lens reconstruction, environments or playback.
- Classic CLI 0.1.1: NU20 model inspection alongside CU2/AN3/GIZ inspectors.
- PC DAT Index GUI 0.1.1 and toolbox 0.1.8: read-only paths and file spans for
  the explicit layouts below. This GUI does not extract assets.

```text
python formats/cu3/scripts/archive_index_classic.py "path/to/GAME.DAT" "new-index.json" --game LB1
```

| Game flag | Archive layout | Check performed |
| --- | --- | --- |
| LB1 | -2, 8-byte tree records | All seven installed archives; 10,645 file entries |
| TCS | -3, hash-routed tree records | One private archived GAME.DAT; 12,174 entries; installed tree has local modifications |
| LB2 | -4, aligned offsets | Four installed archives; 11,865 entries |
| SW3 | -4, aligned offsets | Five installed archives; 9,002 entries |
| LMSH1 | -5, 12-byte tree records | Existing validated archive reader retained |
| HOBBIT | -5, explicit parent records | Existing validated archive reader retained |
| MOVIE1 | -5, explicit parent records | Four installed archives; 47,783 entries |
| LB3 | -6, explicit parent records | Existing validated archive reader retained |

These counts describe index records, not characters or confirmed payload
compatibility. LB1 samples extracted by the new provider match independently
decoded source bytes. Every path still passes traversal, identity, ownership,
extent and storage-mode checks. Output reports refuse existing files.
TCS requires matching full path hashes because its leaf ordinals are not file
table positions. Applying the other layout's offset bits corrupts lookups;
those differences are covered by constructed tests.

## Original model and Blender checks

The local census covered 1,627 selected LB1 resources and installed TCS GHG/GSC
files. 1,596 parsed; 31 were refused: 22 empty/duplicate native bone-name sets,
seven metadata-pointer failures, one older whole-container payload arrangement
and one invalid chunk extent. Within parsed files, some draws still lack a
verified material/stride pairing or contain empty mesh records. File parsing is
not complete geometry or visual coverage. The TCS tree is locally modified and
includes variants; this is not a retail roster census.

Raw Blender previews were inspected for LB1 Catwoman, LB1 Batman titles and
TCS Admiral Ackbar. They exposed unresolved rigid heads/accessories, overlapping
costume/visibility parts, and approximate shading. The first material pass
incorrectly used every texture alpha as transparency; that connection was
removed. The source alpha remains packed for inspection. Native tint, render
states, layered materials and expression playback remain undecoded here.

CU2 reference scenes were checked for an LB1 Batboat sample and a TCS Emperor
Fight sample. These verify reference objects and source timing, not playback.
No classic in-game validation or native export was performed in this pass.
The original LSW1 HGP addon and Xbox 360 prototype reader remain separate.

Fresh Blender operator tests imported the same LB1 Catwoman from installed
archives and an extracted tree: 17 draws, 25 native bones and nine hidden
unbound rigid draws in each. A TCS minikit Snowspeeder GSC imported 14 static
draws and was rendered; its native shadow/transparency plane remains an opaque
rectangle under the approximate material mode. Unsupported-version import and
failed-build rollback left existing scene datablocks unchanged. Source hashes
were unchanged. The CU2 operator retained the previous scene and created 11
reference objects with one source shot marker for the Batboat sample.

The repository checks passed 596 constructed tests plus syntax, documentation
and package integrity checks. All ten independent GUI ZIP launchers/imports
and six combined-toolbox tests passed with their windows hidden. Both Blender
ZIPs passed isolated dependency and simultaneous-registration checks in 5.2.2.
These checks are distinct from original-file and visual validation.

Modern regressions imported and rendered Magneto (LMSH1), Batman (LB3), Thrain
(Hobbit) and Captain America AOU (Avengers), each with a declared idle clip and
finite poses at sampled frames. Two LMSH1 CU3s (`GRANDCENTRAL_MIDTRO_2A_NXG`
and `STARKTOWER_INTRO_NXG`) recovered actors and cameras. Their renders were
inspected with environments deliberately disabled to isolate actor recovery;
this is not a full scene/environment fidelity test. Shader and face reports
remain open. Blender also logged DDS GPU fallback warnings in the cutscene
checks; rendering completed, but those warnings are not evidence of exact
native material output.

## Broader installed-game findings

- Existing LMSH1/LB3/Hobbit/Avengers character profiles retain their layout
  gates. The archive additions do not add modern model versions implicitly.
- LOTR still has refused mode-3 compressed archives.
- Current installed DCSV, LMSH2, TFA and Ninjago archive sets include unverified
  CC trailing tables. Diagnostic reports remain available; not every archive
  revision is enabled for extraction or full character import.
- Jurassic World's observed parent -7 index is not enabled. A private probe
  still had two unresolved path hashes and a large unexplained suffix.
- Skywalker Saga's later archive layouts remain unverified. Sharing `.DAT`,
  `.GHG`, `.GSC` or animation extensions does not establish compatibility.
- Indiana Jones is not installed here. Contributor reports remain distinct
  from local original-file checks. Handheld work was not expanded in this pass.

## Remaining work

Decode classic rigid draw ownership and costume/visibility selections before
claiming complete characters. Then verify native shader controls and AN3
skeleton ownership/coordinate conversion against original poses. CU2 needs
camera lens/movement and actor-track binding before playable scene assembly.
Later archives need a validated interpretation of their additional tables;
unknown suffixes must not simply be ignored.

The NU20 reader is adapted from the offered MIT contribution by Gibby /
stryderjoe, with explicit layout/bounds checks; its license travels with each
package. No contributed native/glTF exporter or unsafe archive extractor was
enabled. PR #5 remains open for that outstanding work. No BactaTank code was
copied or translated. Private assets, scenes and test manifests stay local.
