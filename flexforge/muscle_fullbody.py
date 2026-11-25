# FlexForge - one click creation of every muscle preset of the active rig.
# The pure detection and the creation live in `rig_detect`; this module only
# wires them to the operator button and keeps the rig selection and mode sane.
# No PropertyGroup: the Mirror L/R flag belongs to the operator itself.

import bpy

from .armatura import armature_of_mesh
from .muscle_presets import MuscleError, _select_only, _set_mode
from .rig_detect import (
    RigDetectError,
    apply_full_body,
    detect_message,
    detect_rig,
)

NO_PRESETS = "FlexForge - rig: no presets available on this rig"


class FLEXFORGE_OT_apply_full_body(bpy.types.Operator):
    """Create the helper bones of every preset detected on the active rig."""

    bl_idname = "flexforge.apply_full_body"
    bl_label = "Create full body"
    bl_description = "Create the helper bones of every preset detected on the active rig"
    bl_options = {"REGISTER", "UNDO"}

    mirror_lr: bpy.props.BoolProperty(name="Mirror L/R", default=True)

    def execute(self, context):
        previous_active = context.view_layer.objects.active
        previous_selected = [obj for obj in context.selected_objects]
        rig = previous_active
        if rig is not None and getattr(rig, "type", None) == "MESH":
            rig = armature_of_mesh(rig)
        if rig is None or getattr(rig, "type", None) != "ARMATURE":
            self.report({"ERROR"}, "Select the rig: an active armature is required.")
            return {"CANCELLED"}

        bones = list(getattr(getattr(rig, "data", None), "bones", ()) or ())
        bone_names = [bone.name for bone in bones]
        parents = {
            bone.name: (bone.parent.name if bone.parent else "")
            for bone in bones
        }
        report = detect_rig(bone_names, parents)
        if not report["preset_ids"]:
            print(NO_PRESETS)
            self.report({"ERROR"}, NO_PRESETS)
            return {"CANCELLED"}

        # `apply_full_body` works on `edit_bones`: the rig is switched around
        # the call and the previous active object and selection are restored.
        initial_mode = rig.mode
        _select_only(rig, [rig])
        error = _set_mode(rig, "EDIT")
        if error is not None:
            _select_only(previous_active, previous_selected)
            self.report({"ERROR"}, "Cannot switch to Edit Mode: %s" % error)
            return {"CANCELLED"}
        try:
            result = apply_full_body(
                rig, report, armature=rig, mirror_lr=self.mirror_lr
            )
        except (MuscleError, RigDetectError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        finally:
            exit_error = _set_mode(rig, "OBJECT")
            _select_only(previous_active, previous_selected)
        if exit_error is not None:
            self.report({"ERROR"}, "Cannot return to Object Mode: %s" % exit_error)
            return {"CANCELLED"}
        if initial_mode == "EDIT" and _set_mode(rig, "EDIT") is not None:
            self.report({"ERROR"}, "Cannot return to Edit Mode")
            return {"CANCELLED"}

        print(result["message"])
        self.report({"INFO"}, result["message"])
        return {"FINISHED"}