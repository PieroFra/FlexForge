# FlexForge - end-to-end full-body muscle pipeline (no operator class).
# Orchestrates rig detection, helper creation, capsule skinning, shape-key
# baking, deformation verification and engine budget in a single undo step:
# mode switches pass undo=False and all other stages call Python helpers directly.

import bpy

from .armatura import armature_of_mesh
from .engine_budget import DEFAULT_MAX_BONES, DEFAULT_MAX_SHAPE_KEYS, LOD_LEVELS, BudgetError, apply_engine_budget
from .muscle import MUSCLE_PREFIX, MuscleError
from .muscle_bake import BASIS_KEY_NAME, DEFAULT_DISPLACEMENT, SHAPE_KEY_PREFIX, BakeError, apply_muscle_bake
from .muscle_presets import _select_only, create_preset_muscles, setup_preset_constraints
from .muscle_skinning import DEFAULT_RADIUS, SkinningError, apply_muscle_skinning
from .rig_detect import RigDetectError, detect_rig, full_body_message, resolved_bones_for_preset
from .verify import validate_deformation
from .weights import MAX_INFLUENCES_DEFAULT, MAX_INFLUENCES_MIN, WeightsError

NO_PRESETS = "FlexForge - rig: no presets available on this rig"


class FullBodyError(Exception):
    """Full-body pipeline domain error, with an English message."""


def meshes_of_armature(armature, objects):
    """Return every MESH in `objects` deformed by `armature`."""
    if armature is None:
        return []
    return [
        obj for obj in (objects or ())
        if getattr(obj, "type", None) == "MESH" and armature_of_mesh(obj) == armature
    ]


def resolve_targets(context, active=None):
    """Resolve `(armature, meshes)` from the active object and scene."""
    if active is None and context is not None:
        view_layer = getattr(context, "view_layer", None)
        objects = getattr(view_layer, "objects", None)
        active = getattr(objects, "active", None)
    if active is None:
        raise FullBodyError("Select an armature or a rigged mesh first.")

    kind = getattr(active, "type", None)
    if kind == "MESH":
        armature = armature_of_mesh(active)
        if armature is None or getattr(armature, "type", None) != "ARMATURE":
            raise FullBodyError("The active mesh has no Armature modifier.")
        return armature, [active]

    if kind == "ARMATURE":
        scene_objs = getattr(getattr(context, "scene", None), "objects", ())
        meshes = meshes_of_armature(active, scene_objs)
        if not meshes:
            raise FullBodyError(
                "No mesh bound to armature '%s': add an Armature modifier first."
                % getattr(active, "name", "Armature")
            )
        return active, meshes

    raise FullBodyError("Select an armature or a rigged mesh first.")


def _set_mode_no_undo(armature, mode):
    """Switch `armature` to `mode` without pushing an internal undo step."""
    if getattr(armature, "mode", None) == mode:
        return None
    try:
        bpy.ops.object.mode_set("EXEC_DEFAULT", False, mode=mode)
    except RuntimeError as error:
        return error
    return None


def _snapshot_state(armature, meshes):
    """Record pre-existing helper bones, muscle groups and flexforge keys."""
    bones = getattr(getattr(armature, "data", None), "bones", ()) or ()
    bone_names = {b.name for b in bones if str(b.name).startswith(MUSCLE_PREFIX)}
    groups = {}
    keys = {}
    for mesh in meshes:
        mid = id(mesh)
        groups[mid] = {
            g.name for g in (getattr(mesh, "vertex_groups", ()) or ())
            if str(g.name).startswith(MUSCLE_PREFIX)
        }
        sk = getattr(getattr(mesh, "data", None), "shape_keys", None)
        blocks = getattr(sk, "key_blocks", ()) or ()
        keys[mid] = {
            kb.name for kb in blocks
            if str(kb.name).startswith(SHAPE_KEY_PREFIX) or kb.name == BASIS_KEY_NAME
        }
    return {"bones": bone_names, "groups": groups, "keys": keys}


