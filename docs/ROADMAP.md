# Next steps

The [implementation handoff checkpoint](HANDOFF_P1_CHECKPOINT.md) records the
reproduced attachment rollback problem and the P1 dependency-revision fixes.
The [P2–P5 checkpoint](HANDOFF_P2_P5_CHECKPOINT.md) adds shared-source conflict
rejection, staged publication, bounded archives, explicit resource/skeleton
identity and stronger DDS/weight diagnostics. The next gate is original-file
regression of these stricter paths, then the remaining framing, ownership and
visual work in [the handoff](../TTGames_Workshop_Remaining_Handoff.md).

See the [workflow audit and milestones](WORKFLOW.md) for the current public
readers, remaining mesh-extraction dependencies and native editing limits.
The [5 October tool review](TOOL_REVIEW_2026-10-05.md) records the latest checks
and a more specific order of work. Current-game faces, materials, attachments
and cutscene completeness come before adding more game profiles.

- Improve native CU3 meshes, faces, materials, environments and shot playback.
- Extend verified cutscene character/object replacement and investigate custom
  animation writing without losing native skeleton or event semantics.
- Expand DCSV coverage with explicit version gates and original-file checks.
- Consolidate reusable model/texture readers as their layouts are verified.

The early LEGO Fortnite profile now accepts user-selected exported recipes and
baked models, with an optional installed-game extraction bridge. Broaden its
replacement-part and material coverage, recover source display names and finish
static facial atlas rendering. Roster discovery does not establish import or
visual accuracy. Keep character experiments, LOTDK mapping and external readers
private/separate; see [Fortnite coverage](../formats/fortnite/README.md).

The [BactaTank interoperability study](BACTATANK_INTEROP.md) describes a separate
independent `.bmesh` exporter proposal. It does not enable classic-game GHG
writing or reuse that project's implementation.
