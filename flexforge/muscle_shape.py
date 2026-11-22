# FlexForge - pure shape delta math of the muscle helpers.
# Coordinates and weight dicts in, {bone: {vertex: delta}} out: no bpy, so the
# bake module and the tests share the same numbers. Blender 4.2 and 5.3 free.

from .muscle import MUSCLE_PREFIX
from .weights import EPS

SHAPE_KEY_PREFIX = "flexforge_"
DEFAULT_DISPLACEMENT = 0.05
# Envelope radius assumed when the armature reports none, and the share of it a
# baked muscle may push the surface out: the spike guard.
DEFAULT_BONE_RADIUS = 0.1
MAX_DISPLACEMENT_RATIO = 0.3
GEOMETRY_EPS = 1e-9

class BakeError(Exception):
    """Bake module domain error, with an English message."""

def shape_key_name_for_bone(bone_name):
    """Deterministic key name: `muscle_biceps_01` -> `flexforge_biceps`."""
    name = str(bone_name)
    if name.startswith(MUSCLE_PREFIX):
        name = name[len(MUSCLE_PREFIX):]
    separator = name.rfind("_")
    if separator > 0 and name[separator + 1:].isdigit():
        name = name[:separator]
    if not name:
        raise BakeError("Cannot derive a shape key name from '%s'." % bone_name)
    return SHAPE_KEY_PREFIX + name

def _segment_items(muscle_segments):
    """Accept {bone: (head, tail)} or [(bone, head, tail), ...]."""
    if hasattr(muscle_segments, "items"):
        return list(muscle_segments.items())
    return [(item[0], (item[1], item[2])) for item in muscle_segments]

def _muscle_groups(muscle_segments):
    """Group the segments by muscle: `muscle_biceps_01/02` are one muscle."""
    groups = {}
    for bone_name, _ in _segment_items(muscle_segments):
        groups.setdefault(shape_key_name_for_bone(bone_name), []).append(bone_name)
    return groups

def bone_radius(bone, fallback=DEFAULT_BONE_RADIUS):
    """Envelope radius of a rest bone: the larger of head/tail, else the default."""
    values = [getattr(bone, key, None) for key in ("head_radius", "tail_radius")]
    usable = [value for value in values
              if isinstance(value, (int, float)) and value > 0.0]
    return max(usable) if usable else fallback

def _subtract(point_a, point_b):
    return (point_a[0] - point_b[0], point_a[1] - point_b[1], point_a[2] - point_b[2])

def _dot(point_a, point_b):
    return point_a[0] * point_b[0] + point_a[1] * point_b[1] + point_a[2] * point_b[2]

def _cross(point_a, point_b):
    return (point_a[1] * point_b[2] - point_a[2] * point_b[1],
            point_a[2] * point_b[0] - point_a[0] * point_b[2],
            point_a[0] * point_b[1] - point_a[1] * point_b[0])

def _normalize(vector, fallback):
    """Unit vector, or `fallback` when the input is (almost) zero."""
    length = _dot(vector, vector) ** 0.5
    if length <= GEOMETRY_EPS:
        return fallback
    return (vector[0] / length, vector[1] / length, vector[2] / length)

def _fallback_direction(axis):
    """Deterministic radial direction for points lying on the segment axis."""
    direction = _cross(axis, (0.0, 0.0, 1.0))
    if _dot(direction, direction) <= GEOMETRY_EPS ** 2:
        direction = _cross(axis, (1.0, 0.0, 0.0))
    return _normalize(direction, (1.0, 0.0, 0.0))

def _segment_geometry(muscle_segments, radii):
    """Pre-compute axis, envelope radius and fallback direction per segment."""
    geometry = {}
    for bone_name, (head, tail) in _segment_items(muscle_segments):
        axis = _subtract(tail, head)
        axis_square = _dot(axis, axis)
        if axis_square <= GEOMETRY_EPS ** 2:
            raise BakeError("Degenerate muscle segment for bone '%s'." % bone_name)
        radius = radii.get(bone_name, DEFAULT_BONE_RADIUS)
        if not isinstance(radius, (int, float)) or radius <= 0.0:
            radius = DEFAULT_BONE_RADIUS
        geometry[bone_name] = (tuple(head), axis, axis_square, float(radius),
                               _fallback_direction(axis))
    return geometry