def _rollback_state(armature, meshes, snapshot):
    """Remove only the bones, groups and shape keys added during this run."""
    for mesh in meshes:
        mid = id(mesh)
        sk = getattr(getattr(mesh, "data", None), "shape_keys", None)
        blocks = list(getattr(sk, "key_blocks", ()) or ())
        old_keys = snapshot["keys"].get(mid, set())
        for kb in reversed(blocks):
            name = getattr(kb, "name", "")
            is_ff = str(name).startswith(SHAPE_KEY_PREFIX) or name == BASIS_KEY_NAME
            if is_ff and name not in old_keys:
                try:
                    kb.driver_remove("value")
                except Exception:
                    pass
                try:
                    mesh.shape_key_remove(kb)
                except Exception:
                    pass
        old_groups = snapshot["groups"].get(mid, set())
        for group in list(getattr(mesh, "vertex_groups", ()) or ()):
            if str(group.name).startswith(MUSCLE_PREFIX) and group.name not in old_groups:
                mesh.vertex_groups.remove(group)

    old_bones = snapshot["bones"]
    if getattr(armature, "mode", None) == "EDIT":
        edit_bones = getattr(getattr(armature, "data", None), "edit_bones", None)
        if edit_bones is not None:
            for eb in list(edit_bones):
                if str(eb.name).startswith(MUSCLE_PREFIX) and eb.name not in old_bones:
                    edit_bones.remove(eb)
        _select_only(armature, [armature])
        _set_mode_no_undo(armature, "OBJECT")
        return

    bones = list(getattr(getattr(armature, "data", None), "bones", ()) or ())
    added_bones = [
        b.name for b in bones
        if str(b.name).startswith(MUSCLE_PREFIX) and b.name not in old_bones
    ]
    if added_bones:
        _select_only(armature, [armature])
        if _set_mode_no_undo(armature, "EDIT") is None:
            edit_bones = getattr(armature.data, "edit_bones", None)
            if edit_bones is not None:
                for name in added_bones:
                    eb = edit_bones.get(name)
                    if eb is not None:
                        edit_bones.remove(eb)
            _set_mode_no_undo(armature, "OBJECT")


def _validate_params(bind_radius, displacement, max_influences, lod):
    if bind_radius <= 0.0:
        raise FullBodyError("The bind radius must be greater than zero.")
    if displacement <= 0.0:
        raise FullBodyError("The displacement must be greater than zero.")
    if max_influences < MAX_INFLUENCES_MIN:
        raise FullBodyError("Max influences must be at least %d." % MAX_INFLUENCES_MIN)
    if lod not in LOD_LEVELS:
        raise FullBodyError("Unknown LOD level %r." % (lod,))


def _over_budget_warning(mesh, mesh_name, last_budget, deform_count, max_shape_keys, max_bones, lod):
    b_rep = last_budget.get("report", {})
    sk = getattr(getattr(mesh, "data", None), "shape_keys", None)
    live_keys = sum(1 for kb in (getattr(sk, "key_blocks", ()) or ()) if str(getattr(kb, "name", "")).startswith(SHAPE_KEY_PREFIX))
    cap_k, cap_b = b_rep.get("max_shape_keys", max_shape_keys), b_rep.get("max_bones", max_bones)
    if not b_rep.get("within_budget", True) or (lod != 0 and (live_keys > cap_k or deform_count > cap_b)):
        return "%s: over budget (keys=%s/%s bones=%s/%s lod=%s)" % (
            mesh_name, max(live_keys, b_rep.get("shape_keys", 0)), cap_k,
            max(deform_count, b_rep.get("bones", 0)), cap_b, b_rep.get("lod", lod),
        )
    return None


