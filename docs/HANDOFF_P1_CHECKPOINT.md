# Attachment dependencies and source revisions

The 6 October implementation handoff was reviewed against commit `8487e64`.
Its P1 attachment-rollback risk was reproduced on Character 0.5.5 using the
installed LMSH1 Wolverine specimen and an injected optional-attachment failure.
The body survived, but `tt_native_texture_sources` became empty. This was an
actual Blender regression, rather than confirmation from source inspection alone.
The old exporter also accepted changed CD, TEX and AS files on a copied fixture.

## Implemented behavior

Character 0.5.6 restores image/store caches, material-report entries and consumed
dependency records to their pre-attachment snapshot. Earlier successful and
shared dependencies survive; newly created failed resources are removed.
The dependency ledger is independent of Blender image names/cache lifetime.
It records logical paths, roles, consumed SHA-256 revisions and available
archive/member spans. Catalog bank indexes are verified but copied only when
their animations are loaded. Loaded standalone AN4 files are also tracked.

Native source-bundle export verifies recorded CD, TEX, texture-store, AS,
loaded AN4 and PAK revisions before creating output. Export uses those verified
bytes and retained logical paths. Changed/missing companions are named errors.
Older imports need reimporting to establish these consumed revisions; they
cannot acquire a trustworthy old baseline during export. The separate active
ANI-D writer retains its existing action/source guards.

Shared readers retain the digest of consumed model/definition bytes. Model
decoding checks that the source revision remained stable. CU3 0.1.15 includes
that model check; the full character companion ledger is not a CU3 bundle writer.

## Verification checkpoint

Public focused checks are `test_source_provenance.py` and
`check_dependency_rollback_blender.py`. The latter accepts user game, cache,
output and extracted-addon paths; it contains no game fixtures. It covers final
failure, success/failure/success ordering, shared textures, failed-image cleanup,
byte-identical no-op export/reimport and changed CD/TEX/AS/PAK/AN4 rejection
before output appears. Five synthetic provenance tests cover revision mismatch,
missing sources, rollback ownership, archive spans and bank-use tracking.

Private original-file logs and input identities stay under ignored
`local/validation/handoff-p1/`. No game installation or edited project is changed.
These checks do not establish new format/game support or edited-file gameplay.
The repository release suite and four fresh character import/preview/no-op
exports passed across LMSH1, LB3, Hobbit and Avengers. No new in-game editing
test was run: this packet changes dependency integrity, not native edit encoding.

Commands: `python formats/cu3/scripts/test_source_provenance.py`,
`python tools/check_repository.py`, and Blender's `--background --factory-startup
--python formats/character/check_dependency_rollback_blender.py --` with the
required addon/game/cache/output arguments. These are synthetic, original-file
Blender and package checks respectively; source assets are not distributed.

Next packet: P2, group edits by native source and publish staged bundles without
silent instance conflicts. Divergent shared-source edits and interrupted output
publication remain unresolved; this P1 pass does not claim a transactional writer.
