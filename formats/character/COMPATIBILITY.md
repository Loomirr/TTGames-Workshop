# PC character compatibility, 5 October 2026

Version 0.3.0 focuses on the PC NXG/DX11 games. Handheld character support is
separate work and is postponed. Shared file extensions do not imply shared
binary layouts. The Blender game selector offers LMSH1, LB3 and The Hobbit;
the other profiles below are inspection tools, not complete importers.

## New working coverage

- The Hobbit installed archives use a verified parent-index -5 variant. Its
  v27 definitions, MESH 169/170, DISP 24/26 and HGOL 12/16 resources now assemble
  characters with their native skeletons, attachments and declared animation sets.
- Native material footer role IDs select costume texture slots. A fixed role
  lookup was assigning several arms incorrectly; both arms now use their own
  authored slots instead of guessing from material names.
- Standalone character imports default to the explicit gameplay costume layer
  mask. The file importer also offers cutscene layers or authored flags. This
  restores attachments such as Gandalf's hat. CU3 assembly keeps its existing
  authored layer policy.
- HGOL 15 and the observed ROTV version 17 layout, several older material tables,
  high attachment layer bits and empty customization slots are handled explicitly.
  Other version 17 layouts are still rejected.
- LB3 face targets have variable-length companion arrays. Reading a fixed
  length shifted subsequent targets, rejecting valid faces. The reader now
  validates each array length and continuation marker. Zero-length padding runs
  do not consume vertices, and total decoded vertex counts still must match.
- LOTR's name-tree tags and storage flag fields are handled by its own archive
  profile. Separate path hashes, bounds and node references remain checked.
- LMSH2 archive inventory is available. Sample files include both ANI-D and ANI-E;
  successful ANI-D scalar sampling does not establish character playback support.

## Validation

All 146 portable checks pass, including independently constructed archive,
skeleton, display, material-role and facial target fixtures. Package integrity
checks confirm the ZIP contains tools and documentation, with no game assets.

Full installed-roster preflights were run with the current readers:

| Game | Definitions checked | Parser-ready |
| --- | ---: | ---: |
| LMSH1 | 467 | 342 |
| LB3 | 361 | 280 |
| The Hobbit | 417 | 375 |

These are character definitions across minifig, small, bigfig and creature
families, including alternate and inherited definitions. They are not counts
of unique playable characters. Parser-ready means the probed primary model
and immediate attachment models passed the audit. Recursive attachment assembly,
texture conversion, shader appearance, facial timing and animation playback
need separate Blender checks. Missing companions, ambiguous references and
unsupported native records remain failures rather than selecting arbitrary data.

Blender 5.2.2 checks imported Bilbo, Gandalf, B66 Catwoman, Wolverine and B66
Alfred, loaded idle/run/walk for each, sampled start/middle/end poses and mesh
coordinates, and saved private preview scenes. Front renders were inspected.
Gandalf's older cape texture reports missing conversion metadata; some shaders,
surface smoothing and face masking remain approximate. No new in-game export
test was performed. Facial shape targets are readable, but cutscene target-weight
timing is still incomplete.

## Other installed PC games

| Game | Confirmed inspection | Current import blockers |
| --- | --- | --- |
| Avengers | CC archive index, MESH 175, HGOL 17 ROTV, DISP 32; sampled ANI-D | Material table 235 shader layout |
| The Force Awakens | CC archive index, MESH 175, HGOL 17 ROTV | DISP 33, material table 236, ANI-E sampling and some actor bounds |
| DC Super-Villains | CC archive index and animation structure | CD 38, MESH 200, newer HGOL 17, DISP 35 and ANI-E |
| LMSH2 | Full archive inventory; sample ANI-D scalar poses | Newer HGOL 17, DISP 34, material table 270, ANI-E and newer definitions |
| Lord of the Rings | All installed archive indexes; HGOL 10 skeleton | MESH 48, DISP 15 and material table 150 |
| The Skywalker Saga | Container header inspection | New container and model families; no enabled profile |

The local folder labelled Ninjago contains Star Wars III assets and an
uninstaller identifying that game. It was not counted as a verified Ninjago
installation. Neither game gets a Blender support claim from that folder name.

## Reproduce the checks

Run from the repository root with your own game and a cache outside the game:

```powershell
python formats/character/audit_characters.py HOBBIT "D:/Games/LEGO The Hobbit" "output/hobbit-roster.json" --cache "cache"
python formats/character/inspect_game.py LMSH2 "D:/Games/LEGO Marvel Super Heroes 2" "output/lmsh2.json" --cache "cache" --samples 5
python tools/check_repository.py
```

Use `--limit 20` on the roster audit for a quick subset. Reports require a new
output filename. Installed archives are read only; requested companions are
cached separately. Blender checking is manual through the packaged addon or
`check_blender.py` with user-supplied case paths.

The loose-source exporter still copies original model/definition/animation
bytes. It does not encode edited meshes, UVs, materials, skeletons or actions.
The constrained facial writer remains gated to MESH 169/175; MESH 170 reading
does not enable Hobbit facial writing. See the [workflow](README.md) and
[earlier animation research](RESEARCH_0.2.md).
