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
    return tuple(value_a - value_b for value_a, value_b in zip(point_a, point_b))

def _dot(point_a, point_b):
    return sum(value_a * value_b for value_a, value_b in zip(point_a, point_b))

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

DEFAULT_POSE_RADIUS = 1.0

def rbf_weight(distance, radius):
    """Compact Wendland weight for a pose distance: 1 at 0, 0 at `radius`.

    The weight decays smoothly as `(1 - t) ** 4 * (4 * t + 1)` with
    `t = distance / radius`, so poses at `radius` or beyond contribute
    nothing at all. Return the weight in [0, 1].
    """
    if not isinstance(distance, (int, float)) or distance < 0.0:
        raise BakeError("The distance must be greater than or equal to 0.")
    if not isinstance(radius, (int, float)) or radius <= 0.0:
        raise BakeError("The radius must be greater than 0.")
    if distance >= radius:
        return 0.0
    ratio = float(distance) / float(radius)
    return (1.0 - ratio) ** 4 * (4.0 * ratio + 1.0)

def pose_correction(pose, controls, radius=DEFAULT_POSE_RADIUS):
    """Blended corrective vector for `pose` from control poses.

    `controls` is a sequence of `(control_pose, correction)` pairs of
    equal-length numeric tuples; each control contributes
    `rbf_weight(distance(pose, control_pose), radius)` times its
    correction, normalized by the total weight. A pose far from every
    control (total weight zero) corrects nothing. Return the blended
    correction tuple.
    """
    controls = list(controls)
    if not controls:
        raise BakeError("At least one control pose is required.")
    if not isinstance(radius, (int, float)) or radius <= 0.0:
        raise BakeError("The radius must be greater than 0.")
    pose = tuple(float(value) for value in pose)
    if not pose:
        raise BakeError("The pose must not be empty.")
    blended = None
    total = 0.0
    for control_pose, correction in controls:
        control_pose = tuple(float(value) for value in control_pose)
        correction = tuple(float(value) for value in correction)
        if len(control_pose) != len(pose) or len(correction) != len(pose):
            raise BakeError("Control pose and correction sizes must match the pose size.")
        if blended is None:
            blended = [0.0] * len(pose)
        distance = _dot(_subtract(pose, control_pose),
                        _subtract(pose, control_pose)) ** 0.5
        weight = rbf_weight(distance, radius)
        if weight <= 0.0:
            continue
        total += weight
        for index, value in enumerate(correction):
            blended[index] += weight * value
    if blended is None or total <= EPS:
        return tuple(0.0 for _ in pose)
    return tuple(value / total for value in blended)

def apply_pose_correction(base_deltas, pose, control_corrections,
                          fallback_deltas=None, radius=DEFAULT_POSE_RADIUS):
    """Add the blended pose correction to `base_deltas`, shape as fallback.

    `control_corrections` is a sequence of `(control_pose, deltas)` pairs
    (or a {control_pose: deltas} mapping) where `deltas` has the
    {bone: {vertex: (dx, dy, dz)}} shape of the base deltas. When the
    pose is far from every control, or no control is given, the shape
    fallback is returned instead: `fallback_deltas` when provided, else
    a copy of `base_deltas`. Missing entries count as zero deltas and
    the inputs are never mutated. Return a new deltas dict.
    """
    source = fallback_deltas if fallback_deltas is not None else base_deltas
    if hasattr(control_corrections, "items"):
        control_corrections = list(control_corrections.items())
    else:
        control_corrections = list(control_corrections or [])
    if not control_corrections:
        return {bone: dict(vertices) for bone, vertices in dict(source).items()}
    pose = tuple(float(value) for value in pose)
    total = 0.0
    blended = {}
    for control_pose, deltas in control_corrections:
        control_pose = tuple(float(value) for value in control_pose)
        if len(control_pose) != len(pose):
            raise BakeError("Control pose size must match the pose size.")
        distance = _dot(_subtract(pose, control_pose),
                        _subtract(pose, control_pose)) ** 0.5
        weight = rbf_weight(distance, radius)
        if weight <= 0.0:
            continue
        total += weight
        for bone, vertices in dict(deltas).items():
            for vertex, delta in dict(vertices).items():
                entry = blended.setdefault(bone, {}).setdefault(
                    vertex, [0.0, 0.0, 0.0])
                for axis_index in range(3):
                    entry[axis_index] += weight * float(delta[axis_index])
    if total <= EPS:
        return {bone: dict(vertices) for bone, vertices in dict(source).items()}
    result = {bone: dict(vertices) for bone, vertices in dict(base_deltas or {}).items()}
    for bone, vertices in blended.items():
        for vertex, delta in vertices.items():
            base = result.get(bone, {}).get(vertex, (0.0, 0.0, 0.0))
            result.setdefault(bone, {})[vertex] = tuple(
                float(base[axis_index]) + delta[axis_index] / total
                for axis_index in range(3))
    return result

CACHE_FORMAT_VERSION = 1

def _cache_vertex(vertex):
    if isinstance(vertex, bool):
        raise BakeError("A cache vertex index must be an integer.")
    if isinstance(vertex, int):
        return vertex
    if isinstance(vertex, str) and vertex.strip().lstrip("-").isdigit():
        return int(vertex)
    raise BakeError("A cache vertex index must be an integer.")

