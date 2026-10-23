"""Incremental, cancellable native-model review galleries."""
import json
from pathlib import Path
import bpy
from bpy.props import StringProperty, EnumProperty, IntProperty, FloatProperty
from mathutils import Vector
from .batch_catalog import catalog_paths, select_paths
from .importer import snapshot, rollback, import_character

_running = False


class BatchRun:
    def __init__(self, context, assets, game, paths, *, columns=5, gap=0.25, cache=None):
        self.assets, self.game, self.paths, self.cache = assets, game, paths, cache
        self.columns, self.gap = columns, gap
        self.index = self.placed = 0
        self.x = self.y = self.row_depth = 0.0
        self.origin = context.scene.cursor.location.copy()
        self.options = dict(attachments=context.scene.tt_import_attachments,
                            layer_mode=context.scene.tt_costume_layers,
                            highest_detail=context.scene.tt_mesh_detail == 'HIGHEST')
        self.collection = bpy.data.collections.new('TT Batch gallery')
        context.scene.collection.children.link(self.collection)
        self.text = bpy.data.texts.new('TT Batch report.json')
        self.report = dict(game=game, root=str(assets.root), status='running',
                           requested=len(paths), entries=[], options=self.options,
                           limitations=['Successful import is not visual fidelity certification.',
                                        'Raw models do not assemble vehicle definitions or configured costumes.',
                                        'Native face depth masks need the individual composed preview.'])
        self.flush()

    def flush(self):
        self.text.clear()
        self.text.write(json.dumps(self.report, indent=2))

    def step(self, context):
        path = self.paths[self.index]
        before = snapshot()
        selected = list(context.selected_objects)
        active = context.view_layer.objects.active
        entry = dict(path=path)
        try:
            source = self.assets.find_exact(path)
            if self.game in ('LB1', 'TCS'):
                from . import import_classic_model
                _, details = import_classic_model(context, source, self.game)
            else:
                _, details = import_character(context, source, self.assets.root, self.game,
                    assets=self.assets, cache=self.cache, **self.options)
            objects = set(bpy.data.objects) - before['objects']
            context.view_layer.update()
            points = [o.matrix_world @ Vector(corner) for o in objects if o.type == 'MESH'
                      and o.visible_get(view_layer=context.view_layer) and not o.hide_render
                      for corner in o.bound_box]
            if not points:
                raise ValueError('No visible mesh geometry imported')
            lo = Vector(tuple(min(p[i] for p in points) for i in range(3)))
            hi = Vector(tuple(max(p[i] for p in points) for i in range(3)))
            offset = self.origin + Vector((self.x, self.y, 0)) - lo
            # Move roots only: skeleton rest matrices and child offsets stay intact.
            for obj in objects:
                if obj.parent not in objects:
                    obj.matrix_world.translation += offset
            for coll in set(bpy.data.collections) - before['collections']:
                if coll.name in context.scene.collection.children:
                    context.scene.collection.children.unlink(coll)
                    self.collection.children.link(coll)
            # Classic inspectors may link directly into the active collection.
            for obj in objects:
                if obj.name in context.scene.collection.objects:
                    context.scene.collection.objects.unlink(obj)
                    self.collection.objects.link(obj)
            context.view_layer.update()
            self.x += max(hi.x - lo.x, 0.1) + self.gap
            self.row_depth = max(self.row_depth, hi.y - lo.y)
            self.placed += 1
            if self.placed % self.columns == 0:
                self.x = 0.0
                self.y += self.row_depth + self.gap
                self.row_depth = 0.0
            entry.update(status='imported', objects=sorted(o.name for o in objects), details=details)
        except Exception as error:
            rollback(before)
            for obj in selected:
                obj.select_set(True)
            context.view_layer.objects.active = active
            entry.update(status='failed', error=f'{type(error).__name__}: {error}')
        self.report['entries'].append(entry)
        self.index += 1
        self.flush()

    def finish(self, cancelled=False):
        self.report.update(status='cancelled' if cancelled else 'complete',
                           imported=self.placed, failed=self.index-self.placed,
                           unprocessed=len(self.paths)-self.index)
        self.flush()


