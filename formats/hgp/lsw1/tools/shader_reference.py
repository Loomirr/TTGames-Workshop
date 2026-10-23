"""Arithmetic reference for the observed ordinary LSW1 PC ps_2_0 programs.

Effect candidates 9, 15 and 19 share these pixel equations. Inputs are shader
numbers, before any display conversion; this does not choose a runtime pass,
prepare vertices, filter textures or reproduce GPU partial-precision behavior.
"""
import math


def vector(values, size, label):
    result = tuple(float(value) for value in values)
    if len(result) != size or not all(math.isfinite(value) for value in result):
        raise ValueError(f'{label} needs {size} finite components')
    return result


def lighting_inputs(ambient, lights):
    ambient = vector(ambient, 3, 'Ambient color')
    lights = tuple((vector(direction, 3, 'Light direction'), vector(color, 3, 'Light color'))
                   for direction, color in lights)
    if len(lights) != 3:
        raise ValueError('The observed shader has exactly three directional lights')
    return ambient, lights


def native_lighting(ambient_rgba, directions, colors_rgba):
    """Observed draw-item light block -> shader RGB, in native coordinates.

    Native upload halves ambient and directional RGB without clamping, gamma
    conversion or direction normalization. W is uploaded separately and is not
    used by the reviewed RGB lighting equations. This does not select a level's
    light block or evaluate the game's light interpolation.
    """
    ambient = vector(ambient_rgba, 4, 'Native ambient RGBA')
    directions = tuple(vector(value, 3, 'Native light direction') for value in directions)
    colors = tuple(vector(value, 4, 'Native light RGBA') for value in colors_rgba)
    if len(directions) != 3 or len(colors) != 3:
        raise ValueError('Native lighting needs three directions and three colors')
    return tuple(value*.5 for value in ambient[:3]), tuple(
        (direction, tuple(value*.5 for value in color[:3]))
        for direction, color in zip(directions, colors))


def shadow_receiver_pixel(vertex_rgba, projected_w, incidence, shadow_rgba, attenuation_rgba, texture=None):
    """Observed shadow receiver color output, given already sampled maps.

    This is not depth-map generation or pass selection. The textured branch
    uses RGB shadow samples; the untextured branch uses their red component.
    """
    vertex=vector(vertex_rgba,4,'Receiver vertex color')
    shadow=vector(shadow_rgba,4,'Shadow sample');attenuation=vector(attenuation_rgba,4,'Attenuation sample')
    projected_w,incidence=vector((projected_w,incidence),2,'Shadow projection and incidence')
    occlusion=tuple(0. if projected_w<=0 else (1.-v)*incidence for v in shadow[:3])
    if texture is None:
        factor=1.-.25*occlusion[0]*attenuation[0]
        return tuple(v*factor for v in vertex[:3])+(min(1.,max(0.,2*vertex[3])),)
    texture=vector(texture,4,'Receiver texture')
    rgb=tuple(2*v*t*(1.-.25*o*a) for v,t,o,a in zip(vertex,texture,occlusion,attenuation))
    return tuple(min(1.,max(0.,v)) for v in rgb)+(min(1.,max(0.,2*vertex[3]*texture[3])),)


def ordinary_pixel(material_rgb, vertex_alpha, normal, ambient, lights, texture=None):
    """Return shader RGBA for a sampled texel, or the untextured variant.

    material_rgb is the original material value, before the verified upload
    branch halves it for textured draws. Neither light directions nor the
    interpolated normal are normalized by these pixel programs.
    """
    material_rgb = vector(material_rgb, 3, 'Material color')
    normal = vector(normal, 3, 'Interpolated normal')
    ambient, lights = lighting_inputs(ambient, lights)
    vertex_alpha = float(vertex_alpha)
    if not math.isfinite(vertex_alpha) or not 0 <= vertex_alpha <= 1:
        raise ValueError('Vertex alpha must be finite and between zero and one')
    light = list(ambient)
    for direction, color in lights:
        amount = max(0., sum(a * b for a, b in zip(normal, direction)))
        light = [total + amount * channel for total, channel in zip(light, color)]
    if texture is None:
        return tuple(a * b for a, b in zip(material_rgb, light)) + (min(1., 2 * vertex_alpha),)
    texture = vector(texture, 4, 'Texture sample')
    if not 0 <= texture[3] <= 1:
        raise ValueError('Texture alpha must be between zero and one')
    # Preserve the order of the actual upload/pixel stages, including the final
    # clamp. Texture color is not doubled relative to the original material RGB.
    rgb = [min(1., max(0., 2 * (texel * (material * .5) * illumination)))
           for texel, material, illumination in zip(texture, material_rgb, light)]
    return tuple(rgb) + (min(1., 2 * texture[3] * vertex_alpha),)


