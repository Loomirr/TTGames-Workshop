"""Experimental LSW1 ANI local transforms; no automatic clip ownership.

Row-vector matrices follow the observed PC track evaluator. Game overrides,
animation blending, root motion and gameplay timing are outside this module.
"""
import math
import struct


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def multiply(a, b):
    return tuple(sum(a[r*4+k] * b[k*4+c] for k in range(4))
                 for r in range(4) for c in range(4))


IDENTITY = (1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.)


def local_transform(values, flags, joint=IDENTITY, pivot=(0., 0., 0.),
                    joint_flags=0, parent_scale=(1., 1., 1.)):
    """Return native local matrix and inherited scale for one sampled track.

    Inputs are serialized ANI values, HGP joint orientation/pivot and parent scale.
    No per-bone game override structure is accepted. The sine table is synthesized;
    its initialization and original floating-point precision remain a limitation.
    """
    if len(values) != 9 or len(joint) != 16 or len(pivot) != 3 or len(parent_scale) != 3:
        raise ValueError('Invalid transform dimensions')
    if not all(math.isfinite(v) for v in (*values, *joint, *pivot, *parent_scale)):
        raise ValueError('Non-finite animation transform')
    if flags & ~0x7b or joint_flags & ~9:
        raise ValueError('Unknown ANI or HGP joint flags')
    if flags & 0x10 and any(abs(v) < 1e-12 for v in parent_scale):
        raise ValueError('Cannot compensate zero or near-zero parent scale')
    values = tuple(f32(v) for v in values)
    if flags & 1:
        # Original radians -> integer turns -> 32768-entry lookup addressing.
        turns = [int(v * 10430.3779296875) for v in values[3:6]]
        if any(abs(v) > 0x7fffffff for v in turns):
            raise ValueError('Rotation exceeds native integer conversion range')
        sine = lambda i: f32(math.sin(((i >> 1) & 32767) * math.tau / 32768))
        sx, sy, sz = (sine(v) for v in turns)
        cx, cy, cz = (sine(v + 16384) for v in turns)
        rotation = (cy*cz, cy*sz, -sy, 0.,
                    sx*sy*cz-cx*sz, sx*sy*sz+cx*cz, sx*cy, 0.,
                    cx*sy*cz+sx*sz, cx*sy*sz-sx*cz, cx*cy, 0.,
                    0., 0., 0., 1.)
    else:
        rotation = IDENTITY
    if flags & 0x20:
        rotation = multiply(rotation, joint)
    scale = values[6:9] if flags & 8 else (1., 1., 1.)
    matrix = list(rotation)
    for row in range(3):
        for column in range(3):
            matrix[row*4+column] *= scale[row]
            if flags & 0x10:
                # Original helper 0x495980 scales columns, after the track's
                # own row scaling. Translation is added later and stays intact.
                matrix[row*4+column] /= parent_scale[column]
    matrix[12:15] = values[:3]
    if joint_flags & 8:
        for column in range(3):
            matrix[12+column] += sum(pivot[k]*matrix[k*4+column] for k in range(3)) - pivot[column]
    # Native coordinate handedness conversion, applied after pivot handling.
    for index in (2, 6, 8, 9, 11, 14):
        matrix[index] = -matrix[index]
    inherited = scale if flags & 0x10 else tuple(a*b for a, b in zip(scale, parent_scale))
    return tuple(matrix), inherited


def sample_pose(model, clip, time, track_bones):
    """Explicit complete mapping only; counts alone never create a binding."""
    if clip.family != 'ANI' or clip.tracks != model.count:
        raise ValueError('Preview requires an ANI with a complete explicit skeleton binding')
    if list(track_bones) != [bone['name'] for bone in model.bones]:
        raise ValueError('Explicit track binding disagrees with the native bone order')
    worlds, scales = [], []
    for index, bone in enumerate(model.bones):
        at = model.joints_at + index * 0x60
        parent = bone['parent']
        matrix, scale = local_transform(
            [clip.evaluate_channel(index, c, time) for c in range(9)], clip.flags[index],
            model.floats(at, 16), model.floats(at+0x40, 3), model.body[at+0x51],
            scales[parent] if parent >= 0 else (1., 1., 1.))
        worlds.append(multiply(matrix, worlds[parent]) if parent >= 0 else matrix)
        scales.append(scale)
    return worlds
