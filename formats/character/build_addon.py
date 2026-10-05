"""Build the independent character addon from our UI and shared native readers."""
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from package_individual_guis import dependencies, ADDON


def main():
    files = set()
    for name in ('an4', 'native_model_blender', 'costume_materials', 'asset_index', 'dependencies', 'blender_import'):
        files.update(dependencies(ADDON / (name + '.py')))
    target = ROOT / 'builds/blender/TT_Character_Importer_0.1.0.zip'
    prefix = 'io_scene_tt_character/'
    with ZipFile(target, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted((ROOT / 'formats/character/Addon/io_scene_tt_character').glob('*.py')):
            archive.write(path, prefix + path.name)
        for path in sorted(files):
            if path.parent != ADDON:
                raise ValueError('Unexpected shared dependency')
            archive.write(path, prefix + '_core/' + path.name)
        archive.writestr(prefix + '_core/__init__.py', '"""Bundled shared native readers; no separate addon registration."""\n')
        archive.write(ROOT / 'formats/character/README.md', prefix + 'README.md')
        archive.write(ROOT / 'docs/LICENSING.md', prefix + 'LICENSING.md')
    manifest_path = ROOT / 'builds/manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    record = dict(path=target.relative_to(ROOT/'builds').as_posix(), bytes=target.stat().st_size,
                  sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    manifest['packages'] = [p for p in manifest['packages'] if p['path'] != record['path']] + [record]
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(target, record['bytes'], 'bytes')


if __name__ == '__main__':
    main()