def check_material(source):
    """Refuse auxiliary/special paths when constructing an ordinary lab preview."""
    if source['effect'] != 0 or source.get('linked_material') or source.get('normal_texture') is not None:
        raise ValueError('Shader lab supports ordinary effect 0 without auxiliary passes')
    if (source['attributes'] >> 16) & 3 == 2:
        raise ValueError('Shader lab does not reconstruct lighting-mode-2 runtime paths')
    if source['attributes'] & 15 not in (0, 1, 2, 10):
        raise ValueError('Shader lab supports only opaque (0/10), source-alpha and additive blending')


def check_legacy_plastic(source):
    """Observed effect-145 fallback with advanced lighting explicitly disabled."""
    if source['effect'] != 145:
        raise ValueError('Legacy plastic experiment requires material effect 145')
    # Retain every ordinary geometry/material restriction, including auxiliaries.
    check_material(dict(source, effect=0))


def bump_pixel(material_rgb, vertex_alpha, bump_texel, ambient, tangent_lights, texture=None):
    """Observed effects 27/43/47: interpolated tangent light vectors, raw bump RGB.

    Light vectors are normalized at vertices, not here. The sampled bump vector
    is decoded as 2*RGB-1 without normalization. Textured output doubles AFTER
    clamping texture*vertex color and applying lighting; it has no final clamp.
    """
    material_rgb = vector(material_rgb, 3, 'Material color')
    bump = vector(bump_texel, 4, 'Bump sample')
    ambient, tangent_lights = lighting_inputs(ambient, tangent_lights)
    alpha = float(vertex_alpha)
    if not math.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError('Vertex alpha must be finite and between zero and one')
    normal = tuple(2*v-1 for v in bump[:3])
    light = list(ambient)
    for direction, color in tangent_lights:
        amount = max(0., sum(a*b for a,b in zip(normal, direction)))
        light = [a+amount*b for a,b in zip(light, color)]
    if texture is None:
        return tuple(a*b for a,b in zip(material_rgb,light)) + (min(1.,2*alpha),)
    texture = vector(texture, 4, 'Texture sample')
    if not 0 <= texture[3] <= 1:
        raise ValueError('Texture alpha must be between zero and one')
    saturate = lambda value: min(1., max(0., value))
    return tuple(2*saturate(t*m*.5)*l for t,m,l in zip(texture,material_rgb,light)) + (2*saturate(texture[3]*alpha),)


def tangent_light_vectors(tangent, bitangent, normal, lights):
    """Vertex-stage basis projection and normalization, before interpolation."""
    basis = [vector(v,3,'Tangent basis') for v in (tangent,bitangent,normal)]
    _, lights = lighting_inputs((0,0,0), lights)
    result = []
    for direction,_ in lights:
        projected = [sum(a*b for a,b in zip(direction,axis)) for axis in basis]
        length = math.sqrt(sum(v*v for v in projected))
        if length < 1e-12 or not math.isfinite(length):
            raise ValueError('Light projects to a zero or invalid tangent vector')
        result.append(tuple(v/length for v in projected))
    return result


