# LSW1 feedback and GitHub review — 2026-10-15

## LSW1 HGP 0.1.5

- Multiple-file spacing defaults to zero; filename case and underscores remain intact.
- Joint-name relocation uses the recorded first-name offset. The old fixed offset truncated some native bone names.
- The observed original PC offsets 0x28 and 0x36 are enabled with table bounds and finite-transform checks. Unknown layouts remain rejected.
- All 149 local original HGP files decoded, including AUTO and nonempty detail layers: 12,383 primitives, valid material/texture references and bind-inverse errors below 2e-5.
- Six constructed header/bounds regressions pass. Blender checks cover two Yodas, Watto and Dooku's speeder: hierarchy, exact names, zero batch spacing and native rest matrices.
- Watto's opposing wing axes are authored in the source. Bone sticks are not child-pointing guides; no cosmetic flips were applied.
- WheelBike imported with 74 meshes, eight bones and 19 packed images. Its render was inspected. The local file actually contains a Droid Starfighter; another edition's WheelBike contents are not established.

## GitHub PRs

[PR 7](https://github.com/Loomirr/TTGames-Workshop/pull/7) adds an explicit stored-only LSW2 DAT -1 index profile and tests. [PR 8](https://github.com/Loomirr/TTGames-Workshop/pull/8) enables classic NU20 container version 3, retaining payload validation. Changes were reviewed and integrated with existing code. Contributor attribution and MIT licensing remain intact. Reviewed heads: PR 7 `9bd83fd986948afac972535b9baecc7e957b0fdf`; PR 8 `059434b9c992216dfe5ddd5f5acaeb2adaf4af18` (Gibby / stryderjoe).

LSW2 and Indiana Jones 1 original-file counts are contributor-reported, not local validation. LSW2 has no complete HGP/character Blender importer. Classic version-3 support is raw inspection, not complete character assembly or animation export.

[PR 5](https://github.com/Loomirr/TTGames-Workshop/pull/5) supplied the previously reviewed classic inspectors. Its author has withdrawn the old archive implementations, approximate AN4 reader and exporters. Those withdrawn additions were not applied.

## LB2 issue 9

The reported absolute CMI names can now be explicitly remapped with the PAK extractor's `--cubemap-basenames` option. Default extraction and animation lookup remain strict. Only drive-qualified Windows CMI names are remapped; invalid segments, duplicate basenames, case aliases and reserved filenames are rejected before publication. The manifest retains the original name. All 52 local original cubemap packages passed opt-in parsing (68 remapped members); all 52 remained rejected in strict mode. One original package was extracted successfully to a new folder.

This is container extraction, not a CMI texture decoder. LB2's earlier CU3 and AN4 payload layouts, and its big-endian model bodies without the newer resource wrapper, remain unsupported. No version gate was bypassed to manufacture imported scenes.

## Remaining visual reports

[Issue 1](https://github.com/Loomirr/TTGames-Workshop/issues/1) remains open. Prior material/LOD/UV fixes do not establish complete facial shader fidelity. Native normals and topology are preserved; automatic vertex welding and blanket normal replacement are not appropriate fixes for every seam. Face depth/expression differences and the reported global mirroring still require validation.

Private original files, renders, scenes and machine-specific audit manifests remain under ignored `local/validation/`. These checks do not constitute in-game validation.

Fresh Tony Stark and Vulture live/composed previews and idle-frame renders were inspected. Tony's `TonyStark_Default/Idle2` wink retains a white sliver; Vulture retains eye/mouth clipping jaggies. These remain unresolved rather than being hidden by guessed target or axis changes.

All three packaged Blender addons passed simultaneous registration, module loading and file-drop routing checks in Blender 5.2.2. The packaged HGP operator imported WheelBike successfully. The manual repository suite passed, including the new header and PAK path regressions.

Seven GUI/dispatch tests pass with Python, Pillow and Tk available. The workstation's default Python lacks Pillow, so the BTGA worker checks were rerun with those documented dependencies present.
