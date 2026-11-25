# FlexForge — pure capsule math for the muscle helper auto-skinning.
# Every function works on {vertex_index: {group_name: weight}} and stays free
# of bpy, so the skinning operator can be tested headless.

from .muscle import MUSCLE_PREFIX
from .muscle_side import passes_side, side_direction, unit_vector
from .weights import (
    EPS,
    MAX_INFLUENCES_DEFAULT,
    limit_influences,
)

DEFAULT_RADIUS = 0.15
DEFAULT_INTENSITY = 0.5
# Coverage floor: the capsule must reach the skin it binds, so its radius is at
# least this factor times the distance from the helper axis to the nearest
# masked skin vertex. The mesh surface is a shell at the skin distance, so the
# factor has to put that shell at a real falloff: 1.1 leaves the nearest skin
# vertex at 0.008 (a graze that binds nothing useful), 1.9 puts it at ~0.22,
# the order the helpers whose span cap already reached the skin showed (calf:
# a 0.050 cap on a 0.022 skin, ~2.2x). Measured on the 168k asset: 13 -> 34
# helpers bound, with zero opposite-side weight.
SKIN_REACH_FACTOR = 1.9
# Envelope radius used when a rest bone does not report one.
DEFAULT_BONE_RADIUS = 0.1
# Bones that never take a leg muscle capsule: the quadriceps helper stops at the
# knee, and a capsule reaching the shin squeezes the foot flat. "leg" is the
# tibia token of rigs that name it `LeftLeg`/`RightLeg`, with no shin in the name.
FOOT_EXCLUDE_TOKENS = ("foot", "toe", "ankle", "shin", "calf", "tibia", "leg")

class SkinningError(Exception):
    """Skinning module domain error, with an English message."""

def _distance(point, other):
    """Euclidean distance between two 3D points."""
    return sum((point[i] - other[i]) ** 2 for i in range(3)) ** 0.5

def segment_distance(point, head, tail):
    """Distance between `point` and the (head, tail) segment in local space.

    A degenerate segment (head == tail) degrades to the distance to `head`."""
    direction = [tail[i] - head[i] for i in range(3)]
    length_squared = sum(value * value for value in direction)
    offset = [point[i] - head[i] for i in range(3)]
    if length_squared <= 0.0:
        return _distance(point, head)
    factor = sum(offset[i] * direction[i] for i in range(3)) / length_squared
    factor = min(1.0, max(0.0, factor))
    closest = [head[i] + direction[i] * factor for i in range(3)]
    return _distance(point, closest)

def capsule_weight(point, head, tail, radius=DEFAULT_RADIUS):
    """Quadratic falloff `(1 - d / radius) ** 2` for `d < radius`, else 0.

    Raise `SkinningError` if `radius` is not strictly positive."""
    if radius <= 0.0:
        raise SkinningError("The capsule radius must be greater than zero.")
    distance = segment_distance(point, head, tail)
    if distance >= radius:
        return 0.0
    falloff = 1.0 - distance / radius
    return falloff * falloff

def _segment_of(value):
    """Accept a (head, tail) pair or a dict with local/global bone points."""
    if not isinstance(value, dict):
        return tuple(value)
    return (value.get("head_local", value.get("head")),
            value.get("tail_local", value.get("tail")))

def _capsule_side(value, head, tail):
    """Optional side direction of a capsule; `side_filter` follows the bone."""
    if not isinstance(value, dict):
        return None
    if value.get("side_filter"):
        return side_direction(head, tail)
    side = value.get("side")
    return unit_vector(tuple(side)) if side else None

def bone_radius(bone, fallback=DEFAULT_BONE_RADIUS):
    """Envelope radius of a rest bone: the larger of head/tail, or `fallback`."""
    values = [getattr(bone, key, None) for key in ("head_radius", "tail_radius")]
    usable = [v for v in values if isinstance(v, (int, float)) and v > 0.0]
    return max(usable) if usable else fallback

