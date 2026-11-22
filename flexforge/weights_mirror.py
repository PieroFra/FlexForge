# FlexForge — weight mirroring between the right and the left side.
# Pure functions on dictionaries {vertex_index: {group_name: weight}} plus the
# operator that applies them to the active mesh: the weights of the .L/.R and
# _L/_R groups are copied to the opposite side only for the vertices that have
# no weight yet on the target side. Normalization and influence cap reuse
# weights.py; the name inversion reuses weight_transfer.py.
# APIs present on both Blender 4.2 and 5.3.

import bpy

from .weight_nomi import LATERAL_SUFFIXES, invert_group_name
from .weight_transfer import (
    GRID_MIN_VERTICES, MAX_DISTANCE_DEFAULT, build_spatial_grid,
    nearest_vertex, nearest_vertex_grid,
)
from .weights import (
    MAX_INFLUENCES_DEFAULT,
    MAX_INFLUENCES_MIN,
    WeightsError,
    budget_report,
    limit_influences,
    read_weights,
    write_weights,
)


def group_side(name):
    """Return "L", "R" or None according to the name lateral suffix."""
    for left, right in LATERAL_SUFFIXES:
        if name.endswith(left):
            return "L"
        if name.endswith(right):
            return "R"
    return None


def mirror_weights(
    weights,
    right_names,
    left_names,
    max_influences=MAX_INFLUENCES_DEFAULT,
):
    """Copy lateral weights to the opposite side where the side is missing.

    `weights` is {vertex_index: {group_name: weight}}, `right_names` and
    `left_names` are the vertex group names available on the respective side.
    If a vertex has no group of the right side, its left weights are copied
    onto the matching existing right groups (and vice versa). The returned
    dict is new, it goes through `limit_influences` from weights.py
    (normalization to 1 and influence cap); the input is not modified.
    Raise `WeightsError` if the influence limit is not valid.
    """
    right = {str(name) for name in right_names}
    left = {str(name) for name in left_names}

    mirrored_weights = {
        vertex: _mirror_vertex(groups, right, left)
        for vertex, groups in weights.items()
    }
    return limit_influences(mirrored_weights, max_influences)


def _copy_side(new, source, side_names, target_names):
    """Copy the `side_names` weights of `source` into `new`, names inverted."""
    for name, weight in source.items():
        if name in side_names:
            opposite = invert_group_name(name)
            if opposite in target_names:
                new[opposite] = weight


def _mirror_vertex(groups, right, left):
    """Copy the missing side of one vertex from its own opposite-side groups."""
    new = dict(groups)
    has_right = any(name in right for name in groups)
    has_left = any(name in left for name in groups)
    if not has_right:
        _copy_side(new, groups, left, right)
    if not has_left:
        _copy_side(new, groups, right, left)
    return new


def mirror_weights_spatial(
    weights,
    coordinates,
    right_names,
    left_names,
    max_distance=MAX_DISTANCE_DEFAULT,
    max_influences=MAX_INFLUENCES_DEFAULT,
):
    """Copy the lateral weights from the vertex mirrored on the X axis.

    For every vertex the nearest vertex to (-x, y, z) is looked up with
    `nearest_vertex`: when it is a different vertex, its lateral weights are
    copied onto the missing side only, with the group name inverted. When the
    match is the vertex itself the single-vertex rule is used.
    """
    right = {str(name) for name in right_names}
    left = {str(name) for name in left_names}

    grid = None
    cell_size = float(max_distance)
    if len(coordinates) > GRID_MIN_VERTICES and max_distance > 0.0:
        grid = build_spatial_grid(coordinates, cell_size)

    mirrored_weights = {}
    for vertex, groups in weights.items():
        new = dict(groups)
        here = coordinates[vertex] if vertex < len(coordinates) else None
        opposite_vertex = None
        if here is not None:
            point = (-float(here[0]), float(here[1]), float(here[2]))
            if grid is None:
                opposite_vertex = nearest_vertex(point, coordinates, max_distance)
            else:
                opposite_vertex = nearest_vertex_grid(
                    point, coordinates, grid, cell_size, max_distance
                )
        if opposite_vertex is None or opposite_vertex == vertex:
            mirrored_weights[vertex] = _mirror_vertex(groups, right, left)
            continue

        other = weights.get(opposite_vertex, {})
        if not any(name in left for name in groups):
            _copy_side(new, other, right, left)
        if not any(name in right for name in groups):
            _copy_side(new, other, left, right)
        mirrored_weights[vertex] = new

    return limit_influences(mirrored_weights, max_influences)


