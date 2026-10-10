"""Rest-relative rotation transfer without Blender, Euler angles or game guesses.

Input/output matrices use native row-vector order. The axis bridge is an
explicit rotation from source delta coordinates to target delta coordinates.
Root motion, translation, scale animation and hierarchy changes are separate.
"""
import math


IDENTITY = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]


def _matrix(values):
    if (not isinstance(values, (list, tuple)) or len(values) != 16 or
            any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                not math.isfinite(v) for v in values)):
        raise ValueError("Expected 16 finite row-major matrix values")
    # Transpose the serialized row-vector matrix into column-vector algebra.
    matrix = [[float(values[j * 4 + i]) for j in range(4)] for i in range(4)]
    if max(abs(matrix[3][i] - (1 if i == 3 else 0)) for i in range(4)) > 1e-6:
        raise ValueError("Expected an affine native transform")
    return matrix


def _flat(matrix):
    return [matrix[j][i] for i in range(4) for j in range(4)]


def _multiply(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4))
             for j in range(4)] for i in range(4)]


def _inverse(matrix):
    rows = [row[:] + [float(i == j) for j in range(4)]
            for i, row in enumerate(matrix)]
    for column in range(4):
        pivot = max(range(column, 4), key=lambda i: abs(rows[i][column]))
        if abs(rows[pivot][column]) < 1e-12:
            raise ValueError("Singular native transform")
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        rows[column] = [v / divisor for v in rows[column]]
        for i in range(4):
            if i != column:
                factor = rows[i][column]
                rows[i] = [a - factor * b for a, b in zip(rows[i], rows[column])]
    return [row[4:] for row in rows]


def _rigid_rotation(matrix, label):
    rotation = [row[:3] for row in matrix[:3]]
    error = max(abs(sum(rotation[k][i] * rotation[k][j] for k in range(3)) -
                    (1 if i == j else 0)) for i in range(3) for j in range(3))
    a, b, c = rotation
    determinant = (a[0] * (b[1] * c[2] - b[2] * c[1]) -
                   a[1] * (b[0] * c[2] - b[2] * c[0]) +
                   a[2] * (b[0] * c[1] - b[1] * c[0]))
    if error > 1e-5 or abs(determinant - 1) > 1e-5:
        raise ValueError(label + " must be a proper rotation; scale/shear/reflection needs a separate policy")


def validate_axis_bridge(values):
    bridge = _matrix(values)
    _rigid_rotation(bridge, "Axis bridge")
    if max(abs(bridge[i][3]) for i in range(3)) > 1e-6:
        raise ValueError("Axis bridge must not contain translation")
    return values


def transfer_local_rotation(source_rest, target_rest, source_pose, axis_bridge):
    """Transfer a rotation delta, retaining target rest translation and scale.

Column-vector equation: Pt = Rt * B * rotation(Rs^-1 * Ps) * B^-1.
The caller must explicitly choose B and verify mapped hierarchy/rest ownership.
Source pose translation is intentionally excluded, not applied to the target.
Animated source scale/shear/reflection is refused rather than normalized away.
"""
    source, target, pose = map(_matrix, (source_rest, target_rest, source_pose))
    _inverse(target)  # Verify even a rest-only target is invertible.
    validate_axis_bridge(axis_bridge)
    bridge = _matrix(axis_bridge)
    delta = _multiply(_inverse(source), pose)
    _rigid_rotation(delta, "Rest-relative pose delta")
    for i in range(3):
        delta[i][3] = 0.0
    mapped = _multiply(_multiply(bridge, delta), _inverse(bridge))
    return _flat(_multiply(target, mapped))
