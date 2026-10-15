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
    ('TT_Cutscene_Importer_', 'io_scene_lego_cu3', 'formats/cu3/Addon/io_scene_lego_cu3/__init__.py'),
    ('TT_Character_Importer_', 'io_scene_tt_character', 'formats/character/Addon/io_scene_tt_character/__init__.py'),
    ('lsw1_hgp_importer-', 'lsw1_hgp_importer', 'formats/hgp/lsw1/__init__.py'),
)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    registered = []
    results = []
    with tempfile.TemporaryDirectory(prefix='tt-blender-packages-') as temporary:
        extracted = Path(temporary)
        sys.path.insert(0, str(extracted))
        try:
            for prefix, name, source_path in PACKAGES:
                packages = list((ROOT / 'builds/blender').glob(prefix + '*.zip'))
                if len(packages) != 1:
                    raise AssertionError('Build exactly one current package: ' + prefix)
                with ZipFile(packages[0]) as archive:
                    destination = extracted / name if name == 'lsw1_hgp_importer' else extracted
                    for member in archive.namelist():
                        target = (destination / member).resolve()
                        if not target.is_relative_to(extracted / name):
                            raise AssertionError('Unexpected addon package member: ' + member)
                    archive.extractall(destination)
                source = ROOT / source_path
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
                if name == 'io_scene_lego_cu3':
                    from types import SimpleNamespace
                    for version in (16,17,18):
                        assert addon.assembly_profile(SimpleNamespace(version=version),'AUTO') == 'LMSH1'
                    assert addon.assembly_profile(SimpleNamespace(version=19),'AUTO') == 'LB3'
                    try:addon.assembly_profile(SimpleNamespace(version=30),'AUTO')
                    except ValueError:pass
                    else:raise AssertionError('Unverified assembly version accepted')
                if name == 'lsw1_hgp_importer':
                    status = None
                else:
                    core = name + '._core' if name == 'io_scene_tt_character' else name
                    status = importlib.import_module(core + '.geometry_normals').normal_preservation_status()
                    assert status['supported'] == hasattr(bpy.types, 'GeometryNodeSetMeshNormal')
                check_drop_handlers(addon)
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
        scope='Extracted dependencies, simultaneous registration, drop routing, defaults and cleanup; no game files')))


def check_drop_handlers(addon):
    """Exercise handler polls and drop invocation without synthesizing OS input."""
    from types import SimpleNamespace
    handlers = [v for v in vars(addon).values() if isinstance(v,type)
                and issubclass(v,bpy.types.FileHandler) and v is not bpy.types.FileHandler]
    expected = {'io_scene_lego_cu3':{'.cu3','.cu2'},
                'io_scene_tt_character':{'.cd','.ghg','.gsc','.an4'},
                'lsw1_hgp_importer':{'.hgp'}}[addon.__name__]
    assert {ext for cls in handlers for ext in cls.bl_file_extensions.split(';')} == expected
    viewport = SimpleNamespace(area=SimpleNamespace(type='VIEW_3D'),mode='OBJECT',object=None)
    for cls in handlers:
        assert cls.is_registered
        assert not cls.poll_drop(SimpleNamespace(area=None,mode='OBJECT',object=None))
        assert not cls.poll_drop(SimpleNamespace(area=SimpleNamespace(type='VIEW_3D'),mode='EDIT_MESH',object=None))
        assert cls.poll_drop(viewport) == (cls.bl_file_extensions != '.an4')
        operator = next(v for v in vars(addon).values() if isinstance(v,type)
                        and issubclass(v,bpy.types.Operator) and getattr(v,'bl_idname',None)==cls.bl_import_operator)
        calls=[]
        manager=SimpleNamespace(invoke_props_dialog=lambda *a,**k:calls.append('dialog') or {'RUNNING_MODAL'},
                                fileselect_add=lambda *a:calls.append('selector'))
        context=SimpleNamespace(window_manager=manager,scene=bpy.context.scene)
        dropped=SimpleNamespace(filepath='sample'+cls.bl_file_extensions.split(';')[0])
        assert operator.invoke(dropped,context,None)=={'RUNNING_MODAL'}
        assert calls==['dialog']


if __name__ == '__main__':
    main()
