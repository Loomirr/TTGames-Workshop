# Shared model validation and compatibility reporting

Character 0.5.4 and CU3 0.1.13 add a shared validation boundary between decoded
native data and Blender object creation. It applies to the existing NXG/DX11
readers by structure, without character-name conditions. It does not enable
unknown file versions or change source geometry, skin weights or bind poses.

## Import stages

The shared loader reports failures as mesh decoding, display decoding, skeleton
decoding, material decoding or decoded model validation. Selected draws then
validate mesh/material references and rigid/skinned skeleton associations
before Blender objects are created. Static instance matrices are checked before
coordinate conversion. Existing importer rollback still removes a failed
import's new objects and restores the previous scene.

The existing binary readers already bound many references and reject non-finite
vertex values. The new layer also checks consistency across decoded attributes,
singular bind transforms and selected associations. In particular, negative
material/bone indices previously escaped upper-bound-only checks and could
select the last Python table entry. They now fail explicitly. A selected skinned
vertex must have a positive valid influence; rigid parts do not require vertex
weights. No global bone count, character scale threshold or topology repair is
introduced.

Quality observations, including empty parts, repeated triangle indices and
non-unit decoded weight sums, are warnings. They do not normalize weights,
weld vertices or discard parts. Some empty/degenerate source data is deliberate;
warning counts are evidence to investigate, not a claim that the asset is broken.

## Finding the report

Open the import report in Blender's Text Editor. Each character model has a
`validation` entry. CU3 reports include `model_validation` for actor models and
a validation entry on successfully decoded static stage resources.

The `tt.model-validation.v1` record includes MESH, DISP, HGOL and material table
versions, joint counts, per-part attribute/triangle/vertex/target counts and
stage-labelled warning counts. The game profile and asset source remain in the
outer import report. Unknown shader bytes already retained by the material
reader remain available; this report does not establish a complete accounting
of all unknown file sections or shader behavior.

## Checks and limits

Independent fixtures exercise malformed triangle/UV data, non-finite values,
negative references/weights, invalid parents, singular matrices, rigid versus
skinned associations and warning-only preservation. A Blender audit reimports
sixteen existing samples across LMSH1, The Hobbit, LB3 and Avengers, creates
independent live previews and verifies unchanged native vertex exports.
All sixteen passed. Eleven independent test cases and the repository checks
also passed. Source meshes with repeated triangle indices are retained and
reported; these warnings are not automatically treated as import failures.
This pass uses static poses; it does not add animation or facial fidelity
coverage beyond the previous release. Installed-game CU3 checks remain separate.
The LB3 Batcave hub intro and LMSH1 Stark Tower intro also passed their normal
import operator checks, including actor/camera assembly, packed textures and
the new validation report records. These are assembly checks, not a fresh
frame-by-frame comparison against game playback.

Structural validation makes format failures easier to locate. It cannot prove
correct materials, exact face masking, correct scale relative to the game or
complete character assembly. Future support should add verified readers and
structural capabilities, with tests at the stage that introduced the problem.
