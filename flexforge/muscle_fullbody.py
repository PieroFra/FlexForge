# FlexForge - one-click end-to-end full-body muscle operator.
# Orchestration lives in `fullbody_pipeline`; this module only exposes the
# operator properties and wires execute/reporting/selection restoration.

import bpy

from .engine_budget import BudgetError
from .fullbody_pipeline import (
    NO_PRESETS,
    FullBodyError,
    _set_mode_no_undo,
    resolve_targets,
    run_full_body_pipeline,
)
from .muscle import MuscleError
from .muscle_bake import DEFAULT_DISPLACEMENT, BakeError
from .muscle_presets import _select_only
from .muscle_skinning import DEFAULT_RADIUS, SkinningError
from .rig_detect import RigDetectError, full_body_message  # noqa: F401
from .weights import MAX_INFLUENCES_DEFAULT, MAX_INFLUENCES_MIN, WeightsError


class FLEXFORGE_OT_apply_full_body(bpy.types.Operator):
    """Create, skin, bake, verify and budget every muscle preset on the active rig."""

    bl_idname = "flexforge.apply_full_body"
    bl_label = "Create full body"
    bl_description = (
        "Create, bind, bake shape keys, verify and apply engine budget for "
        "every preset detected on the active rig"
    )
    bl_options = {"REGISTER", "UNDO"}

    mirror_lr: bpy.props.BoolProperty(name="Mirror L/R", default=True)
    bind_radius: bpy.props.FloatProperty(
        name="Bind radius", default=DEFAULT_RADIUS, min=0.01, max=1.0
    )
    displacement: bpy.props.FloatProperty(
        name="Displacement", default=DEFAULT_DISPLACEMENT, min=0.001, max=1.0
    )
    anatomical_taper: bpy.props.BoolProperty(name="Anatomical taper", default=True)
    directional_bias: bpy.props.BoolProperty(name="Directional bias", default=True)
    smooth_iterations: bpy.props.IntProperty(name="Smooth", default=2, min=0, max=5)
    drive_by_pose: bpy.props.BoolProperty(name="Drive by pose", default=True)
    max_influences: bpy.props.IntProperty(
        name="Max influences",
        default=MAX_INFLUENCES_DEFAULT,
        min=MAX_INFLUENCES_MIN,
        max=8,
    )
    lod: bpy.props.IntProperty(name="LOD", default=1, min=0, max=3)

    def execute(self, context):
        previous_active = context.view_layer.objects.active
        previous_selected = [obj for obj in context.selected_objects]
        try:
            armature, meshes = resolve_targets(context, active=previous_active)
        except FullBodyError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        initial_mode = getattr(armature, "mode", "OBJECT")
        previous_active_mode = getattr(previous_active, "mode", "OBJECT")
        try:
            if (
                previous_active is not None
                and previous_active != armature
                and previous_active_mode != "OBJECT"
            ):
                _select_only(previous_active, [previous_active])
                _set_mode_no_undo(previous_active, "OBJECT")
            result = run_full_body_pipeline(
                armature,
                meshes,
                mirror_lr=self.mirror_lr,
                bind_radius=self.bind_radius,
                displacement=self.displacement,
                anatomical_taper=self.anatomical_taper,
                directional_bias=self.directional_bias,
                smooth_iterations=self.smooth_iterations,
                drive_by_pose=self.drive_by_pose,
                max_influences=self.max_influences,
                lod=self.lod,
            )
        except (
            FullBodyError,
            MuscleError,
            RigDetectError,
            SkinningError,
            BakeError,
            WeightsError,
            BudgetError,
        ) as error:
            print(str(error))
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        finally:
            if initial_mode in ("EDIT", "POSE"):
                _select_only(armature, [armature])
                _set_mode_no_undo(armature, initial_mode)
            elif getattr(armature, "mode", "OBJECT") != "OBJECT":
                _select_only(armature, [armature])
                _set_mode_no_undo(armature, "OBJECT")
            _select_only(previous_active, previous_selected)
            if (
                previous_active is not None
                and previous_active != armature
                and previous_active_mode != "OBJECT"
            ):
                _set_mode_no_undo(previous_active, previous_active_mode)

        message = result["message"]
        print(message)
        level = {"WARNING"} if result.get("warnings") else {"INFO"}
        self.report(level, message)
        return {"FINISHED"}