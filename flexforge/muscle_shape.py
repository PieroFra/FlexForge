# FlexForge - pure shape delta math of the muscle helpers.
# Coordinates and weight dicts in, {bone: {vertex: delta}} out: no bpy, so the
# bake module and the tests share the same numbers. Blender 4.2 and 5.3 free.

import math

from .muscle import MUSCLE_PREFIX
from .muscle_anatomy import directional_factor
from .weights import EPS

SHAPE_KEY_PREFIX = "flexforge_"
DEFAULT_DISPLACEMENT = 0.05
# Envelope radius assumed when the armature reports none, and the share of it a
# baked muscle may push the surface out: the spike guard.
DEFAULT_BONE_RADIUS = 0.1
MAX_DISPLACEMENT_RATIO = 0.3
GEOMETRY_EPS = 1e-9
# Skin thickness allowed above a muscle capsule before it counts as a gap.
DEFAULT_SKIN_LIMIT = 0.05

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

def _chain_endpoints(bones, geometry):
    """Chain head, axis and squared length of one muscle, segment by segment.

    The `muscle_biceps_01/02/...` segments are sorted: the chain runs from the
    head of the first to the tail (`head + axis`) of the last, so a taper is
    measured along the whole muscle and not along a single segment.
    """
    ordered = sorted(bones)
    chain_head = geometry[ordered[0]][0]
    last_head, last_axis = geometry[ordered[-1]][0], geometry[ordered[-1]][1]
    last_tail = tuple(last_head[i] + last_axis[i] for i in range(3))
    chain_axis = _subtract(last_tail, chain_head)
    return chain_head, chain_axis, _dot(chain_axis, chain_axis)