def check_bump_material(source, auxiliary):
    """Opt-in bump-only candidate; advanced reflections must be disabled."""
    if source['effect'] != 135 or not source.get('linked_material'):
        raise ValueError('Bump experiment requires effect 135 and its linked material')
    if (auxiliary.get('effect') != 135 or auxiliary.get('linked_material') or auxiliary.get('texture') is None or
            auxiliary.get('texture_aux') != 0x7fef or auxiliary['attributes'] >> 16 != 0x3f52 or
            source.get('normal_texture') != auxiliary['texture']):
        raise ValueError('Unverified bump auxiliary layout')
    check_material(dict(source, effect=0, linked_material=0, normal_texture=None))


def specular_pixel(material_rgb, vertex_alpha, normal, ambient, lights,
                   specular_texel, strength, texture=None):
    """Observed texture-specular ps_2_0: clamp highlight, then add to diffuse.

    The lookup texture supplies RGB, not a roughness value. Its alpha does not
    change opacity. The sum may exceed one; do not clamp it after addition.
    """
    sample = vector(specular_texel, 4, 'Specular sample')
    strength = float(strength)
    if not math.isfinite(strength) or strength < 0:
        raise ValueError('Specular strength must be finite and nonnegative')
    diffuse = ordinary_pixel(material_rgb, vertex_alpha, normal, ambient, lights, texture)
    return tuple(value + min(1., max(0., 2 * sample[i] * strength))
                 for i, value in enumerate(diffuse[:3])) + (diffuse[3],)


def specular_uv(normal, matrix_rows):
    """Vertex-stage lookup coordinates; interpolate these UVs after evaluation.

    Rows are the four uploaded shader constants. Translation is ignored by the
    original dp3 instructions; all four resulting components enter the length.
    Runtime matrix construction is not inferred from a filename or camera.
    """
    normal = vector(normal, 3, 'Vertex normal')
    rows = tuple(vector(row, 4, 'Specular matrix row') for row in matrix_rows)
    if len(rows) != 4:
        raise ValueError('Specular matrix needs four rows')
    transformed = [sum(a * b for a, b in zip(normal, row[:3])) for row in rows]
    length = math.sqrt(sum(value * value for value in transformed))
    if length == 0 or not math.isfinite(length):
        raise ValueError('Specular matrix maps the normal to an invalid zero-length vector')
    return tuple(.5 + .5 * value / length for value in transformed[:2])


def check_specular_material(source, auxiliary):
    """Select only the observed single texture-specular auxiliary path."""
    if source['effect'] != 129 or not source.get('linked_material'):
        raise ValueError('Texture-specular experiment requires effect 129 and its linked material')
    if source.get('normal_texture') is not None or auxiliary.get('linked_material'):
        raise ValueError('Nested or normal-map auxiliary passes are outside this experiment')
    if auxiliary['effect'] != 129 or auxiliary.get('texture') is None:
        raise ValueError('Texture-specular auxiliary needs its original lookup texture')
    if auxiliary['attributes'] >> 16 != 0x3f51:
        raise ValueError('Unverified texture-specular auxiliary layout')
    check_material(dict(source, effect=0, linked_material=0))
    strength = vector(auxiliary['diffuse'], 3, 'Auxiliary color')[0] * .1
    if strength < 0:
        raise ValueError('Invalid negative specular strength')
    return strength


def unit_vector(value, label):
    value = vector(value, 3, label)
    length = math.sqrt(sum(v*v for v in value))
    if length < 1e-12 or not math.isfinite(length):
        raise ValueError(f'{label} must have a finite nonzero length')
    return tuple(v/length for v in value)


def reflection_parameters(material_strength, minimum_scale, maximum_scale):
    """Native SetVector formula; global scale values must be supplied explicitly."""
    strength, low, high = vector((material_strength, minimum_scale, maximum_scale), 3, 'Reflection inputs')
    return vector((.05 + low*strength, high*strength, .2, .8),4,'Computed reflection parameters')


