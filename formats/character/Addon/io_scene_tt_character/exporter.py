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
from ._core.source_provenance import SourceProvenance
from ._core.bundle_output import destination_path, publish_bundle, require_absent
from .source_bundle import canonical_source, group_source_instances, SourceProposals


def export_sources(rig, destination, face_edits=True, mesh_edits=True):
    destination = destination_path(destination)
    require_absent(destination)
    # Source paths reside either in the extracted root or our game cache.
    roots = [Path(rig['tt_character_assets_root']).resolve()]
    from ._core.asset_index import open_assets
    assets = open_assets(roots[0], rig['tt_character_game'], rig.get('tt_character_cache') or None)
    roots.append(assets.root.resolve())
    if any(destination == root or destination.is_relative_to(root) for root in roots):
        raise FormatError('Choose a new export folder outside game files and the source/cache tree')
    provenance=SourceProvenance.loads(rig.get('tt_native_source_provenance'))
    verified={canonical_source(path):data for path,data in provenance.verify().items()}
    records = {}
    for path, record in provenance.records.items():
        if not record.get('export'):
            continue
        path = canonical_source(path)
        if path in records and records[path]['logical_path'] != record['logical_path']:
            raise FormatError('One native source has ambiguous logical export paths: ' + str(path))
        records[path] = record
    def consumed(path):
        path = canonical_source(path)
        if path not in verified:
            raise FormatError('Native dependency has no consumed revision; reimport: '+str(path))
        return verified[path]
    sources, patches, vertex_patches = dict(verified), {}, {}
    instances_report = {}
    # Avoid returning a successful native bundle that silently discards a
    # modified clip. Active ANI-D editing has its own constrained writer.
    from .animation_export import action_fingerprint, check_linked_actions
    for clip in rig.tt_clips:
        if clip.action:check_linked_actions(clip.action)
        if clip.action and clip.action.get('tt_native_pose_fingerprint') and action_fingerprint(clip.action)!=clip.action['tt_native_pose_fingerprint']:
            raise FormatError('Loaded animation has edits. Export it separately with Export active AN4 clip; the source bundle cannot repack edited banks: '+clip.name)
    groups = group_source_instances(
        (obj['tt_native_source'], obj) for obj in [rig] + list(rig.children_recursive)
        if obj.get('tt_native_source'))
    for path, objects in groups.items():
        original = consumed(path)
        source_hash = hashlib.sha256(original).hexdigest()
        model = load_model(path) if mesh_edits or (face_edits and path.suffix.casefold()=='.ghg') else None
        if model and model['source_sha256'] != source_hash:
            raise FormatError('Native model changed during export preflight: '+str(path))
        proposals = SourceProposals(path)
        for obj in objects:
            if source_hash != obj['tt_native_source_sha256']:
                raise FormatError('Native source changed since import: ' + path.name)
            raw, manifest, vertex_manifest = original, None, None
            for mesh in obj.children:
                if mesh.type=='MESH' and mesh.get('tt_vertex_transform'):
                    check_materials(mesh)
            if mesh_edits and model.get('skeleton'):
                check_rig(obj,model['skeleton'])
            if mesh_edits:
                raw, vertex_manifest = patch_vertices(original, vertex_edits(obj.children, model, source_hash))
                if len(raw) != len(original):
                    raise FormatError('Native vertex patch changed source length')
            if face_edits and path.suffix.casefold() == '.ghg':
                parts = {str(p['index']):p['morphs'] for p in model['parts'] if p['morphs']}
                faces = [o for o in obj.children if o.get('tt_face_source_sha256')]
                if parts and faces:
                    companion = dict(schema='tt.relative-position-targets.v1', mesh_version=model['mesh_version'],
                                     sha256=source_hash, parts=parts)
                    edited = edited_companion(faces, companion)
                    if edited != companion or model['mesh_version'] in (169,170,175):
                        face_raw, manifest = patch_targets(original, edited)
                        if len(face_raw) != len(original):
                            raise FormatError('Native face patch changed source length')
                        merged = bytearray(raw)
                        for at,(a,b) in enumerate(zip(original,face_raw)):
                            if a==b:continue
                            if merged[at]!=a and merged[at]!=b:
                                raise FormatError('Face and vertex patches overlap with different values')
                            merged[at]=b
                        raw=bytes(merged)
                        read_mesh_bytes(raw)
            # Compare complete payloads, including no-op instances. Never merge
            # two distinct actors' proposals or let iteration order choose one.
            proposals.add(obj.name, raw)
            if vertex_manifest is not None:
                vertex_patches.setdefault(str(path), vertex_manifest)
            if manifest is not None:
                patches.setdefault(str(path), manifest)
            if obj.get('tt_native_definition'):
                cd = canonical_source(obj['tt_native_definition'])
                sources.setdefault(cd, consumed(cd))
        sources[path] = proposals.payload
        instances_report[str(path)] = dict(instances=proposals.instances,
                                          source_sha256=source_hash,
                                          output_sha256=hashlib.sha256(proposals.payload).hexdigest())
    for name in json.loads(rig.get('tt_native_texture_sources', '[]')):
        path = canonical_source(name)
        sources.setdefault(path, consumed(path))
    for name in json.loads(rig.get('tt_animation_set_sources', '[]')):
        path = canonical_source(name)
        sources.setdefault(path, consumed(path))
    for clip in rig.tt_clips:
        if clip.action and clip.action.get('tt_authored_action'):
            entry = json.loads(clip.action['tt_authored_action'])
            path = canonical_source(entry['source'])
            sources.setdefault(path, consumed(path))
        elif clip.action and clip.action.get('tt_native_animation_source'):
            path = canonical_source(clip.action['tt_native_animation_source'])
            sources.setdefault(path, consumed(path))
    planned = [(records[path]['logical_path'], data) for path, data in sources.items()]
    report = dict(schema='tt.loose-source-export.v1', game=rig['tt_character_game'], files=[], face_patches=patches, vertex_patches=vertex_patches,
        source_instances=instances_report,
        consumed_dependencies=json.loads(provenance.dumps()),
        limitations=['Supported existing positions, UVs, vertex colors, normals, palette-limited skin weights and facial targets are encoded when enabled.',
                     'Topology, new palettes, native bounds, material/image encoding, skeleton edits and animation-bank edits are not encoded.',
                     'Position edits must remain inside original part bounds; facial Basis positions are immutable. Object transforms and modifiers are preview-only.',
                     'No DAT archives or installed game files were changed.'])
    return publish_bundle(destination, planned, report, forbidden_suffixes=('.dat',))
