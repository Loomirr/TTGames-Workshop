"""Manual source checks; no game data or Blender required."""
import ast
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

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
    print('Source syntax/config checks passed:',counts)
    print('Nine portable CU3 tests passed. Blender and original-file tests are separate.')

if __name__=='__main__':main()
