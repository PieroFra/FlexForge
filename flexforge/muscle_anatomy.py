# FlexForge - anatomical muscle shaping helpers (pure, no bpy).
# Anterior muscles bulge forward (-Y), posterior ones bulge backward (+Y).

ANATOMY_DIRECTIONS = {
    "biceps": (0.0, -1.0, 0.0),
    "pectoral": (0.0, -1.0, 0.0),
    "quadriceps": (0.0, -1.0, 0.0),
    "triceps": (0.0, 1.0, 0.0),
    "gluteus": (0.0, 1.0, 0.0),
    "hamstring": (0.0, 1.0, 0.0),
    "calf": (0.0, 1.0, 0.0),
    "latissimus": (0.0, 1.0, 0.0),
}


def _normalize(vector):
    """Return the unit vector, or None when the length is negligible."""
    length = (vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2) ** 0.5
    if length <= 1e-9:
        return None
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def muscle_family_from_bone(bone_name):
    """Extract the muscle family from a bone name, otherwise None."""
    if not bone_name:
        return None
    parts = str(bone_name).lower().split("_")
    for index, part in enumerate(parts):
        if part in ANATOMY_DIRECTIONS:
            return part
        if part == "muscle" and index + 1 < len(parts):
            return parts[index + 1]
    return None


def directional_factor(bone_name, direction, min_back=0.15):
    """Scale a delta by how much it points along the anatomical direction."""
    family = muscle_family_from_bone(bone_name)
    if family not in ANATOMY_DIRECTIONS:
        return 1.0
    unit = _normalize(direction)
    if unit is None:
        return 1.0
    anatomy = ANATOMY_DIRECTIONS[family]
    dot = unit[0] * anatomy[0] + unit[1] * anatomy[1] + unit[2] * anatomy[2]
    dot = max(-1.0, min(1.0, dot))
    t = max(0.0, min(1.0, (dot + 1.0) * 0.5))
    return min_back + (1.0 - min_back) * (t * t)


def smooth_shape_deltas(deltas, edges, iterations=2, factor=0.5):
    """Laplacian smoothing of shape deltas over the whole mesh topology."""
    values = {}
    for vertex, delta in deltas.items():
        values[vertex] = (float(delta[0]), float(delta[1]), float(delta[2]))
    neighbors = {}
    for edge in edges:
        v0, v1 = edge[0], edge[1]
        neighbors.setdefault(v0, [])
        neighbors.setdefault(v1, [])
        if v1 not in neighbors[v0]:
            neighbors[v0].append(v1)
        if v0 not in neighbors[v1]:
            neighbors[v1].append(v0)
    for vertex in neighbors:
        values.setdefault(vertex, (0.0, 0.0, 0.0))
    for _ in range(max(0, int(iterations))):
        updated = {}
        for vertex, current in values.items():
            linked = neighbors.get(vertex)
            if not linked:
                updated[vertex] = current
                continue
            sx = sy = sz = 0.0
            for other in linked:
                delta = values.get(other, (0.0, 0.0, 0.0))
                sx += delta[0]
                sy += delta[1]
                sz += delta[2]
            count = float(len(linked))
            avg = (sx / count, sy / count, sz / count)
            updated[vertex] = (
                (1.0 - factor) * current[0] + factor * avg[0],
                (1.0 - factor) * current[1] + factor * avg[1],
                (1.0 - factor) * current[2] + factor * avg[2]
            )
        values = updated
    result = {}
    for vertex, delta in values.items():
        if (delta[0] ** 2 + delta[1] ** 2 + delta[2] ** 2) ** 0.5 > 1e-6:
            result[vertex] = delta
    return result
