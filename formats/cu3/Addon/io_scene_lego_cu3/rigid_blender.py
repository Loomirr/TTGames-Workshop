"""Observed LB3 rigid tracks with absolute rotation/scale and anchor-relative motion.

This gate covers the source-matrix-matching tracks observed in the sewer
segment. It deliberately rejects other conventions until independently checked.
"""
from mathutils import Matrix, Vector
from .cu3 import FormatError
from .blender_import import C, CI, row_matrix, rotations


def rigid_samples(cut, record):
    anim = record['animation']
    anim.prepare(scene_channels=True)
    if cut.version != 19 or anim.nodes != 1 or anim.curves not in (6, 9) or anim.node_flags[0] not in (1, 3, 11):
        raise FormatError('Rigid transform convention has not been verified for this track')
    base = row_matrix(cut.matrices[record['matrix_index']])
    location, rotation, scale = base.decompose()
    first = anim.sample(0)[0]
    first_rotation = rotations(anim, 0)[0]
    if abs(first_rotation.dot(rotation)) < 1-1e-5 or max(abs(x) for x in first[:3]) > .01:
        raise FormatError('Rigid track does not match the verified anchored convention')
    if anim.curves == 9 and max(abs(a-b) for a,b in zip(scale,first[6:9])) > 1e-4:
        raise FormatError('Rigid scale and its source anchor disagree')
    if max(abs(base[a][b] - Matrix.LocRotScale(location, rotation, scale)[a][b]) for a in range(4) for b in range(4)) > 1e-4:
        raise FormatError('Sheared rigid anchor is not supported')
    result = []
    for frame in range(cut.frames):
        values = anim.sample(frame)[0]
        position = location + Vector((values[0], values[1], -values[2]))
        own_scale = Vector(values[6:9]) if anim.curves == 9 else scale
        result.append(C @ Matrix.LocRotScale(position, rotations(anim,frame)[0], own_scale) @ CI)
    return result
