# Contributing to TTGames Workshop

Contributions from people using AI are welcome. The same requirements apply:
understand the changed behavior, preserve attribution, and report what was
actually checked. Start with [AGENTS.md](AGENTS.md) and the component README.
For a ready-to-paste task, use the [AI contribution guide](docs/AI_CONTRIBUTING.md).

## Choose a concrete task

Follow the [era development order](docs/ERA_DEVELOPMENT.md) for new compatibility
work. Early Classic is active; regressions in existing later-era tools can still
be fixed. Record exact game/platform/release/layout evidence before calling a
format or workflow complete.

Include the [shader and facial completion items](docs/VISUAL_AND_FACE_COVERAGE.md)
in every game record. Report shader accuracy, face assembly, facial playback and
native export separately; an approximate preview does not establish 1:1 support.

Pick one reproducible bug or one clearly identified format layout. Check existing
issues and PRs before duplicating work. Include the game, platform, tool version,
input's logical filename, expected result and actual result. For a visual bug,
include the preview mode and animation clip/frame. Do not upload game archives,
models, textures, keys or saves to this repository.

Useful contributions include a failing synthetic test, a measured format note,
a better unsupported-layout diagnostic, or an original-file test report. You do
not need to claim full game support to contribute something useful.

## Set up and locate the source

```text
git clone https://github.com/Loomirr/TTGames-Workshop.git
cd TTGames-Workshop
git status --short
```

Fork the repository if you will submit a PR without write access. Use your own
branch for contributions; preserve any existing working changes. There is no
single repository-wide install command. Python tools, Blender addons and the
.NET extractor have separate requirements; consult their READMEs. Use your own
Python/Blender installation, not the maintainer's private paths.

The root [support table](README.md#game-and-file-support) describes current
coverage. Shared readers live in `formats/cu3/Addon/io_scene_lego_cu3/` and are
bundled into the Character addon by its build script. Do not edit generated
copies to fix a shared reader. Keep private input/output under ignored `local/`.

## Test the relevant behavior

| Check | What it establishes |
| --- | --- |
| `python tools/check_docs.py` | Markdown encoding and local links; not the truth of coverage claims |
| `python tools/check_repository.py` | Manual source, portable regression and existing package-integrity checks; not game fidelity |
| Component tests | The specific parser, guard, conversion or UI behavior being changed |
| Packaged Blender check below | Package imports, registration and handler routing in the tested Blender version |
| Original-file decoding/import | Behavior on the named original samples, not an entire game |
| Inspected renders and animated frames | Visible results under the stated preview/render settings |
| In-game test | Behavior in the exact game build and test scenario |

```text
blender --background --factory-startup --python-exit-code 1 --python tools/check_blender_packages.py
```

That command checks built ZIPs, not unbuilt source edits. Use the component's
source tests while developing, then rebuild before package checks. The current
ZIPs in `builds/` allow a fresh clone to run the registration check. Original-file
tests are separate and require your own game files. Run Blender tests with a
separate temporary user profile when possible; never overwrite your projects.

A practical check sequence is: reproduce, add a regression, fix the source, run
the affected tests, run the repository/docs checks, then perform the relevant
original-file and Blender checks. For a decoder, sample both the newly accepted
layout and already-supported layouts. For an exporter, verify unsupported edits
are still refused. If you cannot run a check, list it as **not run** and why.

If a test cannot write to the system temporary directory, choose a fresh writable
test directory through your environment's `TEMP`/`TMP` settings. Do not remove
path protections or change application behavior to work around a local test setup.

## Builds and review

For Character packaging use `python formats/character/build_addon.py`. For CU3
use `python formats/cu3/scripts/build_addon.py`; its output is under the ignored
component `dist/` directory. Read [HGP build instructions](formats/hgp/lsw1/README.md)
for that extension. Maintainer packaging uses `tools/package_builds.py --blender`
with the local Blender executable; it packages HGP/CU3 and updates the build
manifest. Shared-reader releases also need the Character package rebuilt.

Coordinate version bumps and binary builds with the maintainer. A source-only PR
is fine when it clearly states that distributable ZIPs have not been rebuilt.
Do not hand-edit ZIPs or delete an old build without its validated replacement.
Do not run every packaging script for an unrelated change.

In your PR, describe the problem, resulting behavior, scope, evidence and remaining
limits. Name source commits when incorporating research and retain licenses.
List exact test commands and outcomes, including unavailable checks. Include no
private paths or proprietary assets in public logs. Keep claims such as
"all characters" or "fully accurate" out unless the evidence actually supports them.

AI-generated changes need the same review. Inspect the diff before submitting,
including unexpected files and dependencies. A plausible explanation or generated
test report is not evidence that a tool was run. See [licensing](docs/LICENSING.md).
