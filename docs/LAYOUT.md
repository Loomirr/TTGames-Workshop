# Project layout

```text
formats/       Readers, importers, exporters and their format-specific docs
games/         Game-specific entry points
tools/         Manual repository check tools
docs/          Overall support, licensing and local workspace notes
AGENTS.md      Instructions for AI-assisted work in this repository
local/         Private game assets, scenes, dependencies and historical projects
```

Each tool remains independently installable/buildable. We are not combining
the addons into one addon or changing their native readers in this migration.

The earlier TT-Cutscene-Importer and LSW1HGPBlenderImportAddon repositories
remain separate upstream projects. This repository contains a source snapshot
of their latest local work; future updates must be explicitly synchronized.
Their historical Git checkouts are preserved locally, not nested in this repo.
