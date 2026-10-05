# Working in TTGames Workshop

Read the root README and the README/docs for the component being changed.
This repository contains multiple independent tools; do not assume one shared
game format, byte order, skeleton, material layout or build system.

- Keep extracted game assets, images, audio, scenes, archive keys, proprietary
  runtimes and private manifests under ignored `local/`. Never stage `local/`.
- Keep LSW1 original PC work separate from LSW2 and The Complete Saga readers.
- Treat CU3, AN4, NXG and DX11 version gates explicitly. Reject unknown layouts
  instead of creating guessed poses or writing malformed files.
- Preserve native bone names, hierarchy, bind transforms, scales and markers.
  Retarget rest-relative transforms rather than raw local Euler channels.
- Static shape targets start at zero. Do not modify the Basis or topology while
  writing existing GHG target payloads. Use the hash/layout validation already
  provided by the face editor.
- Native depth-only face surfaces require the render helper and compositor;
  solid viewport output is not a fidelity check.
- Do not change installed games, mods or edited drafts unless requested.
- Use appropriate component checks. Distinguish syntax checks, decoded round
  trips, visual checks and actual in-game validation in reports.
- Public tools accept user paths. Do not add personal absolute paths or depend
  on a particular AI application's runtime.
- Preserve component licenses and third-party attribution. Do not copy external
  repos or game engine source into this repository without license review.
- Update support notes when coverage changes. Keep documentation plain and
  clear; AI assistance is acknowledged in the README.
- After updating a Blender addon for this workstation, install the newest
  validated build into the user's current Blender profile and verify the
  installed version loads. Back up replaced files under ignored `local/`,
  preserve preferences and projects, and report if a restart is needed.
- Keep GitHub issue replies short: fixes, version/commit and remaining needs.
- Commit and push when requested. Do not create scheduled checks or automation.

The private historical workspace is documented in `docs/LOCAL_WORKSPACE.md`.
It includes scratch scripts that are not portable public tools. Use a new output
folder for experiments and preserve the latest validated scenes.
