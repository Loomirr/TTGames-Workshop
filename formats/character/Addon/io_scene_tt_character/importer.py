"""Character assembly and native-skeleton action application for the standalone addon."""
import json
import hashlib
from pathlib import Path
import bpy
from mathutils import Matrix
from ._core.cu3 import FormatError
from ._core.an4 import AnimationFile
from ._core.asset_index import open_assets
from ._core.definitions import character_definition
from ._core.dependencies import ResourceResolver, active_attachments
from ._core.native_model_blender import load_model, create_model
from ._core.costume_materials import CostumeMaterials
from ._core.blender_import import C, CI, row_matrix, apply_pose, prepare_pose
from ._core.animation_bank import AnimationBank
from ._core.animation_catalog import catalog
from ._core.morph import animate_shape_keys

STORES = ('objects', 'collections', 'meshes', 'armatures', 'materials', 'images', 'actions', 'shape_keys', 'node_groups', 'texts')


def snapshot():
    return {name: set(getattr(bpy.data, name)) for name in STORES}


def rollback(before):
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.data.batch_remove(ids={item for name in STORES for item in getattr(bpy.data, name) if item not in before[name]})


def find_rig(obj):
    result = None
    while obj:
        if obj.type == 'ARMATURE' and obj.get('tt_character_skeleton'):
            result = obj
        obj = obj.parent
    return result


def find_character(obj):
    result = None
    while obj:
        if obj.get('tt_character_assets_root'):
            result = obj
        obj = obj.parent
    return result


def write_report(name, report):
    text = bpy.data.texts.new(name)
    text.write(json.dumps(report, indent=2))
    return text.name


def facial_actions(source, actor, child, frames):
    """Link one verified BSA atomically, without changing existing key data."""
    morph = source.morph_animation(actor)
    if morph is None:return []
    faces = [o for o in child.children if o.type=='MESH' and o.data.shape_keys]
    # Some LB3 BSA blocks retain one extra end sample (106 vs 105 frames).
    # Sample the body clip's original range without stretching facial time.
    if len(actor['records']) != 1 or morph.frames not in (frames, frames+1) or not faces:
        raise FormatError('Facial BSA needs one matching clip, target meshes and matching duration (at most one extra end sample)')
    if any(not k.name.rsplit('_',1)[1].isdigit() or int(k.name.rsplit('_',1)[1])>=morph.curves
           for o in faces for k in o.data.shape_keys.key_blocks if k.name.startswith('TT_Target_')):
        raise FormatError('Facial target ID exceeds the native BSA channels')
    before = snapshot()
    previous = [(o.data.shape_keys,
                 o.data.shape_keys.animation_data.action if o.data.shape_keys.animation_data else None,
                 o.data.shape_keys.animation_data.action_slot if o.data.shape_keys.animation_data else None,
                 [(k, k.slider_min, k.slider_max, k.value) for k in o.data.shape_keys.key_blocks]) for o in faces]
    result = []
    try:
        from .animation_export import action_fingerprint
        for obj in faces:
            action = animate_shape_keys(obj, morph, frames)
            result.append(dict(object=obj.name, action=action.name,
                               slot=obj.data.shape_keys.animation_data.action_slot.identifier,
                               fingerprint=action_fingerprint(action)))
        return result
    except Exception:
        rollback(before)
        for keys, action, slot, values in previous:
            if keys.animation_data:
                keys.animation_data.action = action
                if action:keys.animation_data.action_slot = slot
            for key, minimum, maximum, value in values:
                key.slider_min, key.slider_max, key.value = minimum, maximum, value
        raise


