# Cross-game skeleton and animation transfer

The [transfer planner](../tools/skeleton_transfer/README.md) is the first
portable component: it inspects gated native rigs or decoded references,
checks proposed mappings and inspects supported AN4 actors. A separate
rest-relative rotation API handles explicit bone-axis bridges. It currently
does not write a transferred native model or animation.

## Two different operations

**Skeleton transplant:** keep the donor's bone names, hierarchy, orientation,
rest/bind transforms, scale and markers. Adapt the recipient mesh's bind space,
skin weights, palettes, draw ownership and every LOD to that rig. The donor's
animations still need a matching animation/resource/attachment route in the
target game.

**Animation retarget:** keep the target's native rig and transform the source
motion through an explicit bone map and measured coordinate bridges. Transfer
rest-relative rotations. Treat root motion, scale, extra bones, IK and object
attachments separately. Extra trailing bones do not alone establish
incompatibility; equal bone counts also do not establish compatibility.

Neither operation is equivalent to renaming a skeleton or changing a file path.

## Whole-job validation

1. Retain source hashes and exact game/platform/layout identities. Resolve
   skeleton ownership before selecting by animation node count.
2. Preserve an explicit bone map and measured axes, plus unmapped-bone policy.
   Reject unresolved parent changes rather than creating guessed local poses.
3. For a transplant, validate every native variant and draw/skin table. Rebuild
   mesh palettes, weights, bind-space geometry, bounds and enclosing lengths.
   Preserve unrelated materials, textures, topology and opaque fields.
4. Trace action bindings separately for body, weapon, face and other objects.
   A weapon track must not replace the body's action core. Names can occur in
   GHG roots, AN4 actors, AS entries, CPD slots and item definitions; they have
   different meanings and must be matched by ownership. Inspect the item combat
   declarations and inherited fields as well: fight action names alone do not
   establish combat activation. The read-only item audit reports missing flags
   and unresolved references without supplying guessed game settings.
5. Check an attachment's actual animated grip reference. A fixed offset fitted
   in one pose can fail when the grip bone rotates in another. A coherent root
   correction or calibrated attachment transform should move the whole object;
   shifting only endpoint vertices can tear its connection to the chain.
6. Decode output again. Check original data outside declared edits, every
   sampled clip, loop seams, root motion, attachment contact and error bounds.
   Record any loss of interpolation, event/auxiliary data or source rendering.
   Compare native byte order, compression/channel flags and segment start/end
   declarations separately. Integer-frame agreement can hide substantial
   motion changes between frames. Use the read-only animation audit before
   testing an edited clip in-game.
7. Save a new Blender viewing copy and inspect several clips/poses/LODs. Test
   selection, idle, walk, run and attacks in the target game. Keep backups and
   describe runtime results separately from decoded/visual checks.

## Current native experiment

Private supplied-asset work has transplanted an eleven-bone Dimensions weapon
rig onto a nine-bone Ninjago flail mesh. All three recipient rig variants retain
the exact donor joint records; mesh weights and bind-space fitting were rebuilt.
The user reported a working load and weapon motion in Ninjago and, after
attachment-slot alignment, DCSV. These tests still showed grip/body-action
problems and are not full fidelity certification.

A subsequent combined candidate **failed in DCSV**: the user reported many
broken animations and a crash during a combo. Its installer is disabled, and
the isolated test copy was restored to the supplied original animation files.
Decoder and Blender passes did not establish runtime safety.

Review found that the experiment changed all 33 weapon ANI-D blocks from
big-endian to little-endian, reset nonzero segment start declarations, changed
compression flags and enabled previously inactive channels. Quarter-frame
sampling also found up to about 0.85 radians of difference in an unrequested
angular channel despite close integer-frame samples. These are confirmed
export regressions; the exact runtime crash cause has not been isolated.
The body/face payloads were unchanged, but that did not certify simultaneous
body/weapon action routing.

A separate diagnostic retains the original 26 AN4 files byte for byte and
tests only the attachment-binding changes. The user reported no crash or
broken weapon motion in this test, and almost-correct hand placement. The
intended body attack animations still did not play. This is a useful runtime
baseline, not certification of every action or full fidelity. The v33 AS list
reconstruction also passes extent/count checks and exact undo to the source;
structural checks alone do not establish runtime semantics.

Inspection found that the active experimental item declares five fight actions
but lacks the combat flags and damage declared by the original nunchucks item.
A new item-only candidate restores `combo`, `sword` and `damage 50`, preserving
the stable rig, attachments, AS files and all original compressed AN4 motion.
It passes static declaration and dependency/hash checks; its runtime result is
pending. The missing flags are a configuration finding, and their role in the
absent body attacks remains an inference until tested.

Hand placement and the clips with changing grip orientation remain unresolved.
Judge grip contact while the intended body and weapon motion play together
before calibrating offsets. The grip centroid used in these experiments is a
diagnostic reference, not an authored hand locator.

The Dimensions body clips have 63 nodes. The inspected DCSV full-detail body has
65, with `impact1` and `impact2` at the end. This count difference alone is not
an incompatibility finding. Users report that Dimensions animations work in
DCSV. Exact donor/target body hierarchy equivalence has not yet been checked
because the donor shared body GHG was not supplied.

The private experiment uses compact HGOL arrays, v17 AN4 and v33 AS framing
outside current public reader/writer coverage. Hash-gated experimental edits
are not a reason to relax public gates. No game assets, private native writer,
test installation or character-specific output is included in this repository.

## Next implementation gates

The next reusable pieces are measured grip calibration, Blender preview jobs
and a transfer manifest containing rig identities, bone/part mappings, clip
bindings, root policy, attachments and a change list. Native export profiles
need separate schema validation and multi-file original-game samples before
they become public. Reuse existing gated readers and source-format editing
checks; do not import external tools or engine code. Export loose original
source formats into a new directory, following the extracted-game workflow.
