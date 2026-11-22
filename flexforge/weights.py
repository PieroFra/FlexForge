# FlexForge — vertex group weight utilities.
# Pure functions on dictionaries {vertex_index: {group_name: weight}} plus the
# operator that applies them to the active mesh. Engine budget (Unity/Godot/
# Unreal): maximum 4 influences per vertex. APIs also present on Blender 4.2.

import bpy

MAX_INFLUENCES_DEFAULT = 4
MAX_INFLUENCES_MIN = 1
# Weight tolerance: residual influences (~1e-9) count as zero.
EPS = 1e-6


class WeightsError(Exception):
    """Weights module domain error, with an English message."""


def normalize(weights):
    """Bring the sum of each vertex weights back to 1.

    Vertices with a zero sum are left untouched (sum 0) and are not altered;
    the returned dict is new, the input is not modified.
    Raise `WeightsError` if the weight sum of a vertex is negative.
    """
    result = {}
    for vertex, groups in weights.items():
        total = sum(groups.values())
        if total < 0.0:
            raise WeightsError(
                "Negative weight sum on vertex %s: %r." % (vertex, total)
            )
        if total == 0.0:
            result[vertex] = dict(groups)
        else:
            result[vertex] = {
                name: weight / total for name, weight in groups.items()
            }
    return result


def limit_influences(weights, max_influences=MAX_INFLUENCES_DEFAULT):
    """Keep the `max_influences` strongest per vertex and renormalize to 1.

    On equal weight the order is stable on the group name; zero weights do not
    count as influences. Raise `WeightsError` if the limit is < 1.
    """
    if max_influences < MAX_INFLUENCES_MIN:
        raise WeightsError(
            "The maximum number of influences must be at least %d."
            % MAX_INFLUENCES_MIN
        )
    limited = {}
    for vertex, groups in weights.items():
        ordered = sorted(
            groups.items(), key=lambda item: (-item[1], str(item[0]))
        )
        limited[vertex] = {
            name: weight
            for name, weight in ordered[:max_influences]
            if abs(weight) > EPS
        }
    return normalize(limited)


def budget_report(weights, max_influences=MAX_INFLUENCES_DEFAULT):
    """Count vertices, vertices over budget and maximum influences per vertex."""
    if max_influences < MAX_INFLUENCES_MIN:
        raise WeightsError(
            "The maximum number of influences must be at least %d."
            % MAX_INFLUENCES_MIN
        )
    over_budget = 0
    max_influences_seen = 0
    for groups in weights.values():
        count = sum(1 for weight in groups.values() if abs(weight) > EPS)
        if count > max_influences_seen:
            max_influences_seen = count
        if count > max_influences:
            over_budget += 1
    return {
        "vertices": len(weights),
        "over_budget": over_budget,
        "max_influences": max_influences_seen,
    }


def read_weights(obj):
    """Read from the mesh the non-zero weights of the existing vertex groups.

    Return {vertex_index: {group_name: weight}}; groups without weight on the
    vertex are omitted, so the read only sees the groups actually "selected"
    by the mesh.
    """
    names = {group.index: group.name for group in obj.vertex_groups}
    weights = {}
    for vertex in obj.data.vertices:
        groups = {}
        for element in vertex.groups:
            if abs(element.weight) <= EPS:
                continue
            name = names.get(element.group)
            if name is not None:
                groups[name] = element.weight
        weights[vertex.index] = groups
    return weights


def write_weights(obj, weights):
    """Write the weights on the mesh, removing vertices from excluded groups."""
    groups = {group.name: group for group in obj.vertex_groups}
    for vertex in obj.data.vertices:
        new = weights.get(vertex.index, {})
        present = {element.group for element in vertex.groups}
        for name, group in groups.items():
            if name in new:
                group.add([vertex.index], new[name], "REPLACE")
            elif group.index in present:
                group.remove([vertex.index])


def apply_limit(obj, max_influences=MAX_INFLUENCES_DEFAULT):
    """Limit, normalize and write the mesh weights; return the report."""
    weights = limit_influences(read_weights(obj), max_influences)
    write_weights(obj, weights)
    return budget_report(weights, max_influences)


def message_report(report):
    """Weight budget summary line, in English and unambiguous."""
    return (
        "FlexForge - weights: vertices=%d over_budget=%d max_influences=%d"
        % (
            report["vertices"],
            report["over_budget"],
            report["max_influences"],
        )
    )


class FLEXFORGE_OT_limit_weights(bpy.types.Operator):
    """Limit the influences per vertex and normalize the active mesh weights."""

    bl_idname = "flexforge.limit_weights"
    bl_label = "Limit weights"
    bl_description = (
        "Keep the strongest influences per vertex, normalize to 1 and print "
        "the budget report to the console"
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
            report = apply_limit(obj, max_influences)
        except WeightsError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        message = message_report(report)
        print(message)
        self.report({"INFO"}, message)
        return {"FINISHED"}
