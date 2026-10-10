"""Package the reviewed classic readers, with their MIT license and no assets."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
from package_workshop_gui import markdown_for_package
from prune_builds import keep_latest

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.1.0'


def main():
    source=ROOT/'formats/classic-pc'
    files={source/name for name in ('LICENSE','README.md','tools/reader_bounds.py',
                                   'tools/cu2.py','tools/an3.py','tools/giz.py')}
    target=ROOT/'builds/python'/f'Classic_PC_Inspectors-{VERSION}.zip'
    target.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(target,'w',ZIP_DEFLATED) as archive:
        for path in sorted(files):
            name=path.relative_to(ROOT).as_posix()
            if path.suffix=='.md':archive.writestr(name,markdown_for_package(path,files))
            else:archive.write(path,name)
        archive.writestr('README.md',
            '# Classic PC inspectors\n\nRead [instructions](formats/classic-pc/README.md). '
            'Run the commands from this extracted folder. Python 3.10+ is required; '
            'no Blender or third-party Python packages are needed. These are read-only '
            'inspectors, not complete scene/model importers.\n')
    manifest_path=ROOT/'builds/manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    relative=target.relative_to(ROOT/'builds').as_posix()
    manifest['packages']=[r for r in manifest['packages'] if r['path']!=relative]
    manifest['packages'].append(dict(path=relative,bytes=target.stat().st_size,
                                    sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    keep_latest(apply=True)
    print(target)


if __name__=='__main__':main()
