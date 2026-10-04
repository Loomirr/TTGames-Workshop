# Next steps

See the [workflow audit and milestones](WORKFLOW.md) for the current public
readers, remaining mesh-extraction dependencies and native editing limits.

- Improve native CU3 meshes, faces, materials, environments and shot playback.
- Extend verified cutscene character/object replacement and investigate custom
  animation writing without losing native skeleton or event semantics.
- Expand DCSV coverage with explicit version gates and original-file checks.
- Consolidate reusable model/texture readers as their layouts are verified.

LEGO Fortnite is a possible later addition. Keep the current character-specific
experiments private until the tool accepts user-selected LEGO characters and
can extract their meshes, textures, variants and material data. Check several
different characters before adding it publicly, document any unsupported paths,
and retain third-party dependencies externally. The first version contains no
Fortnite tools, LOTDK mapper or suit/character project scripts.
