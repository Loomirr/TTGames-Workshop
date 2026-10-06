"""Asset-free registration and dependency check of the built Blender ZIPs.

blender --background --factory-startup --python-exit-code 1 --python this.py

Imports the extracted packages without using either source addon directory.
This checks Blender APIs and packaging, not original game files or gameplay.
"""
import ast
import importlib
import json
from pathlib import Path
import pkgutil
import sys
import tempfile
from zipfile import ZipFile

import bpy


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = (
    ('TT_Cutscene_Importer_', 'io_scene_lego_cu3', 'formats/cu3/Addon'),
    ('TT_Character_Importer_', 'io_scene_tt_character', 'formats/character/Addon'),
)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    registered = []
    results = []
    with tempfile.TemporaryDirectory(prefix='tt-blender-packages-') as temporary:
        extracted = Path(temporary)
        sys.path.insert(0, str(extracted))
        try:
            for prefix, name, area in PACKAGES:
                packages = list((ROOT / 'builds/blender').glob(prefix + '*.zip'))
                if len(packages) != 1:
                    raise AssertionError('Build exactly one current package: ' + prefix)
                with ZipFile(packages[0]) as archive:
                    for member in archive.namelist():
                        target = (extracted / member).resolve()
                        if not target.is_relative_to(extracted) or not member.startswith(name + '/'):
                            raise AssertionError('Unexpected addon package member: ' + member)
                    archive.extractall(extracted)
                source = ROOT / area / name / '__init__.py'
                expected = next(ast.literal_eval(node.value) for node in ast.parse(source.read_text()).body
                                if isinstance(node, ast.Assign) and any(
                                    isinstance(target, ast.Name) and target.id == 'bl_info'
                                    for target in node.targets))
                addon = importlib.import_module(name)
                assert Path(addon.__file__).is_relative_to(extracted), addon.__file__
                assert addon.bl_info['version'] == expected['version'], addon.bl_info
                imported = []
                for module in pkgutil.walk_packages(addon.__path__, name + '.'):
                    loaded = importlib.import_module(module.name)
                    assert Path(loaded.__file__).is_relative_to(extracted), loaded.__file__
                    imported.append(module.name)
                addon.register()
                registered.append(addon)
                core = name + '._core' if name == 'io_scene_tt_character' else name
                status = importlib.import_module(core + '.geometry_normals').normal_preservation_status()
                assert status['supported'] == hasattr(bpy.types, 'GeometryNodeSetMeshNormal')
                results.append(dict(package=packages[0].name, version=list(addon.bl_info['version']),
                                    imported_modules=len(imported) + 1, normal_preservation=status))
            # Both addons can be enabled together; defaults survive registration.
            assert bpy.context.scene.tt_character_game == 'LB3'
            assert bpy.context.scene.tt_mesh_detail == 'HIGHEST'
            assert bpy.context.scene.tt_preview_normals is True
        finally:
            for addon in reversed(registered):
                addon.unregister()
            sys.path.remove(str(extracted))
    assert not hasattr(bpy.types.Scene, 'tt_character_game')
    assert not hasattr(bpy.types.Scene, 'tt_face_detail')
    print('BLENDER_PACKAGE_CHECK_PASSED', json.dumps(dict(
        blender=bpy.app.version_string, packages=results,
        scope='Extracted dependencies, simultaneous registration, defaults and cleanup; no game files')))


if __name__ == '__main__':
    main()