def _blended_sample(point, bone_weights, geometry):
    """Direction, weight sum and blended radius seen by one vertex.

    Every segment of the muscle weighted on the vertex contributes its own
    radial direction, averaged by its skin weight: adjacent segments cross-fade
    instead of stepping. The envelope radius is blended the same way, so the
    displacement cap never jumps from one segment to the next (the stiff bands
    and the low-chest clipping of stacked segments). Return
    (direction, weight_sum, radius, [(bone, weight, own_direction)]).
    """
    blended = [0.0, 0.0, 0.0]
    total = 0.0
    radius = 0.0
    dominant = None
    samples = []
    for bone_name, weight in bone_weights.items():
        head, axis, axis_square, segment_radius, fallback = geometry[bone_name]
        factor = _dot(_subtract(point, head), axis) / axis_square
        factor = min(1.0, max(0.0, factor))
        closest = tuple(head[i] + axis[i] * factor for i in range(3))
        direction = _normalize(_subtract(point, closest), fallback)
        samples.append((bone_name, weight, direction))
        for axis_index in range(3):
            blended[axis_index] += weight * direction[axis_index]
        total += weight
        radius += weight * segment_radius
        if dominant is None or weight > dominant[0]:
            dominant = (weight, direction)
    if dominant is None or total <= EPS:
        return None
    return (_normalize(tuple(blended), dominant[1]), total, radius / total,
            samples)

def compute_muscle_shape_deltas(vertex_coordinates, weights, muscle_segments,
                                displacement=DEFAULT_DISPLACEMENT,
                                bone_radii=None,
                                max_displacement_ratio=MAX_DISPLACEMENT_RATIO):
    """Radial delta out of each `head->tail` segment, scaled by weight.

    The displacement of a muscle is split over its segments and capped at
    `max_displacement_ratio` of the blended bone envelope radius, so stacked
    segments cannot spike the surface; a vertex weighted on several segments
    gets one cross-faded direction instead of a per-segment step. The weights
    are renormalized to the heaviest segment seen by the vertex, so the peak of
    a bucket reaches the cap instead of a fraction of it. Return
    {bone: {vertex: (dx, dy, dz)}}.
    """
    if displacement is None or displacement <= 0.0:
        raise BakeError("The displacement must be greater than 0.")
    if max_displacement_ratio is None or max_displacement_ratio <= 0.0:
        raise BakeError("The max displacement ratio must be greater than 0.")
    if not muscle_segments:
        raise BakeError("At least one muscle segment is required.")
    groups = _muscle_groups(muscle_segments)
    radii = dict(bone_radii or {})
    geometry = _segment_geometry(muscle_segments, radii)
    deltas = {}
    for bones in groups.values():
        share = displacement / len(bones)
        for vertex, vertex_weights in weights.items():
            bone_weights = {
                bone_name: vertex_weights.get(bone_name, 0.0)
                for bone_name in bones
                if abs(vertex_weights.get(bone_name, 0.0)) > EPS
            }
            if not bone_weights:
                continue
            peak = max(bone_weights.values())
            coordinates = vertex_coordinates.get(vertex)
            if coordinates is None:
                continue
            point = (coordinates[0], coordinates[1], coordinates[2])
            sample = _blended_sample(point, bone_weights, geometry)
            if sample is None:
                continue
            direction, _total, radius, samples = sample
            amplitude = min(share, max_displacement_ratio * radius)
            for bone_name, weight, _own in samples:
                scale = (weight / peak) * amplitude
                deltas.setdefault(bone_name, {})[vertex] = tuple(
                    component * scale for component in direction)
    return deltas
