"""Manual source checks; no game data or Blender required."""
import ast
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
SKIP={'__pycache__','bin','obj','dist','Release','SampleOutput','RunOutput',
      'GuiLaunchOutput','PackageSmoke','PackagedCliOutput'}

def source_files():
    for area in ['formats','games','tools']:
        for path in (ROOT/area).rglob('*'):
            if path.is_file() and not set(path.relative_to(ROOT).parts)&SKIP:
                yield path

def main():
    counts={'python':0,'json':0,'projects':0}
    for path in source_files():
        if path.suffix=='.py':
            ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path));counts['python']+=1
        elif path.suffix=='.json':
            json.loads(path.read_text(encoding='utf-8-sig'));counts['json']+=1
        elif path.suffix=='.csproj':
            ET.parse(path);counts['projects']+=1
    for name in ['test_face_targets.py','test_face_edit.py','test_material_flags.py']:
        subprocess.run([sys.executable,str(ROOT/'formats/cu3/scripts'/name)],check=True,cwd=ROOT)
    manifest=ROOT/'builds/manifest.json'
    if manifest.exists():
        for package in json.loads(manifest.read_text(encoding='utf-8'))['packages']:
            path=(ROOT/'builds'/package['path']).resolve()
            assert path.is_relative_to((ROOT/'builds').resolve()),'Unsafe package path'
            raw=path.read_bytes()
            assert len(raw)==package['bytes'] and hashlib.sha256(raw).hexdigest()==package['sha256'],path.name
            with ZipFile(path) as archive:
                assert archive.testzip() is None,path.name
                for name in archive.namelist():
                    item=Path(name)
                    assert not item.is_absolute() and '..' not in item.parts,name
                    assert item.suffix.lower() in {'.py','.md','.txt','.toml','.exe'} or item.name in {'LICENSE','.gitignore'},name
                    if item.suffix.lower()=='.exe':
                        assert re.fullmatch(r'windows/LIJ1_360_Texture_Extractor-\d+\.\d+\.\d+-win64\.zip',package['path']) and name=='LIJ1_360_Texture_Extractor.exe',name
        print('Build package hashes/integrity and no-game-asset checks passed.')
    print('Source syntax/config checks passed:',counts)
    print('Nine portable CU3 tests passed. Blender and original-file tests are separate.')

if __name__=='__main__':main()
