"""Sample authored normals for a frozen shader-lab pose, without normalization."""
import math
from mathutils import Vector
from shader_reference import tangent_light_vectors


def posed_normals(normals, rigid_bone, weights, poses, binds):
    if len(poses) != len(binds) or len(normals) != len(weights):
        raise ValueError('Shader pose tables have inconsistent lengths')
    if rigid_bone is not None and not 0 <= rigid_bone < len(poses):
        raise ValueError('Shader attachment bone is outside the pose')
    if not all(math.isfinite(v) for matrix in (*poses, *binds) for row in matrix for v in row):
        raise ValueError('Non-finite shader pose matrix')
    if any(abs(matrix.determinant()) < 1e-12 for matrix in binds):
        raise ValueError('Singular shader bind matrix')
    skin = [(pose @ rest.inverted()).to_3x3() for pose, rest in zip(poses, binds)]
    result = []
    for normal, influences in zip(normals, weights):
        if len(normal) != 3 or not all(math.isfinite(v) for v in normal):
            raise ValueError('Invalid source shader normal')
        vector = Vector((normal[0], normal[2], normal[1]))
        if rigid_bone is not None:
            result.append(poses[rigid_bone].to_3x3() @ vector)
            continue
        if (not influences or any(not isinstance(index,int) or not 0 <= index < len(skin)
                                  or not math.isfinite(weight) or weight < 0
                                  for index,weight in influences.items())
                or abs(sum(influences.values())-1) > 1e-4):
            raise ValueError('Invalid shader skin weights')
        result.append(sum((skin[index] @ vector * weight for index,weight in influences.items()), Vector()))
    return result


def bump_corner_lights(part, poses, binds, lights, *, normalize_reflection_normal=False, native_tangents=None):
    """Frozen inputs using explicit native tangents or the MikkTSpace hypothesis.

    Generate tangents in SOURCE coordinates/UVs, then transform T, T cross N and
    N separately as the shader does. Do not use Blender's bitangent sign or its
    flipped-V image coordinates to invent a native tangent convention.
    """
    import bpy
    scratch = bpy.data.meshes.new('Temporary shader tangent hypothesis')
    try:
        scratch.from_pydata(part['vertices'], [], part['faces']); scratch.update()
        uv = scratch.uv_layers.new(name='Native UV')
        normals, weights = [], []
        for poly in scratch.polygons:
            poly.use_smooth = True
        for loop in scratch.loops:
            index = loop.vertex_index
            uv.data[loop.index].uv = part['uvs'][index]
            normals.append(Vector(part['normals'][index]))
            weights.append(part['weights'][index])
        if any(v.length < 1e-12 for v in normals):
            raise ValueError('Bump comparison needs nonzero authored normals')
        if native_tangents is None:
            scratch.normals_split_custom_set([v.normalized() for v in normals])
            scratch.calc_tangents(uvmap=uv.name)
            tangents = [loop.tangent.copy() for loop in scratch.loops]
        else:
            if len(native_tangents)!=len(part['vertices']):raise ValueError('Native tangent table size differs')
            if any(native_tangents[loop.vertex_index] is None for loop in scratch.loops):
                raise ValueError('Native tangent depends on an untouched runtime scratch slot')
            tangents=[Vector(native_tangents[loop.vertex_index]) for loop in scratch.loops]
        bitangents = [t.cross(n) for t,n in zip(tangents,normals)]
        transformed = [posed_normals(vectors,part['rigid_bone'],weights,poses,binds)
                       for vectors in (tangents,bitangents,normals)]
        if normalize_reflection_normal:
            if any(n.length<1e-12 for n in transformed[2]):
                raise ValueError('Reflection normal transformed to zero')
            transformed[2]=[n.normalized() for n in transformed[2]]
        return [tangent_light_vectors(t,b,n,lights) for t,b,n in zip(*transformed)]
    finally:
        bpy.data.meshes.remove(scratch)