def run_full_body_pipeline(
    armature, meshes, mirror_lr=True, bind_radius=DEFAULT_RADIUS,
    displacement=DEFAULT_DISPLACEMENT, anatomical_taper=True,
    directional_bias=True, smooth_iterations=2, drive_by_pose=True,
    max_influences=MAX_INFLUENCES_DEFAULT, lod=1,
    max_shape_keys=DEFAULT_MAX_SHAPE_KEYS, max_bones=DEFAULT_MAX_BONES,
):
    """Run the full-body pipeline from helper creation to engine budget."""
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        raise FullBodyError("An active armature is required.")
    if not meshes:
        raise FullBodyError("At least one bound mesh is required.")
    _validate_params(bind_radius, displacement, max_influences, lod)

    bones = list(getattr(getattr(armature, "data", None), "bones", ()) or ())
    bone_names = [bone.name for bone in bones]
    report = detect_rig(bone_names, {b.name: (b.parent.name if b.parent else "") for b in bones})
    if not report["preset_ids"]:
        raise FullBodyError(NO_PRESETS)

    snapshot = _snapshot_state(armature, meshes)
    created, chains, warnings, budgets = [], [], [], {}
    segments = total_keys = total_drivers = 0
    last_budget = None

    try:
        for mesh in meshes:
            if getattr(mesh, "mode", "OBJECT") != "OBJECT":
                _select_only(mesh, [mesh])
                _set_mode_no_undo(mesh, "OBJECT")
        _select_only(armature, [armature])
        mode_err = _set_mode_no_undo(armature, "EDIT")
        if mode_err is not None:
            raise FullBodyError("Cannot switch to Edit Mode: %s" % mode_err)

        for preset_id in report["preset_ids"]:
            resolved = resolved_bones_for_preset(preset_id, bone_names, mirror_lr)
            if resolved["origin"] not in bone_names or resolved["insertion"] not in bone_names:
                continue
            can_mirror = bool(mirror_lr and resolved.get("origin_r") in bone_names and resolved.get("insertion_r") in bone_names)
            preset_chains = create_preset_muscles(armature, preset_id, mirror_lr=can_mirror)
            chains.extend(preset_chains)
            created.append(preset_id)
            segments += sum(len(names) for _, names in preset_chains)

        exit_err = _set_mode_no_undo(armature, "OBJECT")
        if exit_err is not None:
            raise FullBodyError("Cannot return to Object Mode: %s" % exit_err)
        if not created:
            raise FullBodyError("No muscle preset could be created on this rig.")
        if chains:
            setup_preset_constraints(armature, chains)

        arm_bones = getattr(getattr(armature, "data", None), "bones", ()) or ()
        helper_bones = [b.name for b in arm_bones if getattr(b, "use_deform", True) and str(b.name).startswith(MUSCLE_PREFIX)]
        deform_count = sum(1 for b in arm_bones if getattr(b, "use_deform", False))
        for mesh in meshes:
            mesh_name = getattr(mesh, "name", "mesh")
            skin_report = apply_muscle_skinning(mesh, armature=armature, radius=bind_radius, max_influences=max_influences)
            bake_report = apply_muscle_bake(
                mesh, armature=armature, displacement=displacement,
                strip_muscle_weights=True, max_influences=max_influences,
                drive_by_pose=drive_by_pose, anatomical_taper=anatomical_taper,
                directional_bias=directional_bias, smooth_iterations=smooth_iterations,
            )
            total_keys += bake_report.get("shape_keys", 0)
            total_drivers += bake_report.get("drivers_added", 0)
            verify_report = validate_deformation(skin_report["weights"], helper_bones, max_influences)
            if not verify_report["valid"]:
                warnings.append("%s: %s" % (mesh_name, verify_report["reason"]))
            last_budget = apply_engine_budget(
                mesh, max_influences=max_influences, max_shape_keys=max_shape_keys,
                max_bones=max_bones, lod=lod, armature=armature,
            )
            budgets[mesh_name] = last_budget
            warn = _over_budget_warning(mesh, mesh_name, last_budget, deform_count, max_shape_keys, max_bones, lod)
            if warn:
                warnings.append(warn)
    except (MuscleError, RigDetectError, SkinningError, BakeError, WeightsError, BudgetError, FullBodyError):
        _rollback_state(armature, meshes, snapshot)
        raise

    message = "%s | meshes=%d shape_keys=%d drivers=%d" % (
        full_body_message(report, segments, created), len(meshes), total_keys, total_drivers
    )
    if warnings:
        message = "%s | warnings=%d" % (message, len(warnings))
    return {
        "report": report, "created": created, "segments": segments,
        "meshes": len(meshes), "shape_keys": total_keys,
        "drivers_added": total_drivers, "warnings": warnings,
        "has_warnings": bool(warnings), "budget": last_budget,
        "budgets": budgets, "message": message,
    }
