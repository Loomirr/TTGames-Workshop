"""Loose native sources and constrained facial-target edits; never writes DAT.

This is not a general mesh, material or animation encoder. Source files remain
unchanged except verified existing facial target coordinates. A manifest states
exactly what was written, so preview edits cannot masquerade as native exports.
"""
import hashlib
import json
from pathlib import Path
from ._core.cu3 import FormatError
from ._core.native_model_blender import load_model
from ._core.face_edit_blender import edited_companion
from ._core.face_edit import patch_targets


def export_sources(rig, destination, face_edits=True):
    destination = Path(destination).expanduser().resolve()
    # Source paths reside either in the extracted root or our game cache.
    roots = [Path(rig['tt_character_assets_root']).resolve()]
    from ._core.asset_index import open_assets
    assets = open_assets(roots[0], rig['tt_character_game'], rig.get('tt_character_cache') or None)
    roots.append(assets.root.resolve())
    if any(destination == root or destination.is_relative_to(root) for root in roots):
        raise FormatError('Choose a new export folder outside game files and the source/cache tree')
    sources, patches = {}, {}
    for obj in [rig] + list(rig.children_recursive):
        if not obj.get('tt_native_source'):
            continue
        path = Path(obj['tt_native_source']).resolve()
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != obj['tt_native_source_sha256']:
            raise FormatError('Native source changed since import: ' + path.name)
        manifest = None
        if face_edits and path.suffix.casefold() == '.ghg':
            model = load_model(path)
            parts = {str(p['index']):p['morphs'] for p in model['parts'] if p['morphs']}
            faces = [o for o in obj.children if o.get('tt_face_source_sha256')]
            if parts and faces:
                companion = dict(schema='tt.relative-position-targets.v1', mesh_version=model['mesh_version'],
                                 sha256=obj['tt_native_source_sha256'], parts=parts)
                raw, manifest = patch_targets(raw, edited_companion(faces, companion))
        sources[path] = raw
        if manifest:
            patches[str(path)] = manifest
        if obj.get('tt_native_definition'):
            cd = Path(obj['tt_native_definition']).resolve()
            sources[cd] = cd.read_bytes()
    for name in json.loads(rig.get('tt_native_texture_sources', '[]')):
        path = Path(name).resolve()
        sources[path] = path.read_bytes()
    for name in json.loads(rig.get('tt_animation_set_sources', '[]')):
        path = Path(name).resolve()
        sources[path] = path.read_bytes()
    for clip in rig.tt_clips:
        if clip.action and clip.action.get('tt_authored_action'):
            entry = json.loads(clip.action['tt_authored_action'])
            path = Path(entry['source']).resolve()
            sources[path] = path.read_bytes()
        elif clip.action and clip.action.get('tt_native_animation_source'):
            path = Path(clip.action['tt_native_animation_source']).resolve()
            sources[path] = path.read_bytes()
    planned, targets = [], set()
    for path, data in sources.items():
        root = next((r for r in roots if path.is_relative_to(r)), None)
        relative = path.relative_to(root) if root else Path(path.name)
        target = destination / relative
        if not target.resolve().is_relative_to(destination) or target.suffix.casefold() == '.dat':
            raise FormatError('Unsafe native export path')
        if target.exists():
            raise FormatError('Export would overwrite an existing file: ' + str(target))
        if target in targets:
            raise FormatError('Two native sources map to the same export path')
        targets.add(target)
        planned.append((target, data))
    manifest_path = destination/'TT_Source_Export.json'
    if manifest_path.exists():
        raise FormatError('Choose a fresh export folder')
    report = dict(schema='tt.loose-source-export.v1', game=rig['tt_character_game'], files=[], face_patches=patches,
        limitations=['Only supported existing face-target coordinates are encoded from Blender edits.',
                     'Geometry, UVs, material node edits, skeleton edits and animation edits are not encoded; included sources retain their original bytes.',
                     'No DAT archives or installed game files were changed.'])
    for target, data in planned:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
        report['files'].append(dict(path=target.relative_to(destination).as_posix(), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    manifest_path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report
