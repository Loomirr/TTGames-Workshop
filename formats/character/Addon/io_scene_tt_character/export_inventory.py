"""Preserve the imported assembly when writing layout-preserving native edits.

The writer cannot add/remove draws or character attachment definitions. Keep a
small, name-independent inventory so those changes cannot look like successful
exports of the unchanged source files. Whole source-model copies remain valid
when every instance proposes identical native bytes.
"""
from collections import Counter
import json
from ._core.cu3 import FormatError
from .source_bundle import canonical_source


SCHEMA = 'tt.native-export-inventory.v1'


def _draws(owner):
    rows = []
    for obj in owner.children:
        if obj.type != 'MESH':
            continue
        if not obj.get('tt_vertex_transform'):
            raise FormatError('New or unbound mesh cannot be encoded to a native source: ' + obj.name)
        rows.append([obj.get('source_part'), obj.get('source_special'),
                     obj.get('tt_native_rigid_joint'), obj['tt_vertex_transform']])
    return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True))


def _models(rig):
    return [obj for obj in [rig] + list(rig.children_recursive) if obj.get('tt_native_source')]


def _counts(models):
    return dict(Counter(str(canonical_source(obj['tt_native_source'])) for obj in models))


def bind_inventory(rig, *, import_issues=()):
    """Bind after the complete character assembly succeeds, never on export."""
    models = _models(rig)
    for owner in models:
        owner['tt_native_export_draws'] = json.dumps(dict(schema=SCHEMA, draws=_draws(owner)))
    rig['tt_native_export_inventory'] = json.dumps(dict(schema=SCHEMA, sources=_counts(models),
                                                      import_issues=list(import_issues)))


def _read(text, description):
    try:
        value = json.loads(text)
    except (ValueError, TypeError) as error:
        raise FormatError('Invalid native export ' + description + '; reimport the character') from error
    if not isinstance(value, dict) or value.get('schema') != SCHEMA:
        raise FormatError('Unknown native export ' + description + '; reimport the character')
    return value


def check_inventory(rig):
    models = _models(rig)
    warnings = []
    for obj in [rig] + list(rig.children_recursive):
        if getattr(obj, 'mode', 'OBJECT') == 'EDIT':
            raise FormatError('Leave Edit Mode before native export so pending edits are applied: ' + obj.name)
    baseline = rig.get('tt_native_export_inventory')
    if baseline is None:
        warnings.append('This older import has no assembly inventory. Deleted meshes or attachments cannot be checked; reimport with the current addon.')
        return dict(checked=False, warnings=warnings)
    inventory = _read(baseline, 'assembly inventory')
    expected = inventory.get('sources')
    if not isinstance(expected, dict) or not all(isinstance(key, str) and type(count) is int and count > 0 for key, count in expected.items()):
        raise FormatError('Invalid native source-instance inventory; reimport the character')
    actual = _counts(models)
    for source, count in expected.items():
        if actual.get(source, 0) < count:
            raise FormatError('Native model or attachment was removed or detached; character-definition editing is unsupported: ' + source)
    meshes = set()
    for owner in models:
        if str(canonical_source(owner['tt_native_source'])) not in expected:
            raise FormatError('Adding a native model requires character-definition editing: ' + owner.name)
        bound = _read(owner.get('tt_native_export_draws'), 'draw inventory')
        if bound.get('draws') != _draws(owner):
            raise FormatError('Native meshes were added, removed, duplicated, reparented or rebound; draw-table editing is unsupported: ' + owner.name)
        meshes.update(child.as_pointer() if hasattr(child, 'as_pointer') else id(child)
                      for child in owner.children if child.type == 'MESH')
    for obj in rig.children_recursive:
        identity = obj.as_pointer() if hasattr(obj, 'as_pointer') else id(obj)
        if obj.type == 'MESH' and identity not in meshes:
            raise FormatError('Mesh is outside its imported native model hierarchy: ' + obj.name)
    omissions = inventory.get('import_issues', [])
    if not isinstance(omissions, list) or not all(isinstance(item, str) for item in omissions):
        raise FormatError('Invalid original import diagnostics in native export inventory')
    if omissions:
        warnings.append('The original import reported omissions. The bundle contains consumed resources; it is not a complete dependency dump.')
    return dict(checked=True, model_instances=sum(actual.values()), mesh_draws=len(meshes),
                import_issues=omissions, warnings=warnings)
