# Standalone tool GUI

Version 0.1.3. A small native Tkinter window with browse buttons, forms and a
live log. No browser, server or extra GUI framework.

**Separate downloads are now available for each tool** in
[builds](../builds/README.md#separate-gui-downloads). Each includes its own
backend and opens directly to its form using `Launch.pyw`, without a tool
selector. The instructions below describe the optional combined toolbox.

For direct character/animation import inside Blender, use the separately
installable [character addon](../formats/character/README.md), rather than
the desktop AN4 decoder/BVH exporter. The Blender addon creates native rigs
and a clip list directly; the desktop utilities write intermediate files.

Install Python 3.10 or newer with Tcl/Tk enabled (included in the usual Windows
Python installer). Extract the whole download, then double-click
`Launch Workshop GUI.pyw`. From a terminal you can also run:

```sh
python tools/workshop_gui.py
```

For BTGA texture conversion only, install Pillow into that same Python:

```sh
python -m pip install Pillow
```

Choose a tool, browse for inputs, enter a **new output name**, then click
**Run tool**. For output folders, the save-style picker names a new folder;
do not select an existing one. Keep output/cache folders outside source trees
and game installations. **Open output folder** opens the result location.
The UI stays responsive during processing. Wait for the job to finish before
closing; this first version does not offer cancellation. Failed jobs can leave
partial output, which is never silently overwritten on retry.

## Included forms

- 3DS BTGA to DDS/PNG: already-decompressed, observed Universe in Peril records.
- LMSH1 AN4 decoder: exact actor name and original 63-joint skeleton required.
- Decoded LMSH1 animation to experimental BVH: transformation preview only.
- LB3/LMSH1 CU3 dependency report: game folder and separate companion cache.
- Native face target decode: supported original GHG only; no extraction log is needed in decoder 0.1.2. Older downloads required a plain-text model-extractor log containing mesh part offsets and vertex counts. Target JSON is the output, not that log.
- Native face target write: verified edited-target JSON into a separate GHG.
- TFA CC8 and DCSV CC4 archive indexes: path listings, not full extraction.
- A button opens the existing CU3 instance-name editor in its own window.

Format support is unchanged from the command-line tools. A finished process
does not mean every record was supported: check the log and output manifests.
Face writing remains experimental, and is not a visual shape-key editor.
See the included component READMEs/docs for limitations and input preparation.

Manual checks from the repository root:

```sh
python tools/test_workshop_gui.py
python tools/test_individual_guis.py
```

The six toolbox checks exercise forms, a BTGA job and output protection. The
nine standalone-package checks extract the current per-tool version and open
its launcher with windows hidden, then import its own backends. They do not
prove format fidelity or execute every backend on real game data. The toolbox
0.1.1 package keeps bundled documentation links offline when possible and
points links to omitted repository files at their online source.

The **LIJ1 Xbox 360 extractor already has its own GUI**, including file/folder
drag and drop. Download its Windows ZIP separately from the repository's
`builds/windows` folder and run `LIJ1_360_Texture_Extractor.exe`.
This toolbox uses file pickers; shell drag and drop is not implemented here.

Version 0.1.3 packages the bounded archive and resource-identity readers used by
the relevant backends. See [validation review](../docs/MERGE_PACKET_REVIEW_2026-10-06.md)
for safety changes and the distinction between backend and interactive GUI checks.

Developer checks, Blender-only scripts, raw FUSE access and the native Python
PAK helper are not wrapped in this GUI.
No external extraction programs, Python runtime or game assets are bundled.
