"""Loose sources, existing vertex attributes and face targets; never writes DAT."""
import hashlib
import json
from pathlib import Path
from ._core.cu3 import FormatError
from ._core.native_model_blender import load_model
from ._core.face_edit_blender import edited_companion
from ._core.face_edit import patch_targets
from ._core.mesh_edit import patch_vertices
from ._core.mesh_edit_blender import vertex_edits
from ._core.native_mesh import read_mesh_bytes
from ._core.blender_import import check_rig
from ._core.material_edit_guard import check_materials


def export_sources(rig, destination, face_edits=True, mesh_edits=True):
    destination = Path(destination).expanduser().resolve()
    # Source paths reside either in the extracted root or our game cache.
    roots = [Path(rig['tt_character_assets_root']).resolve()]
    from ._core.asset_index import open_assets
    assets = open_assets(roots[0], rig['tt_character_game'], rig.get('tt_character_cache') or None)
    roots.append(assets.root.resolve())
    if any(destination == root or destination.is_relative_to(root) for root in roots):
        raise FormatError('Choose a new export folder outside game files and the source/cache tree')
    sources, patches, vertex_patches = {}, {}, {}
    # Avoid returning a successful native bundle that silently discards a
    # modified clip. Active ANI-D editing has its own constrained writer.
    from .animation_export import action_fingerprint, check_linked_actions
    for clip in rig.tt_clips:
        if clip.action:check_linked_actions(clip.action)
        if clip.action and clip.action.get('tt_native_pose_fingerprint') and action_fingerprint(clip.action)!=clip.action['tt_native_pose_fingerprint']:
            raise FormatError('Loaded animation has edits. Export it separately with Export active AN4 clip; the source bundle cannot repack edited banks: '+clip.name)
    for obj in [rig] + list(rig.children_recursive):
        if not obj.get('tt_native_source'):
            continue
        path = Path(obj['tt_native_source']).resolve()
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != obj['tt_native_source_sha256']:
            raise FormatError('Native source changed since import: ' + path.name)
        manifest = None
        original = raw
        model = load_model(path) if mesh_edits or (face_edits and path.suffix.casefold()=='.ghg') else None
        for mesh in obj.children:
            if mesh.type=='MESH' and mesh.get('tt_vertex_transform'):
                check_materials(mesh)
        if mesh_edits and model.get('skeleton'):
            check_rig(obj,model['skeleton'])
        if mesh_edits:
            raw, vertex_manifest = patch_vertices(original, vertex_edits(obj.children, model, obj['tt_native_source_sha256']))
            vertex_patches[str(path)] = vertex_manifest
        if face_edits and path.suffix.casefold() == '.ghg':
            parts = {str(p['index']):p['morphs'] for p in model['parts'] if p['morphs']}
            faces = [o for o in obj.children if o.get('tt_face_source_sha256')]
            if parts and faces:
                companion = dict(schema='tt.relative-position-targets.v1', mesh_version=model['mesh_version'],
                                 sha256=obj['tt_native_source_sha256'], parts=parts)
                edited = edited_companion(faces, companion)
                if edited != companion or model['mesh_version'] in (169,170,175):
                    face_raw, manifest = patch_targets(original, edited)
                    merged = bytearray(raw)
                    for at,(a,b) in enumerate(zip(original,face_raw)):
                        if a==b:continue
                        if merged[at]!=a and merged[at]!=b:
                            raise FormatError('Face and vertex patches overlap with different values')
                        merged[at]=b
                    raw=bytes(merged)
                    read_mesh_bytes(raw)
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
    report = dict(schema='tt.loose-source-export.v1', game=rig['tt_character_game'], files=[], face_patches=patches, vertex_patches=vertex_patches,
        limitations=['Supported existing positions, UVs, vertex colors, normals, palette-limited skin weights and facial targets are encoded when enabled.',
                     'Topology, new palettes, native bounds, material/image encoding, skeleton edits and animation-bank edits are not encoded.',
                     'Position edits must remain inside original part bounds; facial Basis positions are immutable. Object transforms and modifiers are preview-only.',
                     'No DAT archives or installed game files were changed.'])
    for target, data in planned:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
        report['files'].append(dict(path=target.relative_to(destination).as_posix(), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    manifest_path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report
