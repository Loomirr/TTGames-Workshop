# Skeleton and animation transfer

Independent, portable groundwork for transferring rigs between TT games.
Requires Python 3.10+ and this repository checkout; no Blender or external
extractor is needed for planning. Supplied assets stay outside the source tree.

**Current stage: read-only transfer plans, animation/item audits and a tested rotation-transfer API.**
This is not a universal native exporter. The private native weapon experiment
does not establish general GHG, AS or CPD writing support.

## Create a plan

```powershell
python tools/skeleton_transfer/plan.py --donor "Donor.GHG" --recipient "Recipient.GHG" --output "transfer-plan.json"
```

Use extracted, uncompressed GHGs accepted by the existing skeleton reader, or
decoded skeleton JSONs containing `joints`, their native indices/parents,
`local_bind_row_major` and `inverse_world_bind_row_major`. JSON references do
not prove native file layout or ownership. Unknown layouts and ambiguous GHG
ownership are rejected. Matching a file extension or joint count is insufficient.

The report records input hashes, native identities/selection, proposed name
matches, parent/rest/bind differences, unmapped bones, locator names and export
blockers. A name match is a proposal, not a confirmed retargeting map.
Reports use a new output path and never overwrite the source or installed game.

An explicit mapping uses this shape:

```json
{
  "bones": [
    {
      "source": "DonorRoot",
      "target": "RecipientRoot",
      "axis_bridge_row_major": [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
    }
  ]
}
```

Pass it with `--mapping mapping.json`. Each source and target occurs at most
once in this first implementation. Axis bridges must be proper rotations.
Choose them from measured source/target bone coordinate systems; the identity
matrix above is only an example. Unmapped targets are reported, and no pose is
fabricated for them.

Add supported standalone AN4 files with repeatable `--animation "clip.AN4"`
and an exact `--actor "NativeActor"`. The existing AN4 version/layout gates
remain unchanged. ANI-E receives structural inspection only. An actor name and
node count do not prove binding; the AS/CD resource and parent attachment still
need verification. This plan does not extract PAK/DAT entries or export animations.

## Rotation API

`rotation.transfer_local_rotation(source_rest, target_rest, source_pose,
axis_bridge)` accepts native row-vector matrices. It derives the source
rest-relative rotation, conjugates it through the explicit axis bridge and
applies it to the target rest transform. Target rest translation and scale are
retained. Source translation/root motion and animated scale need separate
policies. Scaled/sheared/reflected rotation deltas are refused.

The caller must establish joint identity and compatible mapped parents before
using this API. It is not a hierarchy solver, mesh fitter, animation encoder or
Blender preview importer. Raw local Euler copying is not used.

Run the portable checks:

```powershell
python tools/skeleton_transfer/test_transfer.py
python tools/skeleton_transfer/test_animation_audit.py
python tools/skeleton_transfer/test_item_routes.py
```

## Audit an edited native animation

```powershell
python tools/skeleton_transfer/animation_audit.py --source "Original.AN4" --candidate "Edited.AN4" --actor "NativeActor" --changed-bone 0 --output "animation-audit.json"
```

Both files must pass the existing standalone AN4 version/layout gates. Use
`--changed-bone` only for an intentionally edited native bone index; omit it
to compare all bones. The audit compares byte order, compression/channel flags,
clip starts, timing, record placement and auxiliary declarations. It samples
scalar channels every quarter frame by default and reports changes to bones
outside the declared edit. A changed bone does not excuse format or timing
changes. Use `--sample-step 1` if a large clip exceeds the sampling budget.

Reports never certify native export or game compatibility. Scalar angular
differences are not a world-space pose metric, and the audit does not validate
AS/CPD bindings, event execution or unknown fields in the runtime. Unknown
layouts and oversized comparisons fail without a report. Inputs and existing
reports are preserved. This inspection tool does not rewrite an animation.

## Inspect item action declarations

```powershell
python tools/skeleton_transfer/item_routes.py --items "Items.txt" --item "NativeItemName" --output "item-routes.json"
```

This read-only tool inspects the observed braced `item_type` text subset. It
lists action names, animation sets, combat flags and damage. It reports fight
actions without a `combo` flag or damage declaration as findings to compare
with the original game's item. These findings do not establish the cause of
missing attacks, and the tool never adds flags automatically.

Select an exact, unique item name. References resolve only within the supplied
text; external, duplicate, case-ambiguous or cyclic references remain unknown.
Commented-out declarations and orphan blocks do not supply an item's fields.
Quoted TT paths retain literal backslashes; `//` comments are supported. Block
comments, NUL bytes and malformed framing are refused. Other top-level syntax is reported
as uninspected. Input is UTF-8/ASCII, limited to 8 MiB with bounded tokens and
nesting. A new report is required; source and existing output are preserved.

This is not a general game-text parser. It does not resolve AS/CD/CPD resources,
decode motion, verify runtime inheritance/override order, or certify combat
events. A valid action name alone does not enable a combat item.

## Native transfer pipeline

See [the pipeline and current evidence](../../docs/SKELETON_TRANSFER.md).
Native writers should be separate, explicitly gated profiles. Each must
rebuild palettes, all LOD ownership, bind-space mesh data, bounds, section
lengths, animation routing and attachments as a coherent job. Successful
decoding, Blender playback and target-game testing are separate milestones.
The tool should eventually accept a job manifest and output extracted source
files, never rewrite DAT archives or silently modify an installation.
