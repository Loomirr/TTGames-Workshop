"""Actual Blender regression for issue #1's missing Scene preview setting.

Use an extracted Character addon, with no game data or source import paths:
blender --background --factory-startup --python-exit-code 1 --python this.py --
    --addon-directory /path/containing/io_scene_tt_character
"""
import argparse
import sys
from pathlib import Path

import bpy


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--addon-directory', type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
sys.path.insert(0, str(args.addon_directory))
import io_scene_tt_character as addon
from io_scene_tt_character.preview import create_preview
from io_scene_tt_character.preview_settings import apply_settings
from io_scene_tt_character.scene_settings import (
    PREVIEW_FIELDS, ensure_scene_settings, missing_scene_settings,
    unregister_scene_settings,
)


def fixture(scene):
    rig = bpy.data.objects.new('Registration fixture', None)
    scene.collection.objects.link(rig)
    mesh = bpy.data.meshes.new('Registration fixture geometry')
    mesh.from_pydata([(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)], [], [(0, 1, 2, 3)])
    obj = bpy.data.objects.new('Registration fixture surface', mesh)
    obj.parent = rig
    scene.collection.objects.link(obj)
    material = bpy.data.materials.new('Registration fixture source')
    material.use_nodes = True
    obj.data.materials.append(material)
    return rig, obj, material


def values(scene):
    return {field: getattr(scene, field) for field in PREVIEW_FIELDS}


def assert_values(scene, expected):
    for field, value in expected.items():
        actual = getattr(scene, field)
        if isinstance(value, float):
            assert abs(actual - value) < 1e-6, (field, value, actual)
        else:
            assert actual == value, (field, value, actual)


bpy.ops.wm.read_factory_settings(use_empty=True)
addon.register()
scene = bpy.context.scene
rig, surface, material = fixture(scene)
source_positions = [tuple(v.co) for v in surface.data.vertices]
scene.tt_face_detail = 2
scene.tt_preview_normal_strength = .4
scene.tt_preview_normals = False
scene.tt_preview_shading = 'ALBEDO'
scene.tt_preview_display = 'AgX'
scene.tt_preview_exposure = .75
scene.tt_preview_samples = 17
scene.tt_mesh_detail = 'AUTHORED'
expected = values(scene)

# Reproduce the reported state, including an already imported source scene.
# Existing values remain managed by Blender; restoring a definition must not
# replace other properties or overwrite the recovered value with its default.
del bpy.types.Scene.tt_face_detail
assert not hasattr(scene, 'tt_face_detail')
assert missing_scene_settings() == ('tt_face_detail',)
view = create_preview(bpy.context, rig)
assert_values(scene, expected)
assert_values(view, expected)
assert scene.tt_mesh_detail == 'AUTHORED'
assert not missing_scene_settings()
assert ensure_scene_settings() == ()
copied = next(o for o in view.objects if o.get('tt_preview_source') == surface.name)
assert copied.data != surface.data
assert copied.data.materials[0] != material
assert not material.get('tt_preview_material')
assert [tuple(v.co) for v in surface.data.vertices] == source_positions

# Apply also repairs missing settings after a preview already exists.
del bpy.types.Scene.tt_preview_normal_strength
apply_settings(bpy.context, view)
assert_values(view, expected)
assert_values(scene, expected)

# The settings panel has an explicit recovery action that works independently
# of creating a preview. Registration and cleanup must tolerate a partial set.
unregister_scene_settings()
assert len(missing_scene_settings()) == 10
assert bpy.ops.tt_character.restore_settings() == {'FINISHED'}
assert_values(scene, expected)
assert_values(view, expected)

# A scene which never had these settings gets their documented defaults.
# A screen is optional during background use; all geometry work still runs in
# Blender using the real window/view layer/dependency graph.
fresh = bpy.data.scenes.new('Scene without stored preview settings')
bpy.context.window.scene = fresh
fresh_rig, _, _ = fixture(fresh)
unregister_scene_settings()


class WithoutScreen:
    screen = None

    def __getattr__(self, name):
        return getattr(bpy.context, name)


fresh_view = create_preview(WithoutScreen(), fresh_rig)
assert_values(fresh_view, dict(
    tt_face_detail=4, tt_preview_normals=True, tt_preview_normal_strength=1.0,
    tt_preview_shading='LIT', tt_preview_display='Standard',
    tt_preview_exposure=0.0, tt_preview_samples=64))
assert fresh.tt_mesh_detail == 'HIGHEST'
assert fresh.tt_costume_layers == 'default' and fresh.tt_import_attachments

# A failing preview still removes its own partial scene and datablocks.
empty = bpy.data.objects.new('No visible bounds', None)
fresh_view.collection.objects.link(empty)
stores = ('objects', 'collections', 'meshes', 'armatures', 'cameras', 'lights',
          'worlds', 'scenes', 'shape_keys', 'node_groups', 'materials')
before = {name: set(getattr(bpy.data, name)) for name in stores}
try:
    create_preview(bpy.context, empty)
except ValueError as error:
    assert 'visible mesh bounds' in str(error)
else:
    raise AssertionError('Preview without geometry must fail')
assert bpy.context.scene == fresh_view
assert before == {name: set(getattr(bpy.data, name)) for name in stores}
del bpy.types.Scene.tt_face_detail
addon.unregister()
assert not hasattr(bpy.types.Scene, 'tt_character_game')
assert len(missing_scene_settings()) == 10
print('PREVIEW_REGISTRATION_PASSED', bpy.app.version_string,
      'missing RNA recovery, retained settings, defaults, source isolation, background screen, rollback and cleanup')