def _mask_vertices(existing_weights, owners):
    """Vertices already weighted on one of the origin/insertion bones."""
    return {index for index, groups in existing_weights.items()
            if any(name in owners and abs(weight) > EPS
                   for name, weight in groups.items())}

def _chain_length(head, tail):
    """Endpoint span of one helper capsule, never a max over the whole chain."""
    return _distance(head, tail)

def _capsule_radius(radius, head, tail, chain_length, mesh_diagonal=0.0,
                    unit_scale=1.0, skin_distance=None):
    """Cap a reported envelope radius on the helper span it belongs to.

    A rig that reports a body-sized envelope (0.1) on a 0.0063 helper wraps the
    whole forearm (0.1 is 85% of the 0.1179 mesh diagonal) and the helper takes
    the insertion weight: half the capsule length, and a quarter of that span on
    a chain, keep the falloff on the muscle itself. The cap follows the helper
    span at any mesh scale, so a rig measured in another unit space gets the
    same effective radius instead of the reported envelope. The quarter-span
    cap also has a floor tied to the mesh scale: a body-sized mesh needs a
    capsule at least a quarter of its diagonal to reach the skin at all, so a
    0.0016 cap on a 0.1179 mesh diagonal (below the 0.0019 bone-to-skin
    distance) binds no vertex and is raised to the mesh floor instead. The
    floor is a lower bound, never a second cap: minting it into the span cap
    kept the radius at 0.0016-0.0032 on the inner quadriceps helpers and only
    the biceps reached the skin. The floor only applies to tiny-scale meshes (a
    mesh at a metre scale, checked after `unit_scale`): on a human-scale mesh a
    quarter of the diagonal would blow the capsule past the neighbouring limb,
    so there the span cap alone stands.
    `skin_distance` (mesh-local) is the distance from the helper axis to the
    nearest vertex the capsule may weight (its bone mask, on the right side):
    the capsule must reach the skin, so the radius is raised to
    `SKIN_REACH_FACTOR * skin_distance`, never above the effective `radius`
    (the reported muscle envelope, itself capped by the `DEFAULT_RADIUS`
    ceiling: a muscle thinner than its own skin distance keeps its envelope and
    binds nothing, and no capsule can cross to a neighbouring body part). This
    is a floor over the span/mesh cap, and it only widens: a vertex on another
    body part is far beyond `SKIN_REACH_FACTOR * skin_distance`, so it never
    takes the muscle weight. `None` (or a non-positive `skin_distance`) keeps
    the span/mesh cap alone.
    `radius`, `length`, `chain_length`, `mesh_diagonal` and `skin_distance` are
    all expressed in the mesh-local unit; `unit_scale` is the
    metre-to-mesh-local factor, used only to compare the `DEFAULT_RADIUS`
    ceiling and the mesh scale against their metre-based references, so the cap
    is unchanged when the mesh is in metres (`unit_scale == 1.0`).
    Degenerate segments keep their radius, so the `capsule_weight` error stays
    explicit.
    """
    length = _distance(head, tail)
    if length <= EPS:
        return radius
    scale = unit_scale if unit_scale > 0.0 else 1.0
    if radius > DEFAULT_RADIUS * scale:
        return radius
    capped = min(radius, 0.5 * length)
    if chain_length > EPS:
        capped = min(capped, 0.25 * chain_length)
    if mesh_diagonal > 0.0 and mesh_diagonal / scale < 0.5:
        capped = min(radius, max(capped, 0.25 * mesh_diagonal))
    if skin_distance is None or skin_distance <= EPS:
        return capped
    reach = min(SKIN_REACH_FACTOR * skin_distance, radius)
    return max(capped, reach)

