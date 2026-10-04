"""Build an installable addon ZIP containing source only."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import ast


def main():
    root = Path(__file__).resolve().parent.parent
    addon = root / 'Addon' / 'io_scene_lego_cu3'
    source = ast.parse((addon / '__init__.py').read_text(encoding='utf-8'))
    info = next(ast.literal_eval(node.value) for node in source.body
                if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id=='bl_info' for t in node.targets))
    version = '.'.join(map(str,info['version']))
    destination = root / 'dist' / f'TT_Cutscene_Importer_{version}.zip'
    destination.parent.mkdir(exist_ok=True)
    with ZipFile(destination, 'w', ZIP_DEFLATED) as archive:
        for source in sorted(addon.glob('*.py')):
            archive.write(source, f'io_scene_lego_cu3/{source.name}')
    print(destination)


if __name__ == '__main__':
    main()
