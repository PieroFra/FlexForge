# FlexForge - engine budget helper (pure, no bpy objects).
# Reports and fits the budget a character must respect to be delivered to a
# game engine: influences per vertex (default 4, reused from weights.py),
# baked shape keys and exported bones, scaled per LOD level.
# The bpy operator that applies it lives in this module as well, but the
# report/fit helpers are pure and shared with the tests.

import bpy

from .weights import MAX_INFLUENCES_DEFAULT, MAX_INFLUENCES_MIN, WeightsError, budget_report, limit_influences

# Default budgets (game-ready character, LOD1).
DEFAULT_MAX_SHAPE_KEYS = 10
DEFAULT_MAX_BONES = 60

# LOD multipliers: LOD0 is the hero mesh (unlimited), LOD1 is the default
# budget, higher LODs shrink the budgets linearly (floor division, min 1).
LOD_LEVELS = (0, 1, 2, 3)


class BudgetError(WeightsError):
    """Engine budget domain error, with an English message."""


def lod_budgets(lod, max_shape_keys=DEFAULT_MAX_SHAPE_KEYS, max_bones=DEFAULT_MAX_BONES):
    """Return the (shape_keys, bones) budgets for a LOD level.

    LOD 0 means no cap (hero mesh). For LOD >= 1 the given caps are the
    absolute budgets for that LOD: the caller sets them per LOD, the level
    is validated and recorded in the report. Raise BudgetError for unknown
    levels or bad caps.
    """
    if lod not in LOD_LEVELS:
        raise BudgetError("Unknown LOD level %r: expected one of %s." % (lod, LOD_LEVELS))
    if not isinstance(max_shape_keys, int) or isinstance(max_shape_keys, bool) or max_shape_keys < 1:
        raise BudgetError("max_shape_keys must be an int >= 1.")
    if not isinstance(max_bones, int) or isinstance(max_bones, bool) or max_bones < 1:
        raise BudgetError("max_bones must be an int >= 1.")
    if lod == 0:
        return (10 ** 9, 10 ** 9)
    return (max_shape_keys, max_bones)


def engine_budget_report(weights, shape_keys, bones, max_influences=MAX_INFLUENCES_DEFAULT, max_shape_keys=DEFAULT_MAX_SHAPE_KEYS, max_bones=DEFAULT_MAX_BONES, lod=1):
    """Budget report for `weights`, baked shape keys and exported bones.

    `shape_keys` and `bones` are iterables of names (only the counts are
    reported). `lod` selects the scaled budgets from lod_budgets; the report
    keeps the original caps in max_shape_keys/max_bones for the message.
    Raise BudgetError if max_influences < 1 or the LOD is unknown.
    """
    if max_influences < MAX_INFLUENCES_MIN:
        raise BudgetError(
            "The maximum number of influences must be at least %d." % MAX_INFLUENCES_MIN
        )
    shape_keys = list(shape_keys)
    bones = list(bones)
    keys_cap, bones_cap = lod_budgets(lod, max_shape_keys, max_bones)
    base = budget_report(weights, max_influences)
    within = (
        base["over_budget"] == 0
        and len(shape_keys) <= keys_cap
        and len(bones) <= bones_cap
    )
    return {
        "vertices": base["vertices"],
        "over_budget": base["over_budget"],
        "max_influences": base["max_influences"],
        "shape_keys": len(shape_keys),
        "bones": len(bones),
        "within_budget": within,
        "lod": lod,
        "max_shape_keys": keys_cap,
        "max_bones": bones_cap,
    }


def fit_engine_budget(weights, shape_keys, bones, max_influences=MAX_INFLUENCES_DEFAULT, max_shape_keys=DEFAULT_MAX_SHAPE_KEYS, max_bones=DEFAULT_MAX_BONES, lod=1):
    """Fit weights, shape keys and bones to the LOD budget.

    Pure: never mutates the inputs. Weights are limited and renormalised via
    limit_influences; shape keys and bones are truncated in order. Returns
    {weights, shape_keys, bones, report} where report is the budget report
    of the fitted data.
    """
    if not isinstance(max_influences, int) or isinstance(max_influences, bool) or max_influences < MAX_INFLUENCES_MIN:
        raise BudgetError(
            "The maximum number of influences must be at least %d." % MAX_INFLUENCES_MIN
        )
    shape_keys = list(shape_keys)
    bones = list(bones)
    keys_cap, bones_cap = lod_budgets(lod, max_shape_keys, max_bones)
    fitted_weights = limit_influences(weights, max_influences)
    fitted_keys = shape_keys[:keys_cap]
    fitted_bones = bones[:bones_cap]
    report = engine_budget_report(
        fitted_weights, fitted_keys, fitted_bones,
        max_influences, max_shape_keys, max_bones, lod,
    )
    return {
        "weights": fitted_weights,
        "shape_keys": fitted_keys,
        "bones": fitted_bones,
        "report": report,
    }