def _preserve_skeletal(weights, max_influences):
    """Keep the bone influences: the helpers only fill the spare budget slots.

    The capsule weights are added on top of the bone weights, so a vertex bound
    to three bones plus a helper would let `limit_influences` drop the weakest
    influence and lose the joint bone. The helpers beyond the spare budget are
    dropped here, strongest first, before the limit runs.
    """
    trimmed = {}
    for vertex, groups in weights.items():
        kept = {name: weight for name, weight in groups.items()
                if not str(name).startswith(MUSCLE_PREFIX)}
        owners = sum(1 for weight in kept.values() if abs(weight) > EPS)
        helpers = sorted(
            ((name, weight) for name, weight in groups.items()
             if str(name).startswith(MUSCLE_PREFIX) and abs(weight) > EPS),
            key=lambda item: (-item[1], str(item[0])),
        )
        for name, weight in helpers[:max(0, max_influences - owners)]:
            kept[name] = weight
        trimmed[vertex] = kept
    return trimmed

def is_excluded_bone(name, tokens=FOOT_EXCLUDE_TOKENS):
    """True when the bone name carries one of the exclusion tokens."""
    lowered = str(name).lower()
    return any(str(token).lower() in lowered for token in tokens)

def _excluded_vertices(existing_weights, tokens):
    """Vertices already weighted on a bone named by one of the tokens."""
    return {index for index, groups in existing_weights.items()
            if any(is_excluded_bone(name, tokens) and abs(weight) > EPS
                   for name, weight in groups.items())}

