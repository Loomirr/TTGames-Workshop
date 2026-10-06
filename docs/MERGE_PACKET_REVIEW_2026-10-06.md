# Merge packet workstation review — 6 October 2026

## Integration status

The reviewed Astra packet and local corrections were transferred into the main
checkout, at the user's request, for the subsequent source commit. The temporary review
worktree and local branch were removed after preserving the validation files.
The review base was `3c3da56fa18a797b056d475a99d46b35a9df7e03`; main was clean
before transfer. The user subsequently authorized committing and pushing this
checkpoint. No installed-game change or addon installation was performed.
The candidate is **not ready to replace the
previously validated character and cutscene builds**.

All 100 packet SHA-256 records and 89 changed paths verified. The full binary
patch applied cleanly with strict whitespace checking. Its staged tree was
exactly `ed29b7fb030c4efbfb4c41415d78d936aae02d7e` before local corrections.
The eight superseded ZIP removals were reviewed with their replacements and
manifest. No private assets or external programs were added.

## Local corrections

- Archive mutation stamps now consistently use open-handle metadata. Windows
  path metadata lagged handle timestamps after fixture rewrites, falsely
  rejecting unchanged archives. Device, inode, size and both timestamps remain
  checked; the mutation guard was not removed.
- LB3/Hobbit parent-index readers recognize the nameless record-zero root with
  negative name offset and parent `0xffff`. All nine installed DATs exhibit
  this convention. Other unresolved parents still reject.
- Synthetic exporter tests use canonical path keys on Windows rather than
  assuming Linux spelling survives canonicalization.
- The original-file duplicate fixture supports static roots without datablocks.
  A static specimen still needs editable UVs to complete its intentional-edit
  check; the sampled Wolverine hair has none.

Two archive regressions cover handle stamps and the root sentinel. Packages
containing the corrected shared archive reader were refreshed, with updated
manifest hashes. Candidate version numbers remain 0.5.7 and 0.1.16 on this
main-checkout source checkpoint.

## Checks and results

| Check | Result | Scope |
| --- | --- | --- |
| Repository suite | 388 cases passed | Syntax/config, portable readers/writers, docs, current-build policy and package integrity |
| Blender extracted packages | Passed on Windows Blender 5.2.2 | Both addons register together; 55 modules each; defaults and unregister checked |
| Authored normals | Passed; error 0.003922 | Synthetic helper, not original shader parity |
| Preview isolation/settings | Passed | Synthetic authored/skinned normals and reversible controls |
| Facial compositor | Passed | Synthetic render, not game fidelity |
| Thrain standalone face P2 | Passed | Original extracted GHG, byte-identical no-op/reimport, identical instances, both conflict orders, divergent edits, decoded UV edit |
| Wolverine default PAK | Passed | All 27 original members decoded; 885,627 decoded bytes; staged extraction verified and published on Windows |
| Original texture/material/model audit | 27 of 35 complete checks passed | 18 TEX and six texture stores passed DDS bounds; two GSC and one face GHG passed; eight GHG ownership checks refused |
| Full representative character P2 checks | Blocked | Wolverine, Batman and Thrain body skeleton ambiguity; installed Avengers index trailer refusal; extracted Avengers also confirms skeleton ambiguity |
| LB3/LMSH1 CU3 checks | Not a successful scene regression | Original installed-DAT CU3s recovered 4/13 cameras but zero actors; native skeleton refusals recorded |

Additional private preview-sample imports, with default static stage enabled,
also returned zero actors and camera setups. An operator returning `FINISHED`
with warnings is not evidence of successful actor reconstruction. Initial test
invocation errors and sandbox rename failures are retained in private logs;
the corrected final checks above are the authoritative results.

## Remaining blockers

1. **Skeleton ownership:** normal original shared bodies contain several HGOL
   candidates. Some differ in bind tables; face/cape candidates can have equal
   binds but different ownership metadata. Display validation currently accepts
   multiple candidates, and import does not yet supply a proved retained
   identity to select the intended one. Keep the refusal; decode resource/layer
   routing rather than selecting the first table or using joint count alone.
2. **Avengers CC index suffix:** original DAT indexes contain substantial data
   after the packet's parsed tables, including ROTV-tagged data. The new exact
   consumption gate rejects it. Bound and decode the additional grammar before
   enabling it; do not treat arbitrary suffix bytes as harmless padding.
3. **Attachment animation ownership:** full character/linked-track validation
   is blocked upstream by skeleton selection. Passing synthetic ownership tests
   does not establish that every original attachment is matched correctly.
4. **Original-file export coverage:** the unique face proves the P2 path on a
   real specimen, but full body export and edited-file gameplay remain unproved
   for this candidate. No new original-versus-game visual comparison was made.
5. **Archive/DDS breadth:** current original samples pass DDS bounds and one
   original PAK passed complete decoding/publication. Other banks, numerical
   FourCC policies, padded rows, enclosing TEX/TXTS grammar, LOTR mode 3 and
   unknown layouts remain gated or unverified.

Keep Character 0.5.6 / CU3 0.1.15 installed until these regressions are resolved.
The workstation rule to install the newest validated addon does not make a
candidate with failed original character imports a validated replacement.

## Independent exporter plan

[BACTATANK_INTEROP.md](BACTATANK_INTEROP.md) remains a research plan, not an
implemented exporter. Start with an independently authored static `.bmesh`
subset and independent strip decoder, then prove destination `.barm` identity,
axes, palette/weight budgets and target capacities before skinned export.
Replacement/save/reopen and in-game checks are separate gates. No BactaTank
code, addon, executable or strip algorithm was copied or translated.

Private logs, original identities, copied specimens and fresh outputs are under
ignored `local/validation/astra-merge-20261006/` in the main checkout. Package hashes
in `builds/manifest.json` describe the corrected candidate; the packet's original
hashes describe its pre-review artifact.
