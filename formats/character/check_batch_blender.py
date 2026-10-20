"""Blender batch placement, cancellation and failure cleanup regression (no game assets)."""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile
import bpy

root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as temp:
    with ZipFile(next((root/'builds/blender').glob('TT_Character_Importer_*.zip'))) as z:
        z.extractall(temp)
    sys.path.insert(0, temp)
    import io_scene_tt_character as addon
    from io_scene_tt_character import batch
    addon.register()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    keep = bpy.data.objects.new('Existing user object', None)
    bpy.context.scene.collection.objects.link(keep)
    assets = SimpleNamespace(root=Path(temp), find_exact=lambda p: Path(temp)/p)

    def fake_import(context, source, *a, **kw):
        collection = bpy.data.collections.new(source.stem)
        context.scene.collection.children.link(collection)
        rig = bpy.data.objects.new(source.stem+' root', None)
        collection.objects.link(rig)
        mesh = bpy.data.meshes.new(source.stem)
        mesh.from_pydata([(0,0,0),(2,0,0),(0,3,4)], [], [(0,1,2)])
        obj = bpy.data.objects.new(source.stem+' mesh', mesh)
        collection.objects.link(obj)
        obj.parent = rig
        hidden = bpy.data.collections.new(source.stem+' hidden unbound')
        collection.children.link(hidden)
        hidden.hide_viewport = True
        outlier = bpy.data.objects.new(source.stem+' outlier', mesh.copy())
        hidden.objects.link(outlier)
        outlier.parent = rig
        outlier.location = (1000,1000,1000)
        if source.stem == 'broken':
            bpy.data.images.new('Failed orphan image', width=1, height=1)
            raise ValueError('intentional malformed asset')
        return rig, {'issues':[], 'materials':[]}

    with patch.object(batch, 'import_character', fake_import):
        run = batch.BatchRun(bpy.context, assets, 'LMSH1', ['one.cd','broken.cd','two.cd','three.cd'], columns=2, gap=1)
        for _ in range(4):run.step(bpy.context)
        run.finish()
        bpy.context.view_layer.update()
        assert run.report['imported'] == 3 and run.report['failed'] == 1
        assert bpy.data.objects.get('Existing user object') == keep
        assert bpy.data.images.get('Failed orphan image') is None
        assert bpy.data.collections.get('broken') is None
        assert tuple(bpy.data.objects['one root'].location) == (0,0,0)
        assert tuple(bpy.data.objects['two root'].location) == (3,0,0)
        assert tuple(bpy.data.objects['three root'].location) == (0,4,0)
        assert tuple(bpy.data.objects['two mesh'].location) == (0,0,0)
        cancelled = batch.BatchRun(bpy.context, assets, 'LMSH1', ['four.cd','five.cd'])
        cancelled.step(bpy.context)
        cancelled.finish(True)
        assert cancelled.report['status'] == 'cancelled' and cancelled.report['unprocessed'] == 1
        assert bpy.data.objects.get('four root') is not None and bpy.data.objects.get('five root') is None
        # Blender Event has no .timer member. Exercise the UI path as well as
        # direct/background BatchRun, using its real documented event shape.
        calls = []
        operator = SimpleNamespace(_scene=bpy.context.scene,
            _run=SimpleNamespace(index=0, paths=['x'], step=lambda c:calls.append('step')),
            _finish=lambda c,v:calls.append(('finish',v)))
        context = SimpleNamespace(scene=bpy.context.scene, mode='OBJECT', area=None,
            window_manager=SimpleNamespace(progress_update=lambda v:None))
        assert batch.TTCHAR_OT_batch_import.modal(operator, context, SimpleNamespace(type='TIMER')) == {'RUNNING_MODAL'}
        assert calls == ['step']
        batch.TTCHAR_OT_batch_import.modal(operator, context, SimpleNamespace(type='ESC'))
        assert calls[-1] == ('finish',True)
    addon.unregister()
print('PASS: batch placement, failure rollback, user object preservation, partial cancellation')
