"""Report decoded material controls that the inspection shader does not apply.

This module does not interpret unknown native enums or expand renderer/layout
support. Retained values let an original-file audit distinguish an unsupported
declaration from an absent one without inspecting Blender node graphs.
"""
from copy import deepcopy
from .native_materials import costume_slot


UNTRANSLATED_SHADER_FIELDS = (
    'substanceMode', 'roughnessMode', 'fresnelAlphaMode', 'reflection',
    'refraction', 'glow', 'shadedGlow', 'metallicSpecular', 'nextGenShine',
    'carpaint', 'layerBlendDiffuse0', 'layerBlendDiffuse1',
    'layerBlendDiffuse2', 'layerBlendDiffuse3', 'layerBlendSpecular0',
    'layerBlendSpecular1', 'layerBlendSpecular2', 'layerBlendNormal0',
    'layerBlendNormal1', 'layerBlendNormal2', 'usesDiffuseLayerColour0',
    'usesDiffuseLayerColour1', 'usesDiffuseLayerColour2',
    'usesDiffuseLayerColour3',
)


def _declaration(index, obj, used=()):
    fields = obj['fields']
    return {
        'object_index': index, 'class': obj.get('class'),
        'offset': obj.get('offset'), 'complete': obj.get('complete'),
        'decoded_end': obj.get('decoded_end'),
        'decoded_fields': deepcopy(fields),
        'used_fields': sorted(set(used) & fields.keys()),
        'unapplied_fields': sorted(fields.keys() - set(used)),
    }


def material_capability_report(model, entry, definition=None, *,
                               used_definition_fields=None,
                               normal_binding=None, normal_applied=False):
    """Return an actionable diagnostic, or None when no omission is detected.

    ``used_definition_fields`` maps CD object indices to fields actually used
    by the caller. A Material selector counts as used for routing, not as a
    translated native shader. Other fields count only after successful use.
    Material-remap class names identify report inventory, never rendering rules.
    Unknown enum values and unparsed definition tails remain uninterpreted.
    """
    used_definition_fields = used_definition_fields or {}
    slot = costume_slot(entry)
    fields = entry['fields']
    controls = {name: deepcopy(fields[name]) for name in UNTRANSLATED_SHADER_FIELDS if name in fields}
    # Nonzero values are evidence to retain and inspect, not decoded meanings.
    nonzero = [name for name, value in controls.items() if value is not None and value != 0]
    declarations, unresolved = [], []
    roles = {costume_slot(material) for material in model.get('materials', [entry])}
    roles.discard(None)
    for index, obj in enumerate(definition.get('objects', []) if definition else []):
        values = obj['fields']
        if slot is not None and values.get('Material') == slot:
            declarations.append(_declaration(index, obj, used_definition_fields.get(index, ())))
        else:
            name = obj.get('class', '').casefold()
            if 'material' in name and 'remap' in name and values.get('Material') not in roles:
                row = _declaration(index, obj)
                row['reason'] = 'No decoded Material selector matches a supported costume role in this model'
                unresolved.append(row)

    surface_keys = ('surfaceMapMethod', 'surfaceMapFormat0', 'surfaceMapFormat1',
                    'surfaceMapFormat2', 'surfaceMapFormat3', 'surfaceMapFormatVTFN')
    surface_fields = {name: deepcopy(fields[name]) for name in surface_keys if name in fields}
    textures, uvs = entry.get('texture_ids', []), fields.get('uvSets', [])
    texture = textures[6] if len(textures) > 6 else None
    method = fields.get('surfaceMapMethod')
    surface_declared = (method is not None and method != 0) or (texture is not None and texture >= 0)
    surface = dict(decoded_fields=surface_fields, texture_slot_6=texture,
                   uv_pair_4=deepcopy(uvs[4]) if len(uvs) > 4 else None,
                   verified_normal_binding=deepcopy(normal_binding),
                   normal_applied=bool(normal_applied))
    if normal_binding is not None:
        surface['status'] = 'applied' if normal_applied else 'verified_binding_not_applied'
    else:
        surface['status'] = 'unbound_declaration' if surface_declared else 'no_surface_declaration'

    issues = []
    unapplied = [row for row in declarations if row['unapplied_fields']]
    if unapplied:
        issues.append('Decoded costume/material fields were not applied; see each declaration\'s unapplied_fields')
    if any(row['complete'] is False for row in declarations):
        issues.append('A material declaration has an undecoded tail; nested controls are not reconstructed')
    if unresolved:
        issues.append('Material-remap declarations could not be associated with a supported costume role')
    if nonzero:
        issues.append('Nonzero native shader controls have no Blender translation: ' + ', '.join(nonzero))
    if surface['status'] == 'unbound_declaration':
        issues.append('Native surface-map declaration has no verified Blender normal binding; selectors are retained without guessing its encoding')
    elif surface['status'] == 'verified_binding_not_applied':
        issues.append('Verified normal binding was not applied; texture loading or normal-node creation did not complete')
    if not issues:
        return None
    return {
        'kind': 'material_capabilities', 'material': entry['name'],
        'material_index': entry.get('index'), 'source': str(model['source']),
        'mesh_version': model['mesh_version'], 'material_table_version': entry.get('table_version'),
        'costume_role': slot, 'issue': '; '.join(issues),
        'definition_source': definition.get('source') if definition else None,
        'definition_declarations': declarations, 'unresolved_material_remaps': unresolved,
        'untranslated_shader_controls': controls,
        'nonzero_untranslated_shader_controls': nonzero,
        'surface_map': surface,
        'scope': 'Inspection shader omissions, not native enum meanings or a material-remap implementation',
    }
