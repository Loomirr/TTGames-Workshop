"""Build and package our addons and existing freshly published Windows extractor.

The extractor must first be compiled from formats/nu20/lij1-xbox360/Source.
External extraction programs and game inputs are never searched or bundled.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender',required=True,type=Path)
    parser.add_argument('--dotnet-root',type=Path,help='Installed .NET SDK folder, required for its license notices')
    args=parser.parse_args()
    blender=args.blender.resolve()
    builds=ROOT/'builds';addons=builds/'blender';windows=builds/'windows'
    addons.mkdir(parents=True,exist_ok=True);windows.mkdir(exist_ok=True)
    hgp=ROOT/'formats/hgp/lsw1'
    subprocess.run([str(blender),'-b','--factory-startup','--command','extension','build',
                    '--output-dir',str(addons)],cwd=hgp,check=True)
    cu3=ROOT/'formats/cu3'
    subprocess.run([sys.executable,str(cu3/'scripts/build_addon.py')],check=True)
    source=ast.parse((cu3/'Addon/io_scene_lego_cu3/__init__.py').read_text())
    info=next(ast.literal_eval(n.value) for n in source.body if isinstance(n,ast.Assign)
              and any(isinstance(t,ast.Name) and t.id=='bl_info' for t in n.targets))
    version='.'.join(map(str,info['version']))
    shutil.copy2(cu3/'dist'/f'TT_Cutscene_Importer_{version}.zip',addons)
    packages=sorted(addons.glob('*.zip'))
    if args.dotnet_root:
        tool=ROOT/'formats/nu20/lij1-xbox360'
        exe=tool/'dist/LIJ1_360_Texture_Extractor.exe'
        if not exe.is_file():raise ValueError('Compile our LIJ1 extractor first; no external EXE is accepted')
        licenses=args.dotnet_root.resolve()
        version=ET.parse(tool/'Source/LIJ1TextureExtractor.csproj').findtext('./PropertyGroup/Version')
        if not version or not all(part.isdigit() for part in version.split('.')):
            raise ValueError('Invalid extractor project version')
        package=windows/f'LIJ1_360_Texture_Extractor-{version}-win64.zip'
        entries=[(exe,exe.name),(tool/'README.md','README.md'),
                 (tool/'FORMAT.md','FORMAT.md'),
                 (tool/'LICENSE.txt','LICENSE.txt'),(tool/'THIRD_PARTY_NOTICES.txt','THIRD_PARTY_NOTICES.txt'),
                 (licenses/'LICENSE.txt','Runtime_LICENSE.txt'),
                 (licenses/'ThirdPartyNotices.txt','Runtime_ThirdPartyNotices.txt')]
        for file,_ in entries:
            if not file.is_file():raise FileNotFoundError(file)
        unchanged=False
        if package.exists():
            with ZipFile(package) as archive:
                unchanged=(set(archive.namelist())=={name for _,name in entries}
                           and all(hashlib.sha256(archive.read(name)).hexdigest()==sha(file)
                                   for file,name in entries))
        if not unchanged:
            fd,temporary=tempfile.mkstemp(prefix='.package-',suffix='.zip',dir=windows)
            os.close(fd)
            temporary=Path(temporary)
            try:
                with ZipFile(temporary,'w',ZIP_DEFLATED,compresslevel=9) as archive:
                    for file,name in entries:archive.write(file,name)
                temporary.replace(package)
            finally:
                temporary.unlink(missing_ok=True)
        packages.append(package)
    # Preserve the separately packaged lightweight Python GUI downloads.
    packages.extend(sorted((builds/'python').glob('*.zip')))
    records=[]
    for file in packages:
        with ZipFile(file) as archive:
            assert archive.testzip() is None
            names=archive.namelist()
            assert not any(Path(n).suffix.lower() in {'.hgp','.ghg','.gsc','.cu3','.dds','.png','.blend','.dll'} for n in names)
            if file.parent==addons:
                assert not any(Path(n).suffix.lower() in {'.exe','.zip'} for n in names)
        record=dict(path=file.relative_to(builds).as_posix(),bytes=file.stat().st_size,sha256=sha(file))
        records.append(record);print(json.dumps(record),flush=True)
    manifest=dict(packages=records,notes='Our source-built tools only; no game assets or external extraction programs.')
    (builds/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