def compute_muscle_weights(existing_weights, vertex_coordinates,
                           muscle_segments, radius=DEFAULT_RADIUS,
                           intensity=DEFAULT_INTENSITY,
                           max_influences=MAX_INFLUENCES_DEFAULT,
                           bone_masks=None, exclude_tokens=None,
                           mesh_diagonal=0.0, unit_scale=1.0):
    """Bind the `muscle_*` capsules on the vertices and report the result.

    `muscle_segments` is {muscle_name: (head, tail)} or a dict with the local
    `head_local`/`tail_local`, the global fallback and the bone envelope
    `radius` (in mesh-local units), which wins over `radius` when smaller.
    `radius` and `intensity` follow the operator: `radius` is expressed in
    metres (the default 0.15 m) and is converted to the mesh-local unit by
    `unit_scale` (metres-to-mesh-local, 1.0 for a metre mesh): a centimetre GLB
    import (object scale 0.01, `unit_scale == 100.0`) would otherwise compare a
    metre-based default with coordinates 100x larger and bind nothing. The
    `DEFAULT_RADIUS` ceiling and the mesh-scale floor keep their metre-based
    reference through the same factor, so a metre rig (`unit_scale == 1.0`) is
    bit-for-bit unchanged. `bone_masks` maps a muscle
    `mesh_diagonal` is the local bounding-box diagonal of the mesh: it lifts
    the quarter-span cap on a body-sized mesh so a hair-thin helper still
    reaches the skin (0.0 keeps the cap on the helper span alone). On top of
    that cap every helper gets a coverage floor: the radius is raised to
    `SKIN_REACH_FACTOR` times the distance from its axis to the nearest vertex
    it may weight (its mask, on the right side), up to the `DEFAULT_RADIUS`
    ceiling, so a short helper whose span cap sits inside the skin still binds
    its own surface. The floor only widens a capsule, never redirects it, so a
    vertex of another body part (far beyond the reach) keeps its bone weight.
    `bone_masks` maps a muscle to its origin/insertion bones: only the
    vertices weighted on them get the capsule, so the helper cannot bleed on
    the body (an unweighted
    mesh keeps the whole surface). A capsule carrying `side_filter` (or an
    explicit `side` direction) drops the vertices behind its head plane, where
    `dot(head -> tail, point - head) < 0`, so a torso muscle never bulges the
    opposite side of the body. `exclude_tokens` drops the vertices already
    weighted on a bone whose name carries one of the tokens (foot, shin, ...)
    from every capsule, but a vertex weighted on the muscle's own
    origin/insertion bones is kept: `UpLeg`/`Leg` carry the "leg" token, so the
    subtraction emptied the inner quadriceps mask and bound nothing. The capsule weight is scaled by `intensity` and
    limited/normalized by `limit_influences`, after the bone influences are
    preserved: the helpers only fill the spare budget slots.
    Return {vertices, vertices_bound, muscles_bound, weights}.
    """
    scale = unit_scale if unit_scale > 0.0 else 1.0
    radius_local = float(radius) * scale
    segments = {}
    for name, value in dict(muscle_segments).items():
        head, tail = _segment_of(value)
        capsule = value.get("radius") if isinstance(value, dict) else None
        if not isinstance(capsule, (int, float)) or capsule <= 0.0:
            capsule = radius_local
        # A radius the user raised above the default is an explicit Bind radius:
        # it wins over the bone envelope (`min` kept it at the 0.1 default and
        # the span cap then dropped it to nothing, cancelling the Bind radius).
        # The comparison stays on the metre-valued `radius`, the maths run on
        # the mesh-local `radius_local`.
        if radius > DEFAULT_RADIUS:
            effective = radius_local
        else:
            effective = min(radius_local, float(capsule))
        segments[str(name)] = (head, tail, effective,
                               _capsule_side(value, head, tail))
    masks = {str(name): _mask_vertices(existing_weights, set(owners))
             for name, owners in dict(bone_masks or {}).items()}
    masks = {name: allowed for name, allowed in masks.items() if allowed}
    tokens = tuple(exclude_tokens or ())
    excluded = _excluded_vertices(existing_weights, tokens) if tokens else set()
    if excluded:
        universe = set(range(len(vertex_coordinates))) | set(existing_weights)
        owned = {str(name): _mask_vertices(existing_weights, set(owners))
                 for name, owners in dict(bone_masks or {}).items()}
        for name in segments:
            allowed = masks.get(name, universe)
            masks[name] = allowed - (excluded - owned.get(name, set()))
    # Coverage floor: measure, per helper, the distance from its axis to the
    # nearest vertex it may weight (the mask, on the right side), so the capsule
    # reaches the skin. The span cap alone left short helpers off the skin and
    # they bound no vertex; the floor widens them just past their own skin.
    skins = {}
    for name, (head, tail, capsule, side) in segments.items():
        allowed = masks.get(name)
        nearest = None
        for index, coordinate in enumerate(vertex_coordinates):
            if allowed is not None and index not in allowed:
                continue
            if not passes_side(coordinate, head, side):
                continue
            distance = segment_distance(coordinate, head, tail)
            if nearest is None or distance < nearest:
                nearest = distance
        skins[name] = nearest
    segments = {
        name: (head, tail, _capsule_radius(
            capsule, head, tail, _chain_length(head, tail), mesh_diagonal,
            scale, skins.get(name)), side)
        for name, (head, tail, capsule, side) in segments.items()
    }
    combined = {}
    for index, coordinate in enumerate(vertex_coordinates):
        groups = dict(existing_weights.get(index, {}))
        for name, (head, tail, capsule, side) in segments.items():
            allowed = masks.get(name)
            if allowed is not None and index not in allowed:
                continue
            if not passes_side(coordinate, head, side):
                continue
            weight = capsule_weight(coordinate, head, tail, capsule) * intensity
            if weight > EPS:
                groups[name] = groups.get(name, 0.0) + weight
        combined[index] = groups

    limited = limit_influences(
        _preserve_skeletal(combined, max_influences), max_influences
    )
    vertices_bound = 0
    muscles_bound = set()
    for groups in limited.values():
        bound = {
            name for name, weight in groups.items()
            if name.startswith(MUSCLE_PREFIX) and abs(weight) > EPS
        }
        if bound:
            vertices_bound += 1
            muscles_bound.update(bound)
    return {"vertices": len(vertex_coordinates),
            "vertices_bound": vertices_bound,
            "muscles_bound": len(muscles_bound), "weights": limited}
