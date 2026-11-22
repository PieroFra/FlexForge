# FlexForge — vertex group weight cleanup.
# Pure functions on dictionaries {vertex_index: {group_name: weight}} plus the
# operator that applies them to the active mesh: it removes negligible weights,
# finds the groups left orphaned and applies the influence cap reusing the
# weights.py utilities. APIs present on both Blender 4.2 and 5.3.

import bpy

from .weights import (
    EPS,
    MAX_INFLUENCES_DEFAULT,
    MAX_INFLUENCES_MIN,
    WeightsError,
    limit_influences,
    read_weights,
    write_weights,
)


def clean_weights(weights, eps=EPS, max_influences=MAX_INFLUENCES_DEFAULT):
    """Remove weights below `eps`, report orphan groups and limit influences.

    Return {weights, zero_removed, orphan_groups, over_budget_removed,
    vertices}: `weights` is new and normalized to 1 by the weights.py
    influence limit, `zero_removed` counts the single entries below tolerance,
    `orphan_groups` the groups left without any residual weight,
    `over_budget_removed` the entries discarded by the influence cap. The input
    is not modified. Raise `WeightsError` if `eps` is negative or
    `max_influences` is < 1.
    """
    if max_influences < MAX_INFLUENCES_MIN:
        raise WeightsError(
            "The maximum number of influences must be at least %d."
            % MAX_INFLUENCES_MIN
        )
    if eps < 0.0:
        raise WeightsError("The eps tolerance cannot be negative.")

    cleaned = {}
    zero_removed = 0
    for vertex, groups in weights.items():
        kept = {}
        for name, weight in groups.items():
            # Same threshold as weights.py: a weight equal to eps does not count.
            if abs(weight) <= eps:
                zero_removed += 1
                continue
            kept[name] = weight
        cleaned[vertex] = kept

    present = set()
    for groups in weights.values():
        present.update(groups)

    limited = limit_influences(cleaned, max_influences)
    entries_before = sum(len(groups) for groups in cleaned.values())
    entries_after = sum(len(groups) for groups in limited.values())

    residual = set()
    for groups in limited.values():
        residual.update(groups)
    orphan_groups = sorted(present - residual)

    return {
        "weights": limited,
        "zero_removed": zero_removed,
        "orphan_groups": orphan_groups,
        "over_budget_removed": entries_before - entries_after,
        "vertices": len(weights),
    }


def apply_cleanup(obj, eps=EPS, max_influences=MAX_INFLUENCES_DEFAULT):
    """Clean and write the active mesh weights; return the report.

    Reads with `read_weights` and writes with `write_weights`; orphan vertex
    groups are not deleted from the mesh, only reported.
    """
    result = clean_weights(read_weights(obj), eps, max_influences)
    write_weights(obj, result.pop("weights"))
    return result


def cleanup_message(report):
    """Weight cleanup summary line, in English."""
    return (
        "FlexForge - cleanup: vertices=%d zero_removed=%d orphan_groups=%d "
        "over_budget_removed=%d"
        % (
            report["vertices"],
            report["zero_removed"],
            len(report["orphan_groups"]),
            report["over_budget_removed"],
        )
    )


class FLEXFORGE_OT_cleanup_weights(bpy.types.Operator):
    """Remove negligible weights and limit the active mesh influences."""

    bl_idname = "flexforge.cleanup_weights"
    bl_label = "Clean weights"
    bl_description = (
        "Remove weights below tolerance, report orphan groups and limit the "
        "influences per vertex normalizing to 1"
    )
    bl_options = {"REGISTER", "UNDO"}

    max_influences: bpy.props.IntProperty(
        name="Max influences",
        default=MAX_INFLUENCES_DEFAULT,
        min=MAX_INFLUENCES_MIN,
        max=8,
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

        try:
            report = apply_cleanup(obj, EPS, max_influences)
        except WeightsError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        message = cleanup_message(report)
        print(message)
        self.report({"INFO"}, message)
        return {"FINISHED"}
