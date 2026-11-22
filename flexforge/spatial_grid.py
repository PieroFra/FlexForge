# FlexForge — 3D spatial grid for nearest-vertex searches.
# Pure functions without bpy logic: weight_transfer and weights_mirror use them
# above GRID_MIN_VERTICES, so a lookup visits the 27 cells around the point
# instead of every vertex. APIs present on both Blender 4.2 and 5.3.

from itertools import product

# Above this vertex count the nearest vertex search uses the spatial grid.
GRID_MIN_VERTICES = 64


def squared_distance(point, other):
    """Squared distance between two 3-component points."""
    return sum(
        (float(point[i]) - float(other[i])) ** 2 for i in range(3)
    )


def build_spatial_grid(coordinates, cell_size):
    """Map each occupied cell to its vertex indices: {cell: [index, ...]}.

    The cell is the integer part of each coordinate divided by `cell_size`;
    vertices whose coordinates are None stay out of the grid.
    """
    if cell_size <= 0.0:
        raise ValueError("cell_size must be positive.")
    grid = {}
    for index, vertex_coordinates in enumerate(coordinates):
        if vertex_coordinates is None:
            continue
        cell = tuple(int(float(vertex_coordinates[i]) // cell_size)
                     for i in range(3))
        grid.setdefault(cell, []).append(index)
    return grid


def grid_for(coordinates, max_distance):
    """Grid and cell size for the bulk path, (None, 0.0) on small meshes."""
    if len(coordinates) <= GRID_MIN_VERTICES or max_distance <= 0.0:
        return None, 0.0
    cell_size = float(max_distance)
    return build_spatial_grid(coordinates, cell_size), cell_size


def nearest_vertex_grid(point, coordinates, grid, cell_size, max_distance):
    """Nearest vertex within `max_distance` inside the 27 cells around `point`.

    `cell_size` must be at least `max_distance`, otherwise a nearer vertex in
    an unvisited cell would be missed. On equal distance the lower index wins,
    exactly like `nearest_vertex` in weight_transfer.py. Return None when no
    vertex of the visited cells is within the threshold.
    """
    if max_distance < 0.0:
        raise ValueError("The maximum distance cannot be negative.")
    cell = [int(float(point[i]) // cell_size) for i in range(3)]
    limit = max_distance * max_distance
    found = []
    for step in product((-1, 0, 1), repeat=3):
        key = tuple(cell[i] + step[i] for i in range(3))
        for index in grid.get(key, ()):
            distance = squared_distance(point, coordinates[index])
            if distance <= limit:
                found.append((distance, index))
    return min(found)[1] if found else None
