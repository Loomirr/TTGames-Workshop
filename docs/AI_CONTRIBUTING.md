# Using AI to contribute

A repository link is useful context, but it is not a complete task. Give the
session an observable problem, permission to work on the code, and a definition
of success. Some sessions can browse a link but cannot clone a repository, edit
files, run Python or launch Blender. Establish those capabilities first.

No special model or secret prompt is required. Instructions files are not
necessarily loaded by every client, so explicitly ask the session to read
[AGENTS.md](../AGENTS.md) and [CONTRIBUTING.md](../CONTRIBUTING.md).

## Coding agent with a repository checkout

Replace the bracketed fields before sending this:

```text
Work on https://github.com/Loomirr/TTGames-Workshop.

Task: [one specific bug, issue URL, or format feature].
Game/platform: [exact game and platform].
Tool/version: [addon or CLI version, Blender version if relevant].
Reproduction: [input logical filename, steps, error or visible problem].
Expected result: [what should happen].
Available local inputs: [my game/extracted folder and sample paths, or none].

Inspect the actual repository code. If you have no checkout, clone my fork or
this repository into a new directory. If a checkout already exists, check its
status and preserve local changes. Read AGENTS.md, CONTRIBUTING.md and the
component's README before editing. Check the latest issue/PR discussion if
available; do not assume old reports describe the current code.

Reproduce the problem, identify the cause, implement a focused reusable fix,
and add a meaningful regression. Run the relevant checks as you work. Continue
through implementation and verification rather than stopping with a plan.
Do not bypass format/ownership/path checks to make an input appear to work.
Keep native skeletons, topology and unsupported data intact as required by the
component. Do not modify my installed game or upload game assets.

Use original-file tests and inspect rendered images when they are available
and relevant. State exactly which checks ran, what passed, what failed, and
what remains unverified. Update support notes if coverage changes. If files
or execution tools are missing, explain that and complete useful source or
synthetic-test work without inventing results.

Deliver a reviewable diff and concise validation report. Do not commit, push,
post comments, install addons, or change my game unless I separately authorize
those actions. Do not include extracted assets, scenes or private reports.
```

The last paragraph is a safe starting point for a new contributor. They can
explicitly authorize a branch, commit, PR or addon installation when ready.
Their session's direct instructions take precedence over this example prompt.

## If your friend does not know what to work on yet

```text
Review the open issues and PRs in https://github.com/Loomirr/TTGames-Workshop
and inspect the current source after reading AGENTS.md and CONTRIBUTING.md.
Identify three bounded tasks that have not already been fixed. For each,
explain the affected component, evidence, missing inputs and a concrete test.
Recommend one that can be reproduced with the tools and files available here.
Do not change source or post to GitHub yet. Tell me whether you can actually
edit a checkout and run tests, or only review code in this session.
```

Once they select a task, use the implementation prompt above. Broad requests
like "improve every game" are a long-term direction, not a useful first test.
A good first task might improve a reproduced rejection diagnostic or correct
one proven layout, with tests that keep other layouts and malformed files safe.
Consult current issues before choosing an example; it may already be fixed.

## Chat-only or browser-only sessions

If the session cannot execute code, use a narrower review request:

```text
Review this specific issue in TTGames Workshop: [issue URL and symptoms].
Read the current AGENTS.md, CONTRIBUTING.md, component README and relevant
source/tests from [commit SHA or supplied source snapshot]. Tell me if you
cannot access those contents; do not infer code from filenames or the README.

Identify the likely cause with file/function references and distinguish
observations from hypotheses. Propose a focused patch and regression tests
against that exact source revision. State all tests as not run unless you
actually execute them. List the original files or runtime evidence needed
for verification. Do not claim the issue is fixed from code review alone.
```

If it cannot read the repository at all, provide the relevant source files and
a commit identifier. Do not substitute proprietary game files for missing code.
When handing a patch to another session, include the base commit, changed files,
reproduction, test commands/results, and outstanding questions. The receiving
session should inspect the full diff and preserve newer work before applying it.

## What to send with a bug

- Game/platform and current addon or CLI version.
- Input's logical filename and relevant layout/version identifiers, if known.
- Minimal reproduction and the full error text.
- Expected behavior and a reference for the difference.
- For visuals: preview mode, clip/frame, and whether the scene is a fresh import.
- Which inputs and runtimes are available locally, without publishing game assets.

Private machine paths may be useful inside your own session, but remove them
from public reports. A screenshot helps establish a symptom; it does not by
itself prove a byte layout, material meaning, bone mapping or animation owner.

## How to judge the result

A useful result has a small reviewable diff, a reproduced failure, relevant tests,
and honest limits. Ask for separate evidence for decoding, Blender import,
visual fidelity, edited round trips and in-game use. One successful character
is not evidence of universal support, and a test that checks the same guessed
constant as the implementation does not validate the guess.

If the session keeps discussing the repo without acting, say:

> Please inspect the relevant source and reproduce this specific issue now.
> If you can edit and run tests, implement and verify the fix. Otherwise, tell
> me which capability or input is missing and provide a review against an
> identified source revision. Do not report an unexecuted check as passed.