def reflection_terms(normal, to_probe, from_camera, parameters):
    """Pixel-stage cube direction and smooth edge strength for effects 35/44/48.

    Inputs are interpolated vertex outputs. The two view vectors are normalized
    again here. Diffuse lighting separately retains the original normal length.
    """
    normal = unit_vector(normal, 'Reflection normal')
    probe = unit_vector(to_probe, 'Reflection probe vector')
    camera = unit_vector(from_camera, 'Reflection camera vector')
    low, high, start, end = vector(parameters, 4, 'LegoParameters')
    if end <= start:
        raise ValueError('Reflection edge interval must be increasing')
    dot = sum(a*b for a,b in zip(probe, normal))
    reflected = tuple(2*dot*n-p for n,p in zip(normal,probe))
    edge = 1-abs(sum(a*b for a,b in zip(camera,normal)))
    x = min(1.,max(0.,(edge-start)/(end-start)))
    return reflected, low+(high-low)*x*x*(3-2*x)


def reflection_pixel(material_rgb, vertex_alpha, normal, ambient, lights,
                     to_probe, from_camera, parameters, cube_texel, texture=None, *, skinned=False):
    """Observed non-bump reflection pixel shader, including texture-dependent gain."""
    # Reuse ordinary validation and lighting with unit material and no texture.
    light = ordinary_pixel((1,1,1),vertex_alpha,normal,ambient,lights)[:3]
    material_rgb = vector(material_rgb,3,'Material color')
    sample = vector(cube_texel,4,'Cube sample')
    _, strength = reflection_terms(normal,to_probe,from_camera,parameters)
    clamp = (lambda v: v) if skinned else (lambda v: min(1.,max(0.,v)))
    if texture is None:
        return tuple((m+strength*r)*l for m,r,l in zip(material_rgb,sample,light)) + (clamp(2*vertex_alpha),)
    texture = vector(texture,4,'Texture sample')
    if not 0 <= texture[3] <= 1:
        raise ValueError('Texture alpha must be between zero and one')
    rgb = tuple(clamp(2*(t*m*.5+strength*r)*l)
                for t,m,r,l in zip(texture,material_rgb,sample,light))
    return rgb + (clamp(2*texture[3]*vertex_alpha),)


def reflection_vertex(position, camera, player):
    """Rigid reflection vertex inputs, in native Y-up coordinates.

    PlayerPosition is an explicit draw-world translation hypothesis in the lab.
    The preshader shifts the camera down 0.5, then moves the reflection point
    0.5 from PlayerPosition toward that shifted camera. Inputs are normalized
    here and again in the pixel shader, on opposite sides of interpolation.
    """
    position=vector(position,3,'World position')
    camera=vector(camera,3,'Camera position')
    player=vector(player,3,'Player position')
    shifted=(camera[0],camera[1]-.5,camera[2])
    direction=unit_vector(tuple(p-c for p,c in zip(player,shifted)),'Player-camera direction')
    probe=tuple(p-.5*d for p,d in zip(player,direction))
    return (unit_vector(tuple(p-v for p,v in zip(probe,position)),'Vertex-probe direction'),
            unit_vector(tuple(v-c for v,c in zip(position,camera)),'Camera-vertex direction'))


def bump_reflection_pixel(material_rgb,vertex_alpha,normal,ambient,tangent_lights,
                          to_probe,from_camera,parameters,cube_texel,bump_texel,texture=None):
    """Effects 31/45/49: add reflection after bump lighting, without saturation.

    Cube direction varies by the original program: effect 45 uses the opposite
    direction to 31/49. The caller must supply the sample from that direction.
    """
    light=bump_pixel((1,1,1),vertex_alpha,bump_texel,ambient,tangent_lights)[:3]
    material_rgb=vector(material_rgb,3,'Material color')
    sample=vector(cube_texel,4,'Cube sample')
    _,strength=reflection_terms(normal,to_probe,from_camera,parameters)
    if texture is None:
        return tuple(m*l+strength*r for m,l,r in zip(material_rgb,light,sample))+(2*vertex_alpha,)
    texture=vector(texture,4,'Texture sample')
    if not 0<=texture[3]<=1:raise ValueError('Texture alpha must be between zero and one')
    return tuple(2*(t*m*.5*l+strength*r) for t,m,l,r in zip(texture,material_rgb,light,sample))+(2*texture[3]*vertex_alpha,)