def _cache_delta(delta):
    if not isinstance(delta, (tuple, list)) or len(delta) != 3:
        raise BakeError("A cache delta must be a (dx, dy, dz) triple.")
    values = tuple(float(value) for value in delta)
    if any(not math.isfinite(value) for value in values):
        raise BakeError("A cache delta must be finite.")
    return values

def _validate_deltas(deltas):
    if not isinstance(deltas, dict) or not deltas:
        raise BakeError("At least one baked delta is required.")
    cleaned = {}
    for bone, vertices in deltas.items():
        if not isinstance(vertices, dict) or not vertices:
            raise BakeError("Baked deltas for bone '%s' must not be empty." % bone)
        cleaned[str(bone)] = {_cache_vertex(vertex): _cache_delta(delta)
                               for vertex, delta in vertices.items()}
    return cleaned

def _validate_target(target):
    if not isinstance(target, dict):
        raise BakeError("A morph target must be a dict.")
    name = target.get("name")
    if not isinstance(name, str) or not name.strip():
        raise BakeError("A morph target needs a name.")
    factor = target.get("factor")
    if not isinstance(factor, (int, float)) or isinstance(factor, bool) \
            or not math.isfinite(float(factor)):
        raise BakeError("A morph target factor must be a finite number.")
    return {"name": name, "factor": float(factor),
            "deltas": _validate_deltas(target.get("deltas"))}

def bake_morph_target(deltas, morph_name="flex", factor=1.0):
    """Bake {bone: {vertex: (dx, dy, dz)}} into one named morph target.

    Pure and bpy-free: the deltas are validated, deep-copied and scaled by
    `factor`, and returned as {"name", "factor", "deltas"} with int vertex
    keys and tuple deltas, ready for `export_cache`. Inputs are not mutated.
    """
    name = str(morph_name or "").strip()
    if not name:
        raise BakeError("A morph target needs a name.")
    if not isinstance(factor, (int, float)) or isinstance(factor, bool) \
            or not math.isfinite(float(factor)):
        raise BakeError("A morph target factor must be a finite number.")
    factor = float(factor)
    cleaned = _validate_deltas(deltas)
    scaled = {bone: {vertex: tuple(component * factor for component in delta)
                     for vertex, delta in vertices.items()}
              for bone, vertices in cleaned.items()}
    return {"name": name, "factor": factor, "deltas": scaled}

def export_cache(morph_targets):
    """Serialize morph targets (from `bake_morph_target`) to a plain cache dict.

    Accepts a single target dict or an iterable of them. The result holds
    only JSON-safe values (str keys, list deltas, sorted bones/vertices) so
    it can be written to disk unchanged; `import_cache` reads it back.
    """
    if isinstance(morph_targets, dict):
        morph_targets = [morph_targets]
    targets = [_validate_target(target) for target in (morph_targets or [])]
    if not targets:
        raise BakeError("At least one morph target is required.")
    serialized = []
    for target in targets:
        serialized.append({
            "name": target["name"],
            "factor": target["factor"],
            "deltas": {bone: {str(vertex): list(vertices[vertex])
                              for vertex in sorted(vertices)}
                       for bone, vertices in sorted(target["deltas"].items())},
        })
    return {"version": CACHE_FORMAT_VERSION, "targets": serialized}

def import_cache(data):
    """Restore morph targets from a cache dict made by `export_cache`.

    Vertex keys go back to int and deltas to tuples, so the result matches
    the `bake_morph_target` shape. Malformed data raises `BakeError`.
    """
    if not isinstance(data, dict) or data.get("version") != CACHE_FORMAT_VERSION:
        raise BakeError("Unsupported morph cache version.")
    targets = data.get("targets")
    if not isinstance(targets, (list, tuple)) or not targets:
        raise BakeError("The morph cache holds no targets.")
    return [_validate_target(target) for target in targets]

def roundtrip_check(deltas, morph_name="flex", factor=1.0):
    """Bake, export, JSON-serialize and re-import `deltas`; report the drift.

    Returns {"ok", "max_error", "target_count", "vertex_count"}: `ok` is
    True when every delta survives the cache round trip within 1e-9.
    """
    import json
    target = bake_morph_target(deltas, morph_name=morph_name, factor=factor)
    cache = json.loads(json.dumps(export_cache(target)))
    restored = import_cache(cache)[0]
    max_error = 0.0
    vertex_count = 0
    for bone, vertices in target["deltas"].items():
        for vertex, delta in vertices.items():
            vertex_count += 1
            other = restored["deltas"].get(bone, {}).get(vertex)
            if other is None:
                return {"ok": False, "max_error": float("inf"),
                        "target_count": 1, "vertex_count": vertex_count}
            max_error = max(max_error,
                            max(abs(a - b) for a, b in zip(delta, other)))
    ok = restored["name"] == target["name"] \
        and restored["factor"] == target["factor"] and max_error <= 1e-9
    return {"ok": ok, "max_error": max_error, "target_count": 1,
            "vertex_count": vertex_count}
