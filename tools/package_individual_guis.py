"""Build independent GUI downloads with only their Python backend dependencies."""
import ast
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from workshop_gui import TOOLS, DEFAULT_TOOL_VERSION, TOOL_VERSIONS

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / 'formats/cu3/Addon/io_scene_lego_cu3'
PACKAGES = dict(zip(TOOLS, (
    'BTGA_Texture_Converter', 'LMSH1_AN4_Decoder', 'LMSH1_BVH_Exporter',
    'CU3_Dependency_Checker', 'Face_Target_Decoder', 'Face_Target_Writer',
    'TFA_Archive_Index', 'DCSV_Archive_Index')))
PACKAGES['CU3 Name Editor'] = 'CU3_Name_Editor'


def package_version(name):
    if name not in PACKAGES:
        raise ValueError('Unknown standalone GUI')
    return TOOL_VERSIONS.get(name,DEFAULT_TOOL_VERSION)


def dependencies(entry):
    """Follow local imports, including the headless CU3 package aliases."""
    found, pending = set(), [entry]
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            names = []
            if isinstance(node, ast.ImportFrom):
                names = [node.module] if node.module else [n.name for n in node.names]
            elif isinstance(node, ast.Import):
                names = [n.name for n in node.names]
            for name in names:
                if name.startswith(('io_scene_lego_cu3.', 'tt_dependency_check.')):
                    candidates = [ADDON / (name.rsplit('.', 1)[-1] + '.py')]
                else:
                    candidates = [path.parent / (name.replace('.', '/') + '.py')]
                pending.extend(p for p in candidates if p.is_file() and p not in found)
    return found


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool',choices=list(PACKAGES),help='Build only one independent tool')
    args=parser.parse_args()
    manifest_path = ROOT / 'builds/manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for name, slug in PACKAGES.items():
        if args.tool and name!=args.tool:continue
        version=package_version(name)
        is_editor = name == 'CU3 Name Editor'
        script = 'formats/cu3/scripts/cu3_name_editor_gui.py' if is_editor else TOOLS[name][0]
        files = dependencies(ROOT / script)
        if not is_editor:
            files.add(ROOT / 'tools/workshop_gui.py')
        files.add(ROOT / 'docs/LICENSING.md')
        description = ('Edit CU3 instance names and save a separate copy. Supports replacing every instance of a character.'
                       if is_editor else TOOLS[name][1])
        readme = f'''# {name}

Version {version}. {description}

Extract this entire ZIP, then double-click **Launch.pyw**. This opens only
this tool's GUI. No other Workshop download or Blender installation is needed.
Install Python 3.10+ with Tcl/Tk first (included in the usual Windows installer).
You can also run `python Launch.pyw` from this folder.

{'BTGA conversion also requires Pillow: `python -m pip install Pillow`.' if 'BTGA' in name else 'No third-party Python packages are required.'}

Browse for your own inputs and choose a new output name outside the game/input
folder. Output-folder fields use a save-style picker to name a NEW folder.
Wait for processing to finish before closing. Check the log and output
manifests for skipped/unsupported records, even when the process finishes.
Failed jobs may leave partial output; choose a new output name when retrying.

Game files and external tools are not included. Format support is limited to
the versions described above; a GUI does not expand decoder support.
AI was used to help with this project. See docs/LICENSING.md for reuse notes.
'''
        launcher = ("from pathlib import Path\nimport runpy, sys\n"
                    "base = Path(__file__).resolve().parent\n"
                    "sys.path.insert(0, str(base / 'formats/cu3/scripts'))\n"
                    f"runpy.run_path(str(base / {script!r}), run_name='__main__')\n"
                    if is_editor else f'from tools.workshop_gui import main\nmain({name!r})\n')
        target = ROOT / 'builds/python' / f'{slug}_GUI-{version}.zip'
        target.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(target, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(files):
                archive.write(path, path.relative_to(ROOT).as_posix())
            archive.writestr('README.md', readme)
            archive.writestr('Launch.pyw', launcher)
        record = dict(path=target.relative_to(ROOT / 'builds').as_posix(),
                      bytes=target.stat().st_size, sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        manifest['packages'] = [r for r in manifest['packages'] if r['path'] != record['path']]
        manifest['packages'].append(record)
        print(target.name, record['bytes'], 'bytes')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    from prune_builds import keep_latest
    keep_latest(apply=True)


if __name__ == '__main__':
    main()