def apply_mirror(
    obj,
    max_influences=MAX_INFLUENCES_DEFAULT,
    max_distance=MAX_DISTANCE_DEFAULT,
):
    """Mirror and write the active mesh weights; return the report.

    Reads with `read_weights` and writes with `write_weights`; the report adds
    the `mirrored` count. Vertices exposing `co` use the spatial X-axis mirror.
    """
    weights = read_weights(obj)
    right_names = []
    left_names = []
    for group in obj.vertex_groups:
        side = group_side(group.name)
        if side == "R":
            right_names.append(group.name)
        elif side == "L":
            left_names.append(group.name)

    vertices = list(obj.data.vertices)
    if vertices and all(hasattr(vertex, "co") for vertex in vertices):
        coordinates = [tuple(vertex.co) for vertex in vertices]
        mirrored_weights = mirror_weights_spatial(
            weights,
            coordinates,
            right_names,
            left_names,
            max_distance,
            max_influences,
        )
    else:
        mirrored_weights = mirror_weights(
            weights, right_names, left_names, max_influences
        )
    # The helpers above already normalize and cap the influences.
    limited = mirrored_weights
    mirrored = sum(
        1
        for vertex, groups in mirrored_weights.items()
        if any(name not in weights.get(vertex, {}) for name in groups)
    )

    write_weights(obj, limited)
    report = budget_report(limited, max_influences)
    report["mirrored"] = mirrored
    return report


def mirror_message(report):
    """Weight mirror summary line, in English."""
    return (
        "FlexForge - mirror: vertices=%d mirrored=%d over_budget=%d "
        "max_influences=%d"
        % (
            report["vertices"],
            report["mirrored"],
            report["over_budget"],
            report["max_influences"],
        )
    )


class FLEXFORGE_OT_mirror_weights(bpy.types.Operator):
    """Mirror the weights between the right and left side of the active mesh."""

    bl_idname = "flexforge.mirror_weights"
    bl_label = "Mirror weights"
    bl_description = (
        "Copy the weights of the .L/.R and _L/_R groups to the opposite side "
        "for vertices without an already weighted target side, then normalize"
    )
    bl_options = {"REGISTER", "UNDO"}

    max_influences: bpy.props.IntProperty(
        name="Max influences", default=MAX_INFLUENCES_DEFAULT,
        min=MAX_INFLUENCES_MIN, max=8,
    )
    max_distance: bpy.props.FloatProperty(
        name="Max distance", default=MAX_DISTANCE_DEFAULT, min=0.0,
    )

    def execute(self, context):
        obj = context.view_layer.objects.active
        if obj is None or obj.type != "MESH":
            self.report(
                {"ERROR"},
                "An active mesh is required: select the object and try again.",
            )
            return {"CANCELLED"}

        max_influences = getattr(self, "max_influences", None)
        if not isinstance(max_influences, int) or max_influences < MAX_INFLUENCES_MIN:
            max_influences = MAX_INFLUENCES_DEFAULT

        max_distance = getattr(self, "max_distance", None)
        if not isinstance(max_distance, (int, float)) or max_distance < 0.0:
            max_distance = MAX_DISTANCE_DEFAULT

        try:
            report = apply_mirror(obj, max_influences, max_distance)
        except WeightsError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        message = mirror_message(report)
        print(message)
        self.report({"INFO"}, message)
        return {"FINISHED"}
