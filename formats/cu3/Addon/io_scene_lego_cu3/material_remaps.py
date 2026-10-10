"""Observed additive preview layers for explicit PC NXG/DX11 layouts.

This does not choose a replacement shader variant. Only bindings identical
across every exact-name candidate can be used by the inspection renderer.
The native vertex-color predicate is separately gated. Metallic/BRDF layers
and native emission intensity remain untranslated.
"""
from .cu3 import FormatError


def native_vertex_glow(entry, mesh_version):
    """Observed vertex-color additive surfaces; shaded/env glow is separate."""
    fields=entry['fields']
    return ((mesh_version,entry.get('table_version')) in {(169,177),(175,202)}
            and fields.get('version')==2 and fields.get('shaderVersion')==4
            and fields.get('glow')==1 and fields.get('shadedGlow')==0
            and fields.get('layerBlendDiffuse0')==2 and fields.get('layerBlendDiffuse1')==0
            and fields.get('vertAlbedo')==1 and entry['texture_ids'][0]<0
            and entry['texture_ids'][1]<0)


def shared_glow_binding(materials, name, mesh_version):
    if mesh_version != 169 or not isinstance(name, str) or not name:
        return None
    candidates = [entry for entry in materials if entry['name'] == name]
    if not candidates:
        raise FormatError('Declared replacement material name is absent from its resource')
    bindings = []
    for entry in candidates:
        fields = entry['fields']
        if (entry.get('table_version') != 176 or fields.get('version') != 2
                or fields.get('shaderVersion') != 4 or fields.get('glow') != 1
                or fields.get('shadedGlow') != 0 or fields.get('layerBlendDiffuse0') != 2
                or fields.get('layerBlendDiffuse1') != 0):
            return None
        textures, uvs = entry['texture_ids'], fields.get('uvSets', [])
        if len(textures) < 2 or len(uvs) < 2:
            raise FormatError('Replacement glow layer has incomplete texture/UV fields')
        enabled, uv = uvs[1]
        if textures[1] < 0 or enabled != 1 or uv not in range(16):
            raise FormatError('Replacement glow layer has no usable native texture/UV binding')
        bindings.append((textures[1], uv))
    if len(set(bindings)) != 1:
        raise FormatError('Replacement variants disagree on the glow texture/UV binding')
    texture, uv = bindings[0]
    return dict(texture=texture, uv=uv, candidates=len(candidates),
                scope='Common additive-layer binding only; no native shader variant selected')
