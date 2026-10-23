"""Blender checks for navigation context, export availability and classic batches.

Called by check_blender_packages after the built Character addon is registered.
Uses synthetic objects; does not claim visual or original-file validation.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import bpy


class Layout:
    """Record draws while validating their Blender properties and operators."""
    enabled = True

    def __init__(self, events=None):
        self.events = events if events is not None else []

    def box(self): return Layout(self.events)
    def row(self): return Layout(self.events)
    def column(self): return Layout(self.events)
    def separator(self): pass

    def label(self, *, text='', **kwargs):
        self.events.append(text)

    def prop(self, data, name, **kwargs):
        assert hasattr(data, name), name

    def operator(self, name, **kwargs):
        category, operator = name.split('.')
        getattr(getattr(bpy.ops, category), operator).get_rna_type()
        self.events.append(name)
        return SimpleNamespace()

    def template_list(self, _type, _id, data, prop, active, index, **kwargs):
        assert hasattr(data, prop) and hasattr(active, index)


def check_navigation(addon):
    scene = bpy.context.scene
    scene.tt_character_game = 'LB3'
    context = SimpleNamespace(scene=scene, object=None, region=SimpleNamespace(width=240),
                              preferences=bpy.context.preferences)
    assert not addon.TTCHAR_OT_export_sources.poll(context)
    assert not addon.TTCHAR_OT_export_action.poll(context)
    expected = ['LB2', 'LB3', 'LMSH1', 'HOBBIT', 'AVENGERS', 'LB1', 'TCS', 'FORTNITE']
    # Existing saved enum integers retain their game after a UI label change.
    items = bpy.types.Scene.bl_rna.properties['tt_character_game'].enum_items
    assert [(item.identifier, item.value) for item in items] == list(zip(expected, range(8)))
    assert scene.tt_workflow == 'IMPORT'
    assert not scene.tt_show_advanced
    workflows = {'IMPORT': addon.TTCHAR_PT_tools, 'ANIMATE': addon.TTCHAR_PT_animations,
                 'EXPORT': addon.TTCHAR_PT_export}
    for workflow, visible in workflows.items():
        scene.tt_workflow = workflow
        assert [panel for panel in workflows.values() if panel.poll(context)] == [visible]
        assert not addon.TTCHAR_PT_import_options.poll(context)
        assert not addon.TTCHAR_PT_settings.poll(context)
    scene.tt_workflow = 'IMPORT'
    addon.TTCHAR_PT_navigation.draw(SimpleNamespace(layout=Layout()), context)
    panels = (addon.TTCHAR_PT_tools, addon.TTCHAR_PT_import_options,
              addon.TTCHAR_PT_animations, addon.TTCHAR_PT_export, addon.TTCHAR_PT_settings)
    for game in expected:
        scene.tt_character_game = game
        for panel in panels:
            layout = Layout()
            panel.draw(SimpleNamespace(layout=layout), context)
            if panel == addon.TTCHAR_PT_export:
                assert 'tt_character.export_sources' in layout.events
                assert 'tt_character.export_action' in layout.events
            if panel == addon.TTCHAR_PT_tools:
                assert ('import_scene.tt_character' in layout.events) == (game != 'FORTNITE')
    arm = bpy.data.armatures.new('Navigation test rig')
    rig = bpy.data.objects.new('Navigation test character', arm)
    scene.collection.objects.link(rig)
    rig['tt_character_skeleton'] = '{}'
    rig['tt_character_assets_root'] = 'synthetic-test'
    context.object = rig
    assert addon.TTCHAR_OT_export_sources.poll(context)
    assert not addon.TTCHAR_OT_export_action.poll(context)
    action = bpy.data.actions.new('Navigation native clip')
    rig.animation_data_create().action = action
    action['tt_native_pose_fingerprint'] = 'synthetic-test'
    assert addon.TTCHAR_OT_export_action.poll(context)
    # Changing the next-import game must not hide the selected rig's workflows.
    scene.tt_character_game = 'TCS'
    for panel in (addon.TTCHAR_PT_animations, addon.TTCHAR_PT_animation_options, addon.TTCHAR_PT_export):
        panel.draw(SimpleNamespace(layout=Layout()), context)
    addon.TTCHAR_OT_export_sources.draw(SimpleNamespace(layout=Layout(), mesh_edits=True, face_edits=True), context)
    addon.TTCHAR_OT_export_action.draw(SimpleNamespace(layout=Layout(), rebuild_bank=False, omit_auxiliary=False), context)
    bpy.data.objects.remove(rig, do_unlink=True)
    bpy.data.armatures.remove(arm)
    bpy.data.actions.remove(action)
    scene.tt_character_game = 'LB3'


def check_classic_batch(addon):
    from importlib import import_module
    batch = import_module(addon.__name__ + '.batch')
    importer = import_module(addon.__name__ + '.importer')
    calls = []

    def import_model(context, source, game):
        calls.append((source, game))
        mesh = bpy.data.meshes.new('Batch test triangle')
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
        obj = bpy.data.objects.new('Batch test model', mesh)
        context.scene.collection.objects.link(obj)
        return None, {'profile': game}

    for game in ('LB1', 'TCS'):
        before = importer.snapshot()
        source = Path('synthetic-model.ghg')
        assets = SimpleNamespace(root=Path('.'), find_exact=lambda _: source)
        try:
            with patch.object(addon, 'import_classic_model', import_model):
                run = batch.BatchRun(bpy.context, assets, game, ['model.ghg'])
                run.step(bpy.context)
                run.finish()
            assert run.report['imported'] == 1, run.report
            assert run.report['entries'][0]['details']['profile'] == game
            assert calls[-1] == (source, game)
        finally:
            importer.rollback(before)


def check(addon):
    check_navigation(addon)
    check_classic_batch(addon)
    print('CHARACTER_NAVIGATION_CHECK_PASSED: 8 games, sidebar/export draws, export selection, classic batch profiles')
