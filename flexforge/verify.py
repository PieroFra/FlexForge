# FlexForge — deformation verification for skinned meshes.
# Pure function on the weights dict plus the operator that applies it to the
# active mesh; no export, no weight modification. Engine budget
# (Unity/Godot/Unreal): maximum 4 influences per vertex.
# APIs used are present on both Blender 4.2 and 5.3.

import bpy

from .armatura import armature_of_mesh
from .muscle import MUSCLE_PREFIX
from .weights import (
    EPS,
    MAX_INFLUENCES_DEFAULT,
    MAX_INFLUENCES_MIN,
    WeightsError,
    budget_report,
    read_weights,
)

# Weight tolerance: single source in weights.py, no local copy.


def _validate_weight_domain(weights):
    """Raise `WeightsError` for a negative sum or a negative single weight.

    Explicit domain check: a negative weight is not a residual to discard with
    `abs()`, it is invalid data as in `weights.py`.
    """
    for vertex, groups in weights.items():
        total = sum(groups.values())
        if total < 0.0:
            raise WeightsError(
                "Negative weight sum on vertex %s: %r." % (vertex, total)
            )
        for name, weight in groups.items():
            if weight < 0.0:
                raise WeightsError(
                    "Negative weight on vertex %s for group %r: %r."
                    % (vertex, name, weight)
                )


def validate_deformation(weights, helper_bones, max_influences=MAX_INFLUENCES_DEFAULT):
    """Validate the deformation of a skinned mesh with helper bones.

    `weights` is {vertex_index: {group_name: weight}}, `helper_bones` is an
    iterable of helper bone names that must turn out to be weighted. The report
    reuses `budget_report` from weights.py; a helper bone counts as present if
    at least one vertex weights it above `EPS` (imported from weights.py).
    `valid` is true only if no vertex exceeds the budget and all helpers are
    present; an empty helper list is not a valid verification, so `valid` is
    false with the explicit reason in `reason`.
    Raise `WeightsError` if `max_influences` is < 1 or if a weight or a vertex
    weight sum is negative.
    """
    if max_influences < MAX_INFLUENCES_MIN:
        raise WeightsError(
            "The maximum number of influences must be at least %d."
            % MAX_INFLUENCES_MIN
        )

    _validate_weight_domain(weights)

    report = budget_report(weights, max_influences)
    helpers = {str(name) for name in helper_bones}

    helpers_present = 0
    for name in helpers:
        for groups in weights.values():
            if abs(groups.get(name, 0.0)) > EPS:
                helpers_present += 1
                break

    reason = ""
    if not helpers:
        reason = "No helper bones to verify."
    elif report["over_budget"] != 0:
        reason = "%d vertices over the budget of %d influences." % (
            report["over_budget"],
            max_influences,
        )
    elif helpers_present != len(helpers):
        reason = "%d helper bones out of %d are unweighted." % (
            len(helpers) - helpers_present,
            len(helpers),
        )

    return {
        "vertices": report["vertices"],
        "over_budget": report["over_budget"],
        "max_influences": report["max_influences"],
        "helpers_present": helpers_present,
        "valid": not reason,
        "reason": reason,
    }


# Legacy alias: delegates to the shared helper in armatura.py.
def _armature_of_mesh(obj):
    return armature_of_mesh(obj)


def _verify_message(report):
    """Deformation verification summary line, in English."""
    return (
        "FlexForge - verify: vertices=%d over_budget=%d max_influences=%d "
        "helpers_present=%d valid=%s"
        % (
            report["vertices"],
            report["over_budget"],
            report["max_influences"],
            report["helpers_present"],
            "yes" if report["valid"] else "no",
        )
    )


class FLEXFORGE_OT_verify(bpy.types.Operator):
    """Verify the weights budget of the active mesh against the helper bones."""

    bl_idname = "flexforge.verify"
    bl_label = "Verify deformation"
    bl_description = (
        "Check the influence budget and the presence of muscle helpers on the "
        "active mesh and print the report to the console (no export)"
    )
    bl_options = {"REGISTER"}

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

        armature = _armature_of_mesh(obj)
        if armature is None:
            self.report(
                {"ERROR"},
                "An armature is required: add an Armature modifier to the mesh.",
            )
            return {"CANCELLED"}

        helper_bones = [
            bone.name
            for bone in armature.data.bones
            if bone.use_deform and bone.name.startswith(MUSCLE_PREFIX)
        ]
        if not helper_bones:
            self.report(
                {"ERROR"},
                "No deforming '%s*' helper bones on the armature."
                % MUSCLE_PREFIX,
            )
            return {"CANCELLED"}

        max_influences = getattr(self, "max_influences", None)
        if not isinstance(max_influences, int) or max_influences < MAX_INFLUENCES_MIN:
            max_influences = MAX_INFLUENCES_DEFAULT

        try:
            report = validate_deformation(
                read_weights(obj), helper_bones, max_influences
            )
        except WeightsError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        message = _verify_message(report)
        print(message)
        self.report({"INFO"}, message)
        return {"FINISHED"}