def budget_message(report):
    """Engine budget summary line, in English and unambiguous."""
    return (
        "FlexForge - budget: vertices=%d over_budget=%d max_influences=%d "
        "shape_keys=%d/%d bones=%d/%d within_budget=%s lod=%d"
        % (
            report["vertices"],
            report["over_budget"],
            report["max_influences"],
            report["shape_keys"],
            report["max_shape_keys"],
            report["bones"],
            report["max_bones"],
            "yes" if report["within_budget"] else "no",
            report["lod"],
        )
    )


def _flexforge_keys(obj):
    """Baked FlexForge shape key names of a mesh (flexforge_* minus Basis)."""
    keys = []
    shape_keys = getattr(getattr(obj, "data", None), "shape_keys", None)
    if shape_keys is None:
        return keys
    for kb in getattr(shape_keys, "key_blocks", ()):
        name = str(getattr(kb, "name", ""))
        if name.startswith("flexforge_") and name != "flexforge_Basis":
            keys.append(name)
    return keys


def apply_engine_budget(obj, max_influences=MAX_INFLUENCES_DEFAULT, max_shape_keys=DEFAULT_MAX_SHAPE_KEYS, max_bones=DEFAULT_MAX_BONES, lod=1, armature=None):
    """Apply the LOD budget to a mesh and return the fitted report.

    Reads the live weights, the baked flexforge_* shape keys and the deform
    bones of the (optional) armature, fits them with fit_engine_budget and
    writes the limited weights back. Shape keys and bones are reported, not
    deleted: deleting keys/bones would be destructive and is left to the
    operator Clear muscles.
    """
    from .weights import read_weights, write_weights

    armature = armature if armature is not None else getattr(obj, "parent", None)
    bones = []
    if armature is not None:
        bones = [
            bone.name
            for bone in getattr(getattr(armature, "data", None), "bones", ())
            if getattr(bone, "use_deform", False)
        ]
    weights = read_weights(obj)
    keys = _flexforge_keys(obj)
    result = fit_engine_budget(
        weights, keys, bones,
        max_influences, max_shape_keys, max_bones, lod,
    )
    write_weights(obj, result["weights"])
    return result


class FLEXFORGE_OT_apply_budget(bpy.types.Operator):
    """Fit the active mesh to the engine budget (LOD) and print the report."""

    bl_idname = "flexforge.apply_budget"
    bl_label = "Apply engine budget"
    bl_description = "Fit the active mesh weights, baked keys and deform bones to the engine budget for the chosen LOD and print the report"
    bl_options = {"REGISTER", "UNDO"}

    max_influences: bpy.props.IntProperty(
        name="Max influences",
        default=MAX_INFLUENCES_DEFAULT,
        min=MAX_INFLUENCES_MIN,
        max=8,
    )
    max_shape_keys: bpy.props.IntProperty(
        name="Max shape keys",
        default=DEFAULT_MAX_SHAPE_KEYS,
        min=1,
        max=64,
    )
    max_bones: bpy.props.IntProperty(
        name="Max bones",
        default=DEFAULT_MAX_BONES,
        min=1,
        max=256,
    )
    lod: bpy.props.EnumProperty(
        name="LOD",
        description="LOD level: 0 is the hero mesh (no cap), higher LODs shrink the budget",
        items=(
            ("0", "LOD 0 (hero)", ""),
            ("1", "LOD 1", ""),
            ("2", "LOD 2", ""),
            ("3", "LOD 3", ""),
        ),
        default="1",
    )

    def execute(self, context):
        obj = context.view_layer.objects.active
        if obj is None or obj.type != "MESH":
            self.report({"ERROR"}, "An active mesh is required: select the object and try again.")
            return {"CANCELLED"}
        try:
            lod_level = int(getattr(self, "lod", "1"))
        except (TypeError, ValueError):
            lod_level = 1
        try:
            result = apply_engine_budget(
                obj,
                getattr(self, "max_influences", MAX_INFLUENCES_DEFAULT),
                getattr(self, "max_shape_keys", DEFAULT_MAX_SHAPE_KEYS),
                getattr(self, "max_bones", DEFAULT_MAX_BONES),
                lod_level,
            )
        except WeightsError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        message = budget_message(result["report"])
        print(message)
        self.report({"INFO"}, message)
        return {"FINISHED"}