class TTCHAR_OT_batch_import(bpy.types.Operator):
    bl_idname = 'tt_character.batch_import'
    bl_label = 'Batch import for review'
    bl_description = 'Import a filtered roster or raw model gallery; failures are recorded and skipped'
    scope: EnumProperty(name='Include', items=[
        ('CHARACTERS', 'Characters', 'Character CDs, or classic CHARS models'),
        ('VEHICLES', 'Vehicle models', 'Raw GHG/GSC in vehicle, cars, boats or planes folders; incomplete assembly'),
        ('DEFINITIONS', 'All character definitions', 'Try all CDs, including non-roster definitions'),
        ('MODELS', 'All raw models / props', 'Try every GHG/GSC; includes variants and unsupported scene GSCs'),
        ('ALL', 'All definitions and models', 'Includes duplicate raw/shared variants; not deduplicated by appearance')])
    search: StringProperty(name='Path contains', description='Case-insensitive substring; empty includes every matching file')
    start: IntProperty(name='Start index', default=0, min=0, description='Zero-based offset in the sorted filtered list')
    limit: IntProperty(name='Maximum imports (0 = all)', default=20, min=0)
    columns: IntProperty(name='Columns', default=5, min=1, max=100)
    gap: FloatProperty(name='Gap', default=0.25, min=0.0, description='Space between actual model bounds in Blender units')

    @classmethod
    def poll(cls, context):
        return (not _running and context.mode == 'OBJECT' and
                getattr(context.scene, 'tt_character_game', 'FORTNITE') != 'FORTNITE')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=510)

    def draw(self, context):
        for prop in ('scope', 'search', 'start', 'limit', 'columns', 'gap'):
            self.layout.prop(self, prop)
        self.layout.label(text='Large rosters can use substantial memory. Esc stops after the current asset.')
        self.layout.label(text='Raw vehicle/prop imports are inspection, not complete vehicle assembly.')

    def execute(self, context):
        global _running
        from . import preferences, ensure_scene_settings
        from ._core.asset_index import open_assets
        try:
            ensure_scene_settings()
            prefs = preferences(context)
            game = context.scene.tt_character_game
            root = getattr(prefs, game.lower(), '') if prefs else ''
            if not root:
                raise ValueError('Set the game / extracted folder first')
            cache = Path(bpy.path.abspath(prefs.cache)) if prefs.cache else None
            assets = open_assets(bpy.path.abspath(root), game, cache_root=cache)
            paths = select_paths(catalog_paths(assets, self.scope, self.search), self.start, self.limit)
            if not paths:
                raise ValueError('No matching files; change the scope, path filter or start index')
            self._run = BatchRun(context, assets, game, paths, columns=self.columns, gap=self.gap, cache=cache)
        except (ValueError, OSError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        if bpy.app.background:
            while self._run.index < len(paths):
                self._run.step(context)
            self._run.finish()
            return {'FINISHED'}
        self._scene = context.scene
        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        _running = True
        context.window_manager.modal_handler_add(self)
        context.window_manager.progress_begin(0, len(paths))
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'ESC' or context.scene != self._scene or context.mode != 'OBJECT':
            return self._finish(context, True)
        if event.type != 'TIMER':
            return {'RUNNING_MODAL'}
        try:
            self._run.step(context)
        except Exception as error:
            self._run.report['batch_error'] = f'{type(error).__name__}: {error}'
            return self._finish(context, True)
        context.window_manager.progress_update(self._run.index)
        if context.area:
            context.area.tag_redraw()
        if self._run.index == len(self._run.paths):
            return self._finish(context, False)
        return {'RUNNING_MODAL'}

    def _finish(self, context, cancelled):
        global _running
        context.window_manager.event_timer_remove(self._timer)
        context.window_manager.progress_end()
        _running = False
        self._run.finish(cancelled)
        self.report({'INFO'}, f'{self._run.placed} imported; see {self._run.text.name}')
        # Keep completed assets and the report even after Escape.
        return {'FINISHED'}

    def cancel(self, context):
        self._finish(context, True)
