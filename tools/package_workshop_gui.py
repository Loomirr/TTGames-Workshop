"""Package only our GUI and Python backends; no runtime or game assets."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def markdown_for_package(path, included):
    """Keep offline links when bundled; send other repo links to the source."""
    def link(match):
        parsed = urlsplit(match.group(2))
        if parsed.scheme or parsed.netloc or not parsed.path:
            return match.group()
        resolved = (path.parent / unquote(parsed.path)).resolve()
        if resolved in included or not resolved.is_relative_to(ROOT) or not resolved.exists():
            return match.group()
        url = 'https://github.com/Loomirr/TTGames-Workshop/blob/main/' + resolved.relative_to(ROOT).as_posix()
        if parsed.fragment:url += '#' + parsed.fragment
        return match.group(1) + url + match.group(3)
    return re.sub(r'(\[[^\]\n]*\]\()([^\s)]+)(\))',link,path.read_text(encoding='utf-8'))


def main():
    from workshop_gui import VERSION, TOOLS
    files = {ROOT / name for name in (
        'Launch Workshop GUI.pyw', 'tools/workshop_gui.py', 'tools/WORKSHOP_GUI.md',
        'docs/LICENSING.md', 'docs/DIAGNOSTIC_TOOLS.md', 'docs/CHARACTER_ACCURACY_0.5.9.md', 'README.md', 'formats/cu3/scripts/cu3_name_editor.py',
        'formats/cu3/scripts/cu3_name_editor_gui.py', 'formats/btga/3ds/pica_texture.py',
        'formats/btga/3ds/FORMAT.md', 'formats/cu3/scripts/inspect_archive_cc.py',
        'formats/cu3/scripts/inspect_skeleton_candidates.py',
        'formats/cu3/scripts/inspect_material_declarations.py')}
    files.update(ROOT / data[0] for data in TOOLS.values())
    # Headless CU3 helpers import sibling parser modules, bypassing Blender's entry point.
    files.update((ROOT / 'formats/cu3/Addon/io_scene_lego_cu3').glob('*.py'))
    for area in ('formats/cu3', 'formats/an4/lmsh1', 'formats/btga/3ds'):
        files.add(ROOT / area / 'README.md')
    files.update((ROOT / 'formats/cu3/docs').glob('*.md'))
    target = ROOT / 'builds/python' / f'TTGames_Workshop_GUI-{VERSION}.zip'
    target.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(target, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(files):
            if path.suffix not in ('.py', '.pyw', '.md'):
                raise ValueError(f'Unexpected package file: {path}')
            name = path.relative_to(ROOT).as_posix()
            if path.suffix == '.md':
                archive.writestr(name,markdown_for_package(path,files))
            else:archive.write(path,name)
    manifest_path = ROOT / 'builds/manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    relative = target.relative_to(ROOT / 'builds').as_posix()
    manifest['packages'] = [r for r in manifest['packages'] if r['path'] != relative]
    manifest['packages'].append(dict(path=relative, bytes=target.stat().st_size,
                                    sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    from prune_builds import keep_latest
    keep_latest(apply=True)
    print(target, target.stat().st_size, 'bytes')


if __name__ == '__main__':
    main()
