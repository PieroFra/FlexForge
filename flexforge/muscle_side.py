# FlexForge - optional per-capsule side filter of the muscle helpers.
# A muscle cannot bulge through the opposite side of the body: on a capsule with
# the side filter on, the vertices behind the bone head plane are dropped, so a
# pectoral never pushes the back. Pure functions, no bpy, 4.2 and 5.3 free.

# Origin bones of the torso: the capsules of their muscles keep the side filter
# on by default; the limb helpers keep the whole capsule unchanged.
TORSO_TOKENS = ("spine", "chest", "torso", "ribcage", "thorax")
SIDE_EPS = 1e-9

def is_torso_bone(name, tokens=TORSO_TOKENS):
    """True when the bone name carries one of the torso tokens."""
    lowered = str(name).lower()
    return any(str(token).lower() in lowered for token in tokens)

def unit_vector(vector):
    """Unit copy of `vector`, or None when it is (almost) zero."""
    length = sum(value * value for value in vector) ** 0.5
    if length <= SIDE_EPS:
        return None
    return tuple(value / length for value in vector)

def side_direction(head, tail):
    """Bulge direction of a capsule: the unit `head -> tail` bone axis."""
    return unit_vector([tail[i] - head[i] for i in range(3)])

def passes_side(point, head, direction):
    """False when `point` lies behind the head plane of the bulge direction."""
    if direction is None:
        return True
    offset = [point[i] - head[i] for i in range(3)]
    dot = sum(offset[i] * direction[i] for i in range(3))
    return dot >= 0.0
