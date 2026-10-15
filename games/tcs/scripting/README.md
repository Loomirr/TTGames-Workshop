# TCS PC scripting guide

Research revision: 14 October 2026.

TCS uses several text-driven systems. Its AI `.SCP` files describe state
machines that call native conditions and actions. Character definitions,
collection lists and level settings have their own command vocabularies.
Sharing a text extension does not make their commands interchangeable.

## Reading order

1. [AI language](AI_LANGUAGE.md): states, transitions, arguments, parameters,
   referenced scripts and original worked examples.
2. [Command reference](COMMANDS.md): commonly observed commands and the
   bounded native core registration tables.
3. [Character and level integration](INTEGRATION.md): where scripts fit,
   resource dependencies and TXT definitions.
4. [Character authoring](CHARACTERS.md): identity, categories, inherited
   definitions, animation declarations, collection prices and unlock gates.
5. [Native colors and effects](COLORS_AND_EFFECTS.md): stock saber colors,
   weapon streaks, Force rendering and hilt selection.
6. [Icons, capacities and resource lifetime](ICONS_AND_LIMITS.md): portrait
   names, bundles, caches, save limits and performance.
7. [Native recipes](RECIPES.md): practical editing and level-script patterns.
8. [Testing and research evidence](RESEARCH.md): troubleshooting, reproducible
   checks, native addresses and remaining unknowns.

## Which file am I editing?

| File family / typical location | Role | Use these notes |
| --- | --- | --- |
| `SCRIPTS/*.SCP` | Shared AI behaviours | AI language and command reference |
| `LEVELS/<episode>/<level>/<area>/AI/*.SCP` | Area-specific AI and level logic | AI language, plus level resource dependencies |
| `CHARS/CHARS.TXT` | Character registrations | Integration |
| `CHARS/COLLECTION.TXT` | Collection/shop declarations | Integration |
| `CHARS/<directory>/<character>.TXT` | Character properties and animation mappings | Integration |
| `STUFF/TEXT/ENGLISH.TXT` | Localized text ID mappings | Integration |
| Area `.TXT` files | Rendering, allocations, doors and other area settings | Integration; not the SCP grammar |
| `.GSC`, `.GHG`, `.GIZ`, `.AN3`, `.CU2` | Binary scenes, models, gizmos, animations and cutscenes | [Classic PC tools](../../../formats/classic-pc/README.md) |
| `.PAK` / `.DAT` | Packaged resources | Asset-loading context; not interchangeable with loose scripts |

## Evidence levels

- **Native:** checked in the analyzed PC executable's parser or registration
  tables. This establishes the stated code fact, not that every use works in-game.
- **Observed:** found in supplied installed scripts or definitions. The tree
  contains mods, backups and possibly unused content; an occurrence alone does
  not prove the engine accepts it or the game loads that file.
- **Example:** newly written teaching material using observed syntax. Examples
  have not been gameplay-tested and are not drop-in level replacements.
- **Open:** a question that needs further parser/runtime tracing or a controlled
  game test. No undocumented semantics should be inferred from a command name.

This guide covers the unmodified native PC game. It documents existing text
interfaces and their engine constraints; it introduces no new directives.
Source assets and decompiler output remain private; the guide contains
descriptions, identifiers and small original examples rather than game scripts.
