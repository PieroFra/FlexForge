# FlexForge — weight transfer from a reference mesh to the active mesh.
# Each target vertex takes the weights of the nearest reference vertex within
# a distance threshold; vertex groups are mapped by name with optional L/R
# inversion. Normalization and the 4-influence limit per vertex reuse
# weights.py. Above GRID_MIN_VERTICES the search goes through spatial_grid.py.
# APIs present on both Blender 4.2 and 5.3.

import bpy

from .spatial_grid import (
    GRID_MIN_VERTICES,
    build_spatial_grid,
    grid_for,
    nearest_vertex_grid,
    squared_distance,
)
from .weight_nomi import LATERAL_SUFFIXES, invert_group_name, map_groups
from .weights import (
    MAX_INFLUENCES_DEFAULT, MAX_INFLUENCES_MIN, WeightsError,
    limit_influences, read_weights, write_weights,
)

MAX_DISTANCE_DEFAULT = 0.05
MAX_DISTANCE_MIN = 0.0

# Re-exported for compatibility with tests and existing modules.
__all__ = [
    "GRID_MIN_VERTICES", "LATERAL_SUFFIXES", "MAX_DISTANCE_DEFAULT",
    "MAX_DISTANCE_MIN", "TransferError", "FLEXFORGE_OT_weight_transfer",
    "apply_transfer", "build_spatial_grid", "compute_transfer",
    "invert_group_name", "map_groups", "nearest_vertex",
    "nearest_vertex_grid", "transfer_message",
]


class TransferError(Exception):
    """Weight transfer domain error, English message."""


def nearest_vertex(point, coordinates, max_distance=MAX_DISTANCE_DEFAULT):
    """Index of the nearest vertex within `max_distance`, otherwise None.

    On equal distance the lower index wins, so the outcome is stable. Raise
    `TransferError` if the threshold is negative.
    """
    if max_distance < MAX_DISTANCE_MIN:
        raise TransferError("The maximum distance cannot be negative.")
    limit = max_distance * max_distance
    found = []
    for index, vertex_coordinates in enumerate(coordinates):
        if vertex_coordinates is None:
            continue
        distance = squared_distance(point, vertex_coordinates)
        if distance <= limit:
            found.append((distance, index))
    return min(found)[1] if found else None


def compute_transfer(
    reference_weights,
    reference_coordinates,
    target_coordinates,
    mapping,
    max_distance=MAX_DISTANCE_DEFAULT,
    max_influences=MAX_INFLUENCES_DEFAULT,
):
    """Compute the target weights from the nearest reference vertex.

    `reference_weights` is {vertex_index: {group_name: weight}},
    `coordinates_*` are lists indexed like the vertex indices. The transferred
    weights go through `mapping` (unmapped groups are discarded), then through
    `limit_influences` from weights.py (normalization to 1 and `max_influences`
    cap per vertex). Vertices without a reference within threshold stay
    without weights; above GRID_MIN_VERTICES the lookup uses the spatial grid.
    Raise `WeightsError` if `max_influences` is < 1.
    """
    if max_influences < MAX_INFLUENCES_MIN:
        raise WeightsError(
            "The maximum number of influences must be at least %d."
            % MAX_INFLUENCES_MIN
        )

    grid, cell_size = grid_for(reference_coordinates, max_distance)
    weights = {}
    out_of_range = 0
    for index in range(len(target_coordinates)):
        point = target_coordinates[index]
        if grid is None:
            neighbour = nearest_vertex(point, reference_coordinates, max_distance)
        else:
            neighbour = nearest_vertex_grid(point, reference_coordinates, grid,
                                           cell_size, max_distance)
        if neighbour is None:
            out_of_range += 1
            weights[index] = {}
            continue
        groups = {}
        for name, weight in reference_weights.get(neighbour, {}).items():
            target = mapping.get(name)
            if target is not None:
                groups[target] = groups.get(target, 0.0) + weight
        weights[index] = groups

    present = set()
    for groups in reference_weights.values():
        present.update(groups)
    ignored = sorted(name for name in present if name not in mapping)

    return {
        "vertices": len(target_coordinates),
        "vertices_transferred": len(target_coordinates) - out_of_range,
        "vertices_out_of_range": out_of_range,
        "ignored_groups": ignored,
        "weights": limit_influences(weights, max_influences),
    }


def apply_transfer(
    reference_obj,
    target_obj,
    invert_lr=False,
    max_distance=MAX_DISTANCE_DEFAULT,
    max_influences=MAX_INFLUENCES_DEFAULT,
):
    """Transfer and write the weights on the target mesh; return the report.

    Reads the reference with `read_weights` and writes with `write_weights`, so
    unmapped groups are not created nor touched on the target.
    """
    reference_weights = read_weights(reference_obj)
    reference_coordinates = [tuple(v.co) for v in reference_obj.data.vertices]
    target_coordinates = [tuple(v.co) for v in target_obj.data.vertices]
    mapping = map_groups(
        [g.name for g in reference_obj.vertex_groups],
        [g.name for g in target_obj.vertex_groups],
        invert_lr,
    )
    result = compute_transfer(
        reference_weights, reference_coordinates, target_coordinates,
        mapping, max_distance, max_influences,
    )
    write_weights(target_obj, result.pop("weights"))
    return result


def transfer_message(report):
    """Weight transfer summary line, in English."""
    return (
        "FlexForge - transfer: vertices=%d transferred=%d out_of_range=%d "
        "ignored_groups=%d"
        % (report["vertices"], report["vertices_transferred"],
           report["vertices_out_of_range"], len(report["ignored_groups"]))
    )


class FLEXFORGE_OT_weight_transfer(bpy.types.Operator):
    """Transfer the weights from the reference mesh to the active mesh."""

    bl_idname = "flexforge.weight_transfer"
    bl_label = "Transfer weights"
    bl_description = (
        "Copy the weights from the nearest vertex of the selected reference "
        "mesh, within the threshold, with optional L/R mapping"
    )
    bl_options = {"REGISTER", "UNDO"}

    max_distance: bpy.props.FloatProperty(
        name="Max distance", default=MAX_DISTANCE_DEFAULT,
        min=MAX_DISTANCE_MIN,
    )
    invert_lr: bpy.props.BoolProperty(name="Invert L/R", default=False)
    max_influences: bpy.props.IntProperty(
        name="Max influences", default=MAX_INFLUENCES_DEFAULT,
        min=MAX_INFLUENCES_MIN, max=8,
    )

    def execute(self, context):
        target = context.view_layer.objects.active
        if target is None or target.type != "MESH":
            self.report({"ERROR"}, "An active mesh is required: select the "
                        "object and try again.")
            return {"CANCELLED"}

        reference = None
        for obj in getattr(context, "selected_objects", ()):
            if obj is not target and obj.type == "MESH":
                reference = obj
                break
        if reference is None:
            self.report({"ERROR"}, "Also select the reference mesh in "
                        "addition to the active one.")
            return {"CANCELLED"}

        max_distance = getattr(self, "max_distance", None)
        if not isinstance(max_distance, (int, float)) or max_distance < 0.0:
            max_distance = MAX_DISTANCE_DEFAULT
        max_influences = getattr(self, "max_influences", None)
        if not isinstance(max_influences, int) or max_influences < MAX_INFLUENCES_MIN:
            max_influences = MAX_INFLUENCES_DEFAULT

        try:
            report = apply_transfer(
                reference, target, bool(getattr(self, "invert_lr", False)),
                max_distance, max_influences,
            )
        except (WeightsError, TransferError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        message = transfer_message(report)
        print(message)
        self.report({"INFO"}, message)
        return {"FINISHED"}
