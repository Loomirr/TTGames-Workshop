"""Actual Blender SpiderFace/FACE_* live-clipping equivalence and isolation.

Synthetic geometry only; this does not establish native facial shader parity.
Run from any folder:
blender --background --factory-startup --python-exit-code 1 --python this.py
"""
import sys
import types
from pathlib import Path

import bpy


source = Path(__file__).resolve().parents[1] / 'Addon/io_scene_lego_cu3'
package = types.ModuleType('face_live_blender_fixture');package.__path__ = [str(source)]
sys.modules[package.__name__] = package
from face_live_blender_fixture.face_live import prepare_live


def mesh_snapshot(obj):
    return {
        'vertices': tuple(tuple(vertex.co) for vertex in obj.data.vertices),
        'polygons': tuple(tuple(polygon.vertices) for polygon in obj.data.polygons),
        'normals': tuple(tuple(normal.vector) for normal in obj.data.corner_normals),
        'shape_keys': tuple((key.name, key.value, tuple(tuple(vertex.co) for vertex in key.data))
                            for key in obj.data.shape_keys.key_blocks) if obj.data.shape_keys else (),
    }


def evaluated_snapshot(obj):
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        return {
            'vertices': tuple(tuple(round(component, 6) for component in vertex.co) for vertex in mesh.vertices),
            'polygons': tuple(tuple(polygon.vertices) for polygon in mesh.polygons),
            'normals': tuple(tuple(round(component, 6) for component in normal.vector) for normal in mesh.corner_normals),
        }
    finally:
        evaluated.to_mesh_clear()


def exercise(resource):
    scene = bpy.data.scenes.new(resource + ' / source')
    bpy.context.window.scene = scene
    parent = bpy.data.objects.new(resource + ' / native rig fixture', None)
    scene.collection.objects.link(parent)

    def plane(label, size, height, mask):
        mesh = bpy.data.meshes.new(label + ' / source geometry')
        half = size / 2
        mesh.from_pydata([(-half, -half, height), (half, -half, height),
                         (half, half, height), (-half, half, height)], [], [(0, 1, 2, 3)])
        mesh.update()
        for polygon in mesh.polygons:polygon.use_smooth = True
        mesh.normals_split_custom_set_from_vertices([(0.2, 0, 0.979795897)] * 4)
        obj = bpy.data.objects.new(label, mesh)
        scene.collection.objects.link(obj)
        obj.parent = parent
        obj['source_model'] = resource
        obj['tt_colour_write_mask'] = mask
        obj['fixture_role'] = label
        return obj

    detail = plane('Detail', 2, 0, 15)
    detail.shape_key_add(name='Basis')
    target = detail.shape_key_add(name='TT_Target_003')
    for vertex in target.data:vertex.co.x += 2
    target.value = 0
    mask = plane('Mask', 1, 0.1, 0)
    mask.hide_render = True
    mask.hide_set(True)
    printing = plane('Printing', 0.25, 0.2, 15)
    printing['tt_native_alpha_test'] = 5
    printing['tt_native_draw_order'] = 0
    printing['tt_native_cast_shadows'] = False
    # Missing draw-order metadata keeps the historical mask-only depth bias;
    # this makes the expected clipping region independent of native ordering.
    camera_data = bpy.data.cameras.new(resource + ' / camera')
    camera = bpy.data.objects.new(camera_data.name, camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0, 0, 3)
    camera_data.type = 'ORTHO'
    camera_data.ortho_scale = 3
    scene.camera = camera
    originals = {obj: mesh_snapshot(obj) for obj in (detail, mask, printing)}
    bpy.ops.scene.new(type='FULL_COPY')
    live = bpy.context.scene
    assert live != scene
    copied = {obj['fixture_role']: obj for obj in live.objects if obj.get('fixture_role')}
    report = prepare_live(live, detail_level=2)
    assert report['detail_parts'] == 1, (resource, report)
    assert report['biased_depth_masks'] == report['hidden_depth_parts'] == 1
    assert report['corner_normals_preserved'], report
    live_detail, live_mask, live_print = (copied[key] for key in ('Detail', 'Mask', 'Printing'))
    assert live_detail.data != detail.data
    assert live_detail.data.shape_keys != detail.data.shape_keys
    assert live_detail.modifiers.get('TT live facial clipping')
    assert not live_detail.modifiers.get('TT facial depth bias')
    assert live_mask.modifiers.get('TT facial depth bias')
    assert live_print.modifiers.get('TT facial depth bias')
    assert not live_print.modifiers.get('TT live facial clipping')
    assert live_mask.hide_get() and all(owner.hide_render for owner in live_mask.users_collection)
    modifier = live_detail.modifiers['TT live facial clipping']
    references = [node.inputs['Object'].default_value for node in modifier.node_group.nodes
                  if node.type == 'OBJECT_INFO']
    assert live_mask in references and live.camera in references
    assert all(obj in live.objects.values() for obj in references)
    assert mask not in references and camera not in references
    neutral = evaluated_snapshot(live_detail)
    assert 0 < len(neutral['polygons']) < 16, (resource, neutral)
    live_detail.data.shape_keys.key_blocks['TT_Target_003'].value = 1
    moved = evaluated_snapshot(live_detail)
    assert len(moved['polygons']) == 16, (resource, moved)
    # The helper only changes evaluated viewing-copy geometry. Basis, source
    # topology, source corner normals and source target values remain exact.
    for obj, before in originals.items():
        assert not obj.modifiers
        assert mesh_snapshot(obj) == before, (resource, obj.name)
        assert obj['source_model'] == resource
    assert all(obj['source_model'] == resource for obj in copied.values())
    assert mesh_snapshot(live_mask)['vertices'] == originals[mask]['vertices']
    assert mesh_snapshot(live_print)['vertices'] == originals[printing]['vertices']
    assert live_detail.data.shape_keys.key_blocks['Basis'].data[0].co[:] == detail.data.vertices[0].co[:]
    return neutral, moved


bpy.ops.wm.read_factory_settings(use_empty=True)
standard = exercise('FACE_SYNTHETIC')
spider = exercise('SpiderFace')
assert standard == spider, 'Equivalent source geometry must receive identical evaluated clipping and normals'
for resource in ('face_synthetic', 'Face_Synthetic', 'spiderface', 'SPIDERFACE'):
    assert exercise(resource) == standard, ('Filename case must not change facial clipping or normals', resource)
print('FACE_LIVE_GROUPS_BLENDER_PASSED', bpy.app.version_string,
      'FACE_ and SpiderFace filename-case equivalence, clipping, mask/printing depth helpers, morph evaluation, normal preservation and source isolation')
