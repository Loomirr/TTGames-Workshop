"""Offline LEGO Fortnite export inventory; independent of TT binary readers.

Reads CUE4Parse JSON/GLB/PNG output, not cooked Unreal packages. Names are
resolved by package paths; duplicate basenames are never silently selected.
"""
import json
import re
from pathlib import Path


class MissingExport(ValueError):
    """A required companion is absent, so installed-mode extraction can retry."""


def reference(value):
    if not value:
        return None
    if isinstance(value, dict):
        value = value.get('ObjectPath') or value.get('AssetPathName')
    if not isinstance(value, str):
        raise ValueError('Invalid Unreal asset reference')
    if "'" in value:
        value = value.split("'")[1]
    return value.split('.')[0].replace('\\', '/').strip('/')


def package_path(path):
    value = path.with_suffix('').as_posix()
    marker = '/Content/'
    if marker in value:
        prefix, suffix = value.split(marker, 1)
        plugin = prefix.rsplit('/', 1)[-1]
        return ('Game' if plugin == 'FortniteGame' else plugin) + '/' + suffix
    return value


def head_color(descriptor, material, mesh):
    if 'Color Head ID' in material:
        return material['Color Head ID']
    # Mutable's standard-head selector supplies the color when its material
    # parent omits the scalar. Do not extend this rule to special head layouts.
    standard = 'FigureCharacter/Figure_Core/SkeletalMesh/SKM_Figure_HeadStandard_Mutable'
    if reference(mesh).casefold() == standard.casefold():
        values = [p['ParameterValueName'] for p in descriptor.get('IntParameters', [])
                  if p['ParameterName'] == 'Head Standard Color']
        match = re.fullmatch(r'ColorID_(\d+)_[A-Za-z0-9_]+', values[0]) if len(values) == 1 else None
        if match:
            return int(match.group(1))
    raise ValueError('Head material has no color ID or verified standard-head color selector')


