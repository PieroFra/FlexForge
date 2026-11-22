# FlexForge - one click cleanup of the muscle data created by the addon:
# `flexforge_*` keys (drivers included), `muscle_*` groups and helper bones.

import bpy

from .armatura import armature_of_mesh
from .muscle_bounce import SHAPE_KEY_PREFIX
from .muscle_presets import _select_only, _set_mode

MUSCLE_PREFIX = "muscle_"
BASIS_NAME = "Basis"

class ClearError(Exception):
    """Raised when the flexforge data cannot be cleared."""

def _clear_shape_keys(obj):
    """Remove the driver and block of every `flexforge_*` key; return how many.

    A `Basis` left alone is removed too but is not counted.
    """
    data = obj.data
    if getattr(data, "shape_keys", None) is None:
        return 0
    removed = 0
    for key in list(data.shape_keys.key_blocks):
        if not key.name.startswith(SHAPE_KEY_PREFIX):
            continue
        try:
            key.driver_remove("value")
        except Exception:
            pass
        obj.shape_key_remove(key)
        removed += 1
    blocks = list(getattr(data.shape_keys, "key_blocks", []) or [])
    if len(blocks) == 1 and blocks[0].name == BASIS_NAME:
        obj.shape_key_remove(blocks[0])
    return removed

def _clear_groups(obj):
    """Remove every `muscle_*` vertex group; return how many."""
    groups = obj.vertex_groups
    wanted = [g for g in groups if g.name.startswith(MUSCLE_PREFIX)]
    for group in wanted:
        groups.remove(group)
    return len(wanted)

def _clear_bones(armature):
    """Remove every `muscle_*` edit bone, restoring selection and mode."""
    previous_active = bpy.context.view_layer.objects.active
    previous_selected = [obj for obj in bpy.context.selected_objects]
    initial_mode = armature.mode
    _select_only(armature, [armature])
    error = _set_mode(armature, "EDIT")
    if error is not None:
        _select_only(previous_active, previous_selected)
        raise ClearError("Cannot switch to Edit Mode: %s" % error)
    removed = 0
    try:
        edit_bones = armature.data.edit_bones
        for bone in [b for b in edit_bones if b.name.startswith(MUSCLE_PREFIX)]:
            edit_bones.remove(bone)
            removed += 1
    finally:
        error = _set_mode(armature, "OBJECT")
        _select_only(previous_active, previous_selected)
    if error is not None:
        raise ClearError("Cannot return to Object Mode: %s" % error)
    if initial_mode == "EDIT" and _set_mode(armature, "EDIT") is not None:
        raise ClearError("Cannot return to Edit Mode.")
    return removed

def clear_flexforge_data(obj, armature=None):
    """Clear the muscle data of a mesh or an armature; return the counts."""
    kind = getattr(obj, "type", None)
    report = {"bones": 0, "groups": 0, "shape_keys": 0}
    if kind == "MESH":
        rig = armature if armature is not None else armature_of_mesh(obj)
        report["groups"] = _clear_groups(obj)
        report["shape_keys"] = _clear_shape_keys(obj)
    elif kind == "ARMATURE":
        rig = armature if armature is not None else obj
    else:
        raise ClearError("Select a mesh or an armature.")
    if rig is not None and getattr(rig, "type", None) == "ARMATURE":
        report["bones"] = _clear_bones(rig)
    return report

class FLEXFORGE_OT_clear_muscles(bpy.types.Operator):
    """Remove the flexforge_* keys, muscle_* groups and muscle_* bones."""

    bl_idname = "flexforge.clear_muscles"
    bl_label = "Clear muscles"
    bl_description = ("Remove the flexforge_* shape keys, the muscle_* vertex groups and the muscle_* helper bones")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.view_layer.objects.active
        if obj is None:
            self.report({"ERROR"}, "An active mesh or armature is required.")
            return {"CANCELLED"}
        try:
            report = clear_flexforge_data(obj)
        except ClearError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        message = "FlexForge - cleared: bones=%d groups=%d shape_keys=%d" % (
            report["bones"], report["groups"], report["shape_keys"])
        self.report({"INFO"}, message)
        return {"FINISHED"}