def import_character(context, path, assets_root, game, *, definition_path=None, cache=None, attachments=True, assets=None, layer_mode='default'):
    if context.mode != 'OBJECT':
        raise FormatError('Switch to Object Mode before importing')
    if game not in ('LB3', 'LMSH1', 'HOBBIT', 'AVENGERS'):
        raise FormatError('Select LB3, LMSH1, The Hobbit or Avengers')
    assets = assets or open_assets(assets_root, game, cache_root=cache)
    resolver = ResourceResolver(assets, game)
    definition = character_definition(path) if path.suffix.lower() == '.cd' else character_definition(definition_path) if definition_path else None
    if path.suffix.lower() == '.cd':
        reference = definition['character'].get('Override Model File') or definition['character']['Skeleton Name']
        model_path = assets.find(reference, resolver.suffix, '.GHG', required=False) or assets.find(reference, resolver.suffix, '.GSC')
    else:
        model_path = path
    report = dict(source=str(path), game=game, layer_mode=layer_mode, models=[], materials=[], issues=[],
                  limitations=['Native shaders and depth-mask faces remain approximate.',
                               'Attachment tracks require a unique matching native skeleton and clip; other attachments follow their locators.',
                               'A raw GHG without its CD imports display variants for inspection, not a configured costume.'])
    if not definition:
        report['issues'].append('No CD selected: costume slots and layer variants cannot be resolved as a complete character.')
    before = snapshot()
    original_active = context.view_layer.objects.active
    original_selected = list(context.selected_objects)
    materials = CostumeMaterials(assets, resolver.suffix, report['materials'])
    try:
        collection = bpy.data.collections.new(path.stem + ' / TT Character')
        context.scene.collection.children.link(collection)
        for obj in context.selected_objects:
            obj.select_set(False)

        def build(source, definition, name, parent=None, chain=()):
            key = source.resolve()
            if key in chain or len(chain) > 8:
                raise FormatError('Cyclic or excessively nested character attachments')
            model = load_model(source)
            expected = (175,) if game in ('LB3', 'AVENGERS') else (169, 170) if game == 'HOBBIT' else (169,)
            if game == 'LMSH1' and source.suffix.lower() == '.gsc':
                expected = (161, 169)
            if model['mesh_version'] not in expected:
                raise FormatError('Model version does not match the selected game')
            factory = lambda m, e, d: materials(m, e, d, attachment_tint=parent[2].get('Tint Colour') if parent else None)
            rig, parts = create_model(model, name, collection, definition, factory, layer_mode=layer_mode)
            rig['tt_native_source'] = str(source)
            rig['tt_native_source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
            if definition:
                rig['tt_native_definition'] = definition['source']
            skeleton = model['skeleton']
            if skeleton:
                rig['tt_character_skeleton'] = json.dumps(skeleton)
                rig['tt_character_game'] = game
                rig['cu3_geometry_status'] = 'Native source meshes and skeleton; material reconstruction experimental.'
            if parent:
                parent_rig, parent_skeleton, attachment = parent
                logical = attachment['Locator']
                remap = parent_skeleton['post_poi_bytes']
                if not 0 <= logical < len(remap) or remap[logical] >= len(parent_skeleton['points_of_interest']):
                    raise FormatError('Attachment locator outside native table')
                point = parent_skeleton['points_of_interest'][remap[logical]]
                anchor = bpy.data.objects.new(name + ' / locator', None)
                collection.objects.link(anchor)
                anchor.parent = parent_rig
                constraint = anchor.constraints.new('COPY_TRANSFORMS')
                constraint.target, constraint.subtarget = parent_rig, parent_skeleton['joints'][point['joint']]['name']
                rig.parent = anchor
                rig.matrix_parent_inverse = Matrix.Identity(4)
                rig.matrix_basis = C @ row_matrix(point['matrix']) @ row_matrix(list(attachment['Object Offset'])) @ CI
            report['models'].append(dict(source=str(source), meshes=len(parts), joints=len(skeleton['joints']) if skeleton else 0))
            if attachments and skeleton and definition:
                for attachment in active_attachments(definition, layer_mode=layer_mode):
                    saved = snapshot()
                    count = len(report['models'])
                    try:
                        resolved = resolver.resolve(attachment['Resource File'])
                        build(resolved['model'], resolved['definition'], name + ' / ' + attachment['Resource File'],
                              (rig, skeleton, attachment), chain + (key,))
                    except (ValueError, OSError, KeyError, RuntimeError) as error:
                        rollback(saved)
                        materials.images.clear()
                        del report['models'][count:]
                        report['issues'].append(f'Attachment {attachment.get("Resource File", "unknown")}: {error}')
            return rig

        rig = build(model_path, definition, path.stem)
        rig['tt_character_game'] = game
        rig['tt_character_assets_root'] = str(Path(assets_root).resolve())
        rig['tt_character_cache'] = str(Path(cache).resolve()) if cache else ''
        rig['tt_character_definition'] = str(path if path.suffix.lower() == '.cd' else definition_path or '')
        rig['tt_native_texture_sources'] = json.dumps(sorted({str(key[0] if isinstance(key, tuple) else key) for key in materials.images}))
        if definition:
            try:
                animation_report = refresh_catalog(rig, assets, definition)
                report['animation_catalog'] = dict(sets=animation_report['sets'], entries=len(animation_report['entries']), issues=animation_report['issues'])
            except (ValueError, OSError, KeyError) as error:
                report['issues'].append('Animation catalog: ' + str(error))
        for obj in context.selected_objects:
            obj.select_set(False)
        rig.select_set(True)
        context.view_layer.objects.active = rig
        rig['tt_character_report'] = write_report('TT Character report / ' + path.stem, report)
        context.view_layer.update()
        return rig, report
    except Exception:
        rollback(before)
        for obj in original_selected:
            obj.select_set(True)
        context.view_layer.objects.active = original_active
        raise


def refresh_catalog(rig, assets=None, definition=None):
    assets = assets or open_assets(rig['tt_character_assets_root'], rig['tt_character_game'],
                                 cache_root=rig.get('tt_character_cache') or None)
    definition = definition or character_definition(rig['tt_character_definition'])
    report = catalog(assets, definition)
    rig.tt_animation_assets.clear()
    for entry in report['entries']:
        item = rig.tt_animation_assets.add()
        item.name = entry['name']
        item.payload = json.dumps(entry)
        item.label = entry['set'] + ' / ' + entry['name']
        item.available = bool(entry['source'])
    rig['tt_animation_catalog_report'] = write_report('TT Animation catalog / ' + rig.name, report)
    rig['tt_animation_set_sources'] = json.dumps(report['sources'])
    return report


def import_animations(context, rig, paths, actor_name='', fps=30, *, data=None, clip_name=''):
    report = dict(imported=0, issues=[], clips=[])
    if rig is None:
        report['issues'].append('Select an imported native character rig')
        write_report('TT AN4 report', report)
        return report
    skeleton = json.loads(rig['tt_character_skeleton'])
    original_action = rig.animation_data.action if rig.animation_data else None
    original_slot = rig.animation_data.action_slot if rig.animation_data else None
    for path in paths:
        try:
            source = AnimationFile(path, fps=fps, data=data)
            actor = source.choose_actor(len(skeleton['joints']), actor_name)
            if clip_name and not any(r['name'].casefold() == clip_name.casefold() for r in actor['records']):
                raise FormatError('Declared clip is absent from this actor: ' + clip_name)
            for index, record in enumerate(actor['records']):
                if clip_name and record['name'].casefold() != clip_name.casefold():
                    continue
                if record['animation'].nodes != len(skeleton['joints']):
                    report['issues'].append(f'{path.name} / {record["name"]}: different skeleton size; skipped')
                    continue
                before = snapshot()
                old_action = rig.animation_data.action if rig.animation_data else None
                old_slot = rig.animation_data.action_slot if rig.animation_data else None
                try:
                    prepare_pose(record['animation'])
                    source.frames = record['animation'].frames
                    action, _ = apply_pose(source, actor, index, rig, skeleton)
                    action.name = path.stem + ' / ' + record['name']
                    if data is None:
                        action['tt_native_animation_source'] = str(path.resolve())
                    attachment_actions, face_tracks = [], []
                    for child in rig.children_recursive:
                        if child.type != 'ARMATURE' or not child.get('tt_character_skeleton'):
                            continue
                        child_skeleton = json.loads(child['tt_character_skeleton'])
                        candidates = [(a, i, r) for a in source.actors if a['parent'] is not None
                            for i, r in enumerate(a['records']) if r['name'].casefold() == record['name'].casefold()
                            and r['animation'].nodes == len(child_skeleton['joints'])]
                        if len(candidates) != 1:
                            report['issues'].append(f'{record["name"]}: no unique matching attachment track for {child.name}')
                            continue
                        a, i, r = candidates[0]
                        attachment_before = snapshot()
                        previous = child.animation_data.action if child.animation_data else None
                        previous_slot = child.animation_data.action_slot if child.animation_data else None
                        try:
                            prepare_pose(r['animation'])
                            source.frames = r['animation'].frames
                            child_action, _ = apply_pose(source, a, i, child, child_skeleton)
                            child_action.name = action.name + ' / ' + child.name
                            attachment_actions.append(dict(object=child.name, action=child_action.name,
                                slot=child.animation_data.action_slot.identifier))
                            from .animation_export import action_fingerprint
                            attachment_actions[-1]['fingerprint'] = action_fingerprint(child_action)
                            # Facial scalars are a separate BSA block, not bone
                            # channels. Preserve the native target IDs and sample
                            # only when the actor and clip duration agree.
                            try:
                                face_tracks.extend(facial_actions(source, a, child, r['animation'].frames))
                            except (ValueError, KeyError, RuntimeError) as error:
                                report['issues'].append(f'{record["name"]} / {child.name} facial targets: {error}')
                        except (ValueError, KeyError, RuntimeError) as error:
                            rollback(attachment_before)
                            if child.animation_data:
                                child.animation_data.action = previous
                                if previous:
                                    child.animation_data.action_slot = previous_slot
                            report['issues'].append(f'{record["name"]} / {child.name}: {error}')
                    source.frames = record['animation'].frames
                    action['tt_attachment_actions'] = json.dumps(attachment_actions)
                    action['tt_facial_actions'] = json.dumps(face_tracks)
                    from .animation_export import action_fingerprint
                    action['tt_native_pose_fingerprint'] = action_fingerprint(action)
                    action['tt_character_status'] = 'Native skeleton AN4 pose; original root translation retained. Compatible attachment tracks are linked; FPS is a preview assumption and events remain separate.'
                    item = rig.tt_clips.add()
                    item.name, item.action = action.name, action
                    item.slot = rig.animation_data.action_slot.identifier
                    item.frames, item.fps = source.frames, fps
                    report['imported'] += 1
                    report['clips'].append(dict(source=str(path), actor=actor['name'], action=action.name, frames=source.frames))
                except (ValueError, OSError, KeyError, RuntimeError) as error:
                    rollback(before)
                    if rig.animation_data:
                        rig.animation_data.action = old_action
                        if old_action:
                            rig.animation_data.action_slot = old_slot
                    report['issues'].append(f'{path.name} / {record["name"]}: {error}')
        except (ValueError, OSError, KeyError, RuntimeError) as error:
            report['issues'].append(f'{path.name}: {error}')
    if report['imported']:
        rig.tt_clip_index = len(rig.tt_clips) - report['imported']
    elif rig.animation_data:
        rig.animation_data.action = original_action
        if original_action:
            rig.animation_data.action_slot = original_slot
    write_report('TT AN4 report', report)
    return report


def import_catalog_entry(context, rig, entry):
    if not entry['source']:
        raise FormatError('This action has no resolved AN4 source; see the catalog report')
    payload = AnimationBank(entry['source']).read(entry['member']) if entry['member'] else None
    path = Path(entry['member']) if entry['member'] else Path(entry['source'])
    report = import_animations(context, rig, [path], entry['actor'], 30, data=payload, clip_name=entry['clip'])
    if report['imported']:
        rig.tt_clips[rig.tt_clip_index].action['tt_authored_action'] = json.dumps(entry)
    return report
