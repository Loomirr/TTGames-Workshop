"""Read-only sampler/constant evidence for observed UMTL 176/177 records.

Written independently from original byte spans. Field-name candidates were
cross-checked against JaanDev's UMTL format notes; this is not a shader port.
Other versions retain an explicit unsupported status. No renderer uses these
values until its layout, units and shader operation are separately validated.
"""
import hashlib
import math
import struct


def inspect_parameters(data, entry):
    start, end = entry['texture_end'], entry['name_offset']
    if not 0 <= start <= end <= len(data):
        raise ValueError('Material parameter span is outside the source snapshot')
    raw = data[start:end]
    result = dict(status='unverified_layout', offset=start, end=end,
                  bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                  renderer_application='None; parameter units and shader operations remain unverified')
    if entry['table_version'] not in (176, 177):
        result['reason'] = 'Parameter layout is not validated for this UMTL version'
        return result
    if len(raw) != 492 or struct.unpack_from('>I', raw)[0] != 13:
        result['reason'] = 'Expected the observed 492-byte, 13-sampler parameter record'
        return result
    samplers = []
    for index in range(13):
        anisotropy = struct.unpack_from('>I', raw, 4+4*index)[0]
        bias = struct.unpack_from('>f', raw, 56+4*index)[0]
        auxiliary = struct.unpack_from('>I', raw, 108+4*index)[0]
        if anisotropy > 16 or not math.isfinite(bias):
            result['reason'] = 'Sampler values are outside the observed layout'
            return result
        samplers.append(dict(index=index, max_anisotropy=anisotropy,
                             mipmap_bias=bias, auxiliary_raw=auxiliary))
    if raw[264] not in (0, 1):
        result['reason'] = 'Unverified bitangent-flip scalar'
        return result
    # Offsets are relative to the independently bounded texture/name interval.
    # Retain an explicit naming status: numeric parity is not rendering parity.
    offsets = {'normal_layer_scale': (265, 3), 'parallax': (277, 1),
               'parallax_bias': (281, 1), 'refractive_index': (313, 1),
               'refractive_thickness': (317, 1), 'glow': (321, 1),
               'reflectivity': (329, 1), 'specular_cos_power': (333, 1),
               'environment': (337, 1), 'environment_lighting': (341, 1),
               'environment_alpha_hdr': (345, 1), 'fresnel': (349, 1),
               'fresnel_power': (353, 1), 'brdf_roughness': (393, 1),
               'brdf_secondary': (397, 1)}
    constants = {}
    for name, (offset, count) in offsets.items():
        values = list(struct.unpack_from('>'+str(count)+'f', raw, offset))
        if not all(math.isfinite(value) for value in values):
            result['reason'] = 'Non-finite parameter scalar; block remains uninterpreted'
            return result
        constants[name] = dict(offset=start+offset, values=values)
    result.update(status='observed_layout_decoded', byte_order='big',
                  samplers=samplers, bitangent_flip_raw=raw[264], constants=constants,
                  field_naming='Candidates from format documentation, corroborated by original record spans; no enum/renderer translation',
                  unreported_bytes='Other animation, integer and shader controls remain uninterpreted')
    return result
