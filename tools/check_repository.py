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
    for name in ['test_skeleton_versions.py','test_animation_sources.py','test_tt_deflate.py','test_an4_standalone.py','test_face_targets.py','test_face_edit.py','test_material_flags.py','test_discrete_controls.py','test_texture_store.py','test_native_display.py','test_morph_controls.py','test_dependencies.py','test_native_layers.py','test_camera_version_gate.py','test_archive_cc8.py','test_tfa_structure.py','test_archive_assets.py','test_archive_v5.py','test_scene_configuration.py','test_stage_geometry.py']:
        subprocess.run([sys.executable,str(ROOT/'formats/cu3/scripts'/name)],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'tools/test_prune_builds.py')],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'formats/character/test_fortnite_catalog.py')],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'formats/character/test_fortnite_backend.py')],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'formats/character/test_source_bundle.py')],check=True,cwd=ROOT)
    for name in ['test_bundle_output.py','test_pak_preflight.py','test_archive_cli_bounds.py',
                 'test_identity_ownership.py','test_dds.py','test_preview_capabilities.py']:
        subprocess.run([sys.executable,str(ROOT/'formats/cu3/scripts'/name)],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'formats/cu3/scripts/test_mesh_edit.py')],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'formats/cu3/scripts/test_model_validation.py')],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'formats/cu3/scripts/test_source_provenance.py')],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'formats/cu3/scripts/test_an4_edit.py')],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'formats/cu3/scripts/test_face_decoder_cli.py')],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'tools/check_docs.py')],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'formats/btga/3ds/test_fuse.py')],check=True,cwd=ROOT)
    subprocess.run([sys.executable,str(ROOT/'formats/cu3/scripts/test_archive_cc4_cli.py')],check=True,cwd=ROOT)
    from prune_builds import keep_latest
    assert not keep_latest(), 'Superseded build packages are still published'
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
                    assert item.suffix.lower() in {'.py','.pyw','.md','.txt','.toml','.exe'} or item.name in {'LICENSE','.gitignore'},name
                    if item.suffix.lower()=='.exe':
                        assert re.fullmatch(r'windows/LIJ1_360_Texture_Extractor-\d+\.\d+\.\d+-win64\.zip',package['path']) and name=='LIJ1_360_Texture_Extractor.exe',name
        print('Build package hashes/integrity and no-game-asset checks passed.')
    print('Source syntax/config checks passed:',counts)
    print('Portable native/archive/package and FUSE tests passed. Blender, GUI, Pillow and original-file tests are separate.')

if __name__=='__main__':main()
