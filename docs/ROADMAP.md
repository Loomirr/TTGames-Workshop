# Next steps

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