def _anatomical_taper(point, chain_head, chain_axis, chain_sq):
    """Fusiform envelope of a muscle: 0 at both joints, 1 in its belly."""
    if chain_sq is None or chain_sq <= GEOMETRY_EPS ** 2:
        return 1.0
    factor = _dot(_subtract(point, chain_head), chain_axis) / chain_sq
    return math.sin(math.pi * min(1.0, max(0.0, factor)))

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
                                max_displacement_ratio=MAX_DISPLACEMENT_RATIO,
                                anatomical_taper=False,
                                directional_bias=False):
    """Radial delta out of each `head->tail` segment, scaled by weight.

    The displacement of a muscle is split over its segments and capped at
    `max_displacement_ratio` of the blended bone envelope radius, so stacked
    segments cannot spike the surface; a vertex weighted on several segments
    gets one cross-faded direction instead of a per-segment step. The weights
    are renormalized to the heaviest segment seen by the vertex, so the peak of
    a bucket reaches the cap instead of a fraction of it. With
    `anatomical_taper` the amplitude is scaled by a fusiform curve along the
    whole muscle chain: zero at the tendons, one at the belly. With
    `directional_bias` the amplitude of each segment also follows the anatomical
    direction of its muscle family. Return {bone: {vertex: (dx, dy, dz)}}.
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
        chain = _chain_endpoints(bones, geometry) if anatomical_taper else None
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
            if chain is not None:
                amplitude *= _anatomical_taper(point, chain[0], chain[1],
                                               chain[2])
            for bone_name, weight, _own in samples:
                scale = (weight / peak) * amplitude
                if directional_bias:
                    scale *= directional_factor(bone_name, direction)
                deltas.setdefault(bone_name, {})[vertex] = tuple(
                    component * scale for component in direction)
    return deltas

def compute_rest_length(muscle_segments, bone_radii=None):
    """Rest length of every muscle: the sum of its segment lengths.

    The segments are grouped by muscle (`muscle_biceps_01/02` are one
    muscle) and measured with `_segment_geometry`, so the same degenerate
    segment check applies here as in the shape deltas. Return
    {shape_key_name: rest_length}.
    """
    if not muscle_segments:
        raise BakeError("At least one muscle segment is required.")
    groups = _muscle_groups(muscle_segments)
    geometry = _segment_geometry(muscle_segments, dict(bone_radii or {}))
    lengths = {}
    for key, bones in groups.items():
        total = 0.0
        for bone_name in bones:
            axis = geometry[bone_name][1]
            total += _dot(axis, axis) ** 0.5
        lengths[key] = total
    return lengths

def solve_length(rest_length, contraction):
    """Current length of a muscle at `contraction` (0 rest, 1 fully short).

    The length shortens linearly from `rest_length` to zero: a contraction of
    0.5 halves it. Return the current length.
    """
    if not isinstance(rest_length, (int, float)) or rest_length <= 0.0:
        raise BakeError("The rest length must be greater than 0.")
    if not isinstance(contraction, (int, float)) or not 0.0 <= contraction <= 1.0:
        raise BakeError("The contraction must be between 0 and 1.")
    return float(rest_length) * (1.0 - float(contraction))

def preserve_volume(rest_radius, rest_length, current_length):
    """Radius keeping the cylindrical belly volume constant at a new length.

    A muscle is modelled as a cylinder of radius `rest_radius` and length
    `rest_length`: shortening it to `current_length` must thicken it, so the
    radius scales with the square root of the length ratio. Return the radius
    at `current_length`.
    """
    if not isinstance(rest_radius, (int, float)) or rest_radius <= 0.0:
        raise BakeError("The rest radius must be greater than 0.")
    if not isinstance(rest_length, (int, float)) or rest_length <= 0.0:
        raise BakeError("The rest length must be greater than 0.")
    if not isinstance(current_length, (int, float)) or current_length <= 0.0:
        raise BakeError("The current length must be greater than 0.")
    return float(rest_radius) * (float(rest_length) / float(current_length)) ** 0.5

def capsule_chain_points(muscle_segments, bone_radii=None, steps_per_segment=8):
    """Ordered polyline points along every muscle, head to tail.

    Each segment is sampled `steps_per_segment` times from its head to its
    tail, shared endpoints visited once, so a muscle of `n` segments yields
    `n * steps_per_segment + 1` points. The bake can use the polyline to
    place capsule samples along the whole muscle. Return
    {shape_key_name: [(x, y, z), ...]}.
    """
    if not muscle_segments:
        raise BakeError("At least one muscle segment is required.")
    if not isinstance(steps_per_segment, int) or steps_per_segment < 1:
        raise BakeError("The steps per segment must be at least 1.")
    groups = _muscle_groups(muscle_segments)
    geometry = _segment_geometry(muscle_segments, dict(bone_radii or {}))
    chains = {}
    for key, bones in groups.items():
        points = []
        for index, bone_name in enumerate(sorted(bones)):
            head, axis = geometry[bone_name][0], geometry[bone_name][1]
            first = 0 if index == 0 else 1
            for step in range(first, steps_per_segment + 1):
                factor = step / float(steps_per_segment)
                points.append(tuple(head[i] + axis[i] * factor for i in range(3)))
        chains[key] = points
    return chains

def _segment_distance(point, head, tail):
    """Distance between `point` and the (head, tail) segment in local space."""
    axis = _subtract(tail, head)
    axis_square = _dot(axis, axis)
    if axis_square <= GEOMETRY_EPS ** 2:
        return _dot(_subtract(point, head), _subtract(point, head)) ** 0.5
    factor = _dot(_subtract(point, head), axis) / axis_square
    factor = min(1.0, max(0.0, factor))
    closest = tuple(head[i] + axis[i] * factor for i in range(3))
    return _dot(_subtract(point, closest), _subtract(point, closest)) ** 0.5

def _points_distance(point_a, point_b):
    """Euclidean distance between two 3D points."""
    return _dot(_subtract(point_a, point_b), _subtract(point_a, point_b)) ** 0.5

def _segments_distance(head_a, tail_a, head_b, tail_b):
    """Minimum distance between two segments, via sampled closest points."""
    samples = 16
    best = None
    for index_a in range(samples + 1):
        factor_a = index_a / float(samples)
        point_a = tuple(head_a[i] + (tail_a[i] - head_a[i]) * factor_a
                        for i in range(3))
        for index_b in range(samples + 1):
            factor_b = index_b / float(samples)
            point_b = tuple(head_b[i] + (tail_b[i] - head_b[i]) * factor_b
                            for i in range(3))
            distance = _points_distance(point_a, point_b)
            if best is None or distance < best:
                best = distance
    return best

def _radii_for(bone_radii, name):
    """Positive radius for `name` from `bone_radii`, else the default."""
    radius = dict(bone_radii or {}).get(name, DEFAULT_BONE_RADIUS)
    if not isinstance(radius, (int, float)) or radius <= 0.0:
        return DEFAULT_BONE_RADIUS
    return float(radius)

def check_collision_muscle_muscle(muscle_segments, bone_radii=None):
    """Pairs of muscles whose capsule envelopes overlap.

    Two muscles collide when the minimum distance between any of their
    segments is smaller than the sum of their envelope radii. The muscle
    names are the `flexforge_*` shape key names, so segments of the same
    muscle are never paired with each other. Return a sorted list of
    (muscle_a, muscle_b, penetration) tuples.
    """
    if not muscle_segments:
        raise BakeError("At least one muscle segment is required.")
    groups = _muscle_groups(muscle_segments)
    geometry = _segment_geometry(muscle_segments, dict(bone_radii or {}))
    muscles = sorted(groups)
    collisions = []
    for index_a, muscle_a in enumerate(muscles):
        for muscle_b in muscles[index_a + 1:]:
            radius_a = max(_radii_for(bone_radii, bone)
                           for bone in groups[muscle_a])
            radius_b = max(_radii_for(bone_radii, bone)
                           for bone in groups[muscle_b])
            distance = min(
                _segments_distance(geometry[a][0],
                                   tuple(geometry[a][0][i] + geometry[a][1][i]
                                         for i in range(3)),
                                   geometry[b][0],
                                   tuple(geometry[b][0][i] + geometry[b][1][i]
                                         for i in range(3)))
                for a in groups[muscle_a] for b in groups[muscle_b])
            penetration = radius_a + radius_b - distance
            if penetration > EPS:
                collisions.append((muscle_a, muscle_b, penetration))
    return collisions

def check_collision_muscle_bone(muscle_segments, bone_segments, bone_radii=None):
    """Pairs of muscle and bone whose capsule envelopes overlap.

    `bone_segments` maps a bone name to (head, tail); `bone_radii` maps
    either a muscle segment or a bone name to its envelope radius (the
    default applies when missing). Two capsules collide when the minimum
    distance between their segments is smaller than the sum of their radii.
    Return a sorted list of (muscle, bone, penetration) tuples.
    """
    if not muscle_segments:
        raise BakeError("At least one muscle segment is required.")
    if not bone_segments:
        raise BakeError("At least one bone segment is required.")
    groups = _muscle_groups(muscle_segments)
    geometry = _segment_geometry(muscle_segments, dict(bone_radii or {}))
    collisions = []
    for muscle in sorted(groups):
        radius_muscle = max(_radii_for(bone_radii, bone)
                            for bone in groups[muscle])
        for bone_name in sorted(bone_segments):
            head, tail = bone_segments[bone_name]
            radius_bone = _radii_for(bone_radii, bone_name)
            distance = min(
                _segments_distance(
                    geometry[bone][0],
                    tuple(geometry[bone][0][i] + geometry[bone][1][i]
                          for i in range(3)),
                    tuple(head), tuple(tail))
                for bone in groups[muscle])
            penetration = radius_muscle + radius_bone - distance
            if penetration > EPS:
                collisions.append((muscle, bone_name, penetration))
    return collisions

def skin_limit_check(muscle_segments, vertex_coordinates, bone_radii=None,
                     skin_limit=DEFAULT_SKIN_LIMIT):
    """Vertices farther than `skin_limit` from every muscle capsule.

    A vertex is reported when its distance to the nearest muscle segment
    exceeds `skin_limit`, so loose skin is listed instead of silently
    ignored. `vertex_coordinates` maps a vertex index to (x, y, z). Return
    a sorted list of offending vertex indices.
    """
    if not muscle_segments:
        raise BakeError("At least one muscle segment is required.")
    if not isinstance(skin_limit, (int, float)) or skin_limit < 0.0:
        raise BakeError("The skin limit must be greater than or equal to 0.")
    geometry = _segment_geometry(muscle_segments, dict(bone_radii or {}))
    offenders = []
    for vertex, coordinates in dict(vertex_coordinates).items():
        point = (coordinates[0], coordinates[1], coordinates[2])
        nearest = min(
            _segment_distance(point, head,
                              tuple(head[i] + axis[i] for i in range(3)))
            for head, axis, _square, _radius, _fallback in geometry.values())
        if nearest > skin_limit:
            offenders.append(vertex)
    return sorted(offenders)

def collision_report(muscle_segments, bone_segments=None, bone_radii=None,
                     vertex_coordinates=None,
                     skin_limit=DEFAULT_SKIN_LIMIT):
    """Summary of every collision check for one muscle set.

    Run muscle-muscle and muscle-bone collisions plus the skin limit check
    when `vertex_coordinates` is given. Return
    {muscle_muscle, muscle_bone, skin_limit} with the raw results of each
    check (empty lists when a check is skipped).
    """
    report = {"muscle_muscle": check_collision_muscle_muscle(
        muscle_segments, bone_radii),
        "muscle_bone": [],
        "skin_limit": []}
    if bone_segments:
        report["muscle_bone"] = check_collision_muscle_bone(
            muscle_segments, bone_segments, bone_radii)
    if vertex_coordinates is not None:
        report["skin_limit"] = skin_limit_check(
            muscle_segments, vertex_coordinates, bone_radii, skin_limit)
    return report