class ExportLibrary:
    def __init__(self, root):
        self.root = Path(root).resolve()
        if not (self.root / 'Exports').is_dir() or not (self.root / 'Models').is_dir():
            raise ValueError('Choose a LEGO Fortnite export folder containing Exports (JSON/PNG) and Models (GLB). Cooked Fortnite packages require a separate Unreal exporter.')
        self.files, self.names, self.documents = {}, {}, {}
        for folder, suffixes in [('Exports', {'.json', '.png'}), ('Models', {'.glb'})]:
            for path in (self.root / folder).rglob('*'):
                if path.suffix.lower() not in suffixes:
                    continue
                path = path.resolve()
                if not path.is_relative_to(self.root):
                    raise ValueError('Export file points outside the selected library')
                key = (package_path(path.relative_to(self.root / folder)).casefold(), path.suffix.lower())
                if key in self.files:
                    raise ValueError('Duplicate export package: ' + key[0])
                self.files[key] = path
                self.names.setdefault((path.stem.casefold(), path.suffix.lower()), []).append(path)
        names_path = self.root / 'character-names.json'
        self.labels = json.loads(names_path.read_text(encoding='utf-8')) if names_path.is_file() else {}
        if not isinstance(self.labels, dict) or any(not isinstance(v, str) for v in self.labels.values()):
            raise ValueError('character-names.json must map source codenames to display names')

    def file(self, value, suffix, *, required=True):
        ref = reference(value)
        if ref is None:
            if required:
                raise ValueError('Missing asset reference')
            return None
        result = self.files.get((ref.casefold(), suffix))
        # Only bare names may use basename resolution. Explicit package paths
        # must match exactly, even if a similarly named export exists elsewhere.
        if result is None and '/' not in ref:
            matches = self.names.get((ref.casefold(), suffix), [])
            if len(matches) > 1:
                raise ValueError('Ambiguous export basename: ' + ref)
            result = next(iter(matches), None)
        if result is None and required:
            raise MissingExport('Missing exported companion: ' + ref + suffix)
        return result

    def document(self, value):
        path = self.file(value, '.json')
        if path not in self.documents:
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, list) or any(not isinstance(v, dict) for v in data):
                raise ValueError('Expected CUE4Parse export array: ' + path.name)
            self.documents[path] = data
        return self.documents[path]

    def object(self, value, kind=None):
        name = reference(value).rsplit('/', 1)[-1]
        found = [v for v in self.document(value) if v.get('Name', '').casefold() == name.casefold() and (kind is None or v.get('Type') == kind)]
        if len(found) != 1:
            raise ValueError('Expected one matching exported object: ' + name)
        return found[0]

    def material(self, value, chain=()):
        ref = reference(value)
        if ref in chain or len(chain) >= 32:
            raise ValueError('Cyclic or excessive material inheritance')
        obj = self.object(ref)
        props = obj.get('Properties', {})
        parent = props.get('Parent')
        values = self.material(parent, chain + (ref,)) if parent else {}
        for group in ('ScalarParameterValues', 'TextureParameterValues', 'VectorParameterValues'):
            for param in props.get(group, []):
                values[param['ParameterInfo']['Name']] = param['ParameterValue']
        return values

    def catalog(self):
        entries = []
        for (ref, suffix), path in sorted(self.files.items()):
            if suffix != '.json' or '/figure/figure_' not in '/' + ref:
                continue
            name = path.stem
            mode = 'recipe' if name.startswith('COI_Figure_') and name.endswith('_Dataless') else 'baked' if name.startswith('FigureBake_') else None
            if not mode:
                continue
            if mode == 'baked' and (ref, '.glb') not in self.files:
                continue
            code = name[len('COI_Figure_'):-len('_Dataless')] if mode == 'recipe' else name[len('FigureBake_'):]
            # A discovery entry can be incomplete; importing validates its
            # companions before creating anything in Blender.
            entries.append(dict(resource=ref, mode=mode, code=code, label=self.labels.get(code, code), source=str(path)))
        index_path = self.root / 'lego-fortnite-index.json'
        if index_path.is_file():
            index = json.loads(index_path.read_text(encoding='utf-8'))
            if index.get('schema') != 'tt-workshop.lego-fortnite-index.v1':
                raise ValueError('Unknown LEGO Fortnite inventory schema')
            existing = {v['resource'].casefold(): v for v in entries}
            for value in index['entries']:
                if value.get('mode') not in ('recipe', 'baked') or not all(isinstance(value.get(k), str) for k in ('resource', 'code', 'label', 'backend_resource')):
                    raise ValueError('Invalid LEGO Fortnite inventory entry')
                key = value['resource'].casefold()
                if key in existing:
                    if existing[key]['mode'] != value['mode'] or existing[key]['code'].casefold() != value['code'].casefold():
                        raise ValueError('Conflicting LEGO Fortnite inventory entries for ' + key)
                    existing[key]['backend_resource'] = value['backend_resource']
                    existing[key]['label'] = self.labels.get(value['code'], value['label'])
                else:
                    added = dict(value, resource=key)
                    existing[key] = added
                    entries.append(added)
        return entries

    def plan(self, entry):
        if entry['mode'] == 'baked':
            model = self.object(entry['resource'], 'SkeletalMesh')
            slots = [self.material(v['Material']) for v in model.get('SkeletalMaterials', [])]
            if not slots:
                raise ValueError('Baked model has no material references')
            for props in slots:
                for key in ('Tex Color D','Tex Deco D','Tex Normal','Tex Background-D','Tex Foreground-D'):
                    if props.get(key):
                        self.file(props[key], '.png')
                        self.file(props[key], '.json')
            return dict(mode='baked', meshes=[dict(path=self.file(entry['resource'], '.glb'), materials=slots)], entry=entry)
        descriptor = self.object(entry['resource'], 'CustomizableObjectInstance')['Properties']['Descriptor']
        ints = {v['ParameterName']: v['ParameterValueName'] for v in descriptor.get('IntParameters', [])}
        if ints.get('Body Selector') != 'Default' or ints.get('Body Material Type') != 'Default':
            raise ValueError('This Mutable body selector/material is not supported; export an assembled baked model instead')
        floats = {v['ParameterName']: v['ParameterValue'] for v in descriptor.get('FloatParameters', [])}
        textures = {v['ParameterName']: v['ParameterValue'] for v in descriptor.get('TextureParameters', [])}
        mesh_params = {v['ParameterName']: v['ParameterValue'] for v in descriptor.get('SkeletalMeshParameters', []) if v.get('ParameterValue')}
        unsupported = set(mesh_params) - {'Head SKM', 'Head Acc SKM', 'Head Acc Extra SKM'}
        if unsupported:
            raise ValueError('Unverified replacement/attachment roles: ' + ', '.join(sorted(unsupported)))
        for side in ('l', 'r'):
            if floats.get('arm_' + side + 'u Color') != floats.get('arm_' + side + 'l Color'):
                raise ValueError('Split upper/lower arm color layout needs validation for this recipe')
        material_params = {v['ParameterName']: v['ParameterValue'] for v in descriptor.get('MaterialParameters', [])}
        head = material_params.get('Head Material')
        if not head:
            raise ValueError('Recipe has no declared Head Material reference; its filename cannot be inferred safely')
        head_material = self.material(head)
        meshes = [dict(path=self.file('SKM_Figure_Preview', '.glb'), role='body')]
        for role, value in mesh_params.items():
            meshes.append(dict(path=self.file(value, '.glb'), role=role))
        if 'Head SKM' not in mesh_params:
            raise ValueError('Recipe has no verified head mesh')
        color = head_color(descriptor, head_material, mesh_params['Head SKM'])
        result = dict(mode='recipe', entry=entry, meshes=meshes, floats=floats, textures=textures, head_material=head_material,
                      head_color=color, lut=self.file('T_LUT_Default', '.png'))
        # Preflight all textures used by this shader reconstruction.
        used = [textures.get('Body Deco D'), textures.get('Body Normal')]
        used += [head_material.get(k) for k in ('Tex Background-D', 'Tex Foreground-D','Tex Normal')]
        for role in mesh_params:
            if role != 'Head SKM':
                prefix = role.removesuffix(' SKM')
                used += [textures.get(prefix + ' Deco D'), textures.get(prefix + ' Normal')]
        for value in used:
            if value:
                self.file(value, '.png')
                self.file(value, '.json')
        return result
