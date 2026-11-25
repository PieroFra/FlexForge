# FlexForge - rig detection helper (pure, no bpy objects).
# Detects the rig convention from a list of bone names (standard,
# Mixamo, Bip01, ARP/Rigify aliases) reusing the canonical bone aliases
# from weight_nomi.py, and reports which muscle presets can be created
# on it. The bpy operator that creates the full-body set lives in this
# module as well, but detection is pure and shared with the tests.

import bpy

from .muscle_presets import MUSCLE_PRESETS
from .weight_nomi import (
    BONE_ALIASES,
    invert_group_name,
    resolve_bone_name,
)


class RigDetectError(Exception):
    """Rig detection domain error, with an English message."""


# Canonical bones required by a preset (origin/insertion) per preset id.
# A preset is "available" when both bones resolve on the rig.
_PRESET_BONES = {}
for _preset_id, _spec in MUSCLE_PRESETS.items():
    _PRESET_BONES[_preset_id] = (_spec.origin_bone, _spec.insertion_bone)


# Expected parent links between the 9 canonical muscle anchors, as the
# canonical name. A link is only checked when the real parent resolves to
# one of those anchors (so a bone like mixamorig:Hips for the thighs is
# skipped, not treated as an error). shoulder.L is allowed under spine
# because rigs without a clavicle bone attach it there.
_TOPOLOGY_EXPECTATIONS = {
    "upper_arm.L": ("shoulder.L",),
    "forearm.L": ("upper_arm.L",),
    "shoulder.L": ("spine", "spine.001"),
    "spine": (),
    "spine.001": ("spine",),
    "spine.002": ("spine.001",),
    "thigh.L": ("spine",),
    "shin.L": ("thigh.L",),
    "foot.L": ("shin.L",),
}


def detect_rig(bone_names, parents=None):
    """Detect the rig convention and the available presets from bone names.

    `bone_names` is an iterable of bone names as found on the rig.
    `parents` is an optional dict {bone_name: parent_name_or_empty} with the
    real parent chain: it validates the 9 muscle anchors, so a rig that
    carries the right names but the wrong attachments must not pass as
    mixamo. The rig
    type is inferred from which alias families resolve: mixamo when
    `mixamorig:`/LeftArm style aliases resolve, bip01 on Bip01 aliases,
    standard on the canonical .L/.R names (also ARP/Rigify def- aliases,
    which resolve through BONE_ALIASES). A preset is available when its
    origin and insertion bones both resolve.

    Return {rig_type, matched, missing, coverage, preset_ids, matched_bones,
    topology_ok, topology_checked, topology_bad} where coverage is
    matched/total over the 9 canonical preset bones and preset_ids are the
    presets whose both bones resolve and whose anchor chain is intact, in
    catalog order. topology_ok is None when no parent map is given;
    topology_bad lists the anchors whose parent contradicts the expected
    link, so they are not offered as available.
    """
    names = [str(name) for name in bone_names]
    if not names:
        return {
            "rig_type": "unknown",
            "matched": 0,
            "missing": 0,
            "coverage": 0.0,
            "preset_ids": [],
            "matched_bones": {},
            "topology_ok": None,
            "topology_checked": 0,
            "topology_bad": [],
        }

    def present(canonical):
        resolved = resolve_bone_name(canonical, names)
        return resolved in names

    total = 0
    matched = 0
    matched_bones = {}
    for preset_id, (origin, insertion) in _PRESET_BONES.items():
        for canonical in (origin, insertion):
            if canonical in matched_bones:
                continue
            total += 1
            if present(canonical):
                matched += 1
                matched_bones[canonical] = resolve_bone_name(canonical, names)

    topology_ok = None
    topology_checked = 0
    topology_bad = []

    anchor_of_name = {}
    for canonical in {bone for pair in _PRESET_BONES.values() for bone in pair}:
        resolved = resolve_bone_name(canonical, names)
        if resolved in names:
            anchor_of_name[resolved] = canonical

    if parents is not None:
        topology_ok = True
        for bone_name, parent_name in parents.items():
            if not parent_name or bone_name not in anchor_of_name:
                continue
            parent_canonical = anchor_of_name.get(str(parent_name))
            if parent_canonical is None:
                continue
            topology_checked += 1
            allowed = _TOPOLOGY_EXPECTATIONS.get(anchor_of_name[bone_name], ())
            if parent_canonical not in allowed:
                anchor = anchor_of_name[bone_name]
                if anchor not in topology_bad:
                    topology_bad.append(anchor)
        if topology_checked:
            topology_ok = not bool(topology_bad)
        else:
            topology_ok = None

    presets = []
    for preset_id, (origin, insertion) in _PRESET_BONES.items():
        if origin in topology_bad or insertion in topology_bad:
            continue
        if present(origin) and present(insertion):
            presets.append(preset_id)

    # Rig type from the alias families that actually resolved on this rig.
    def any_resolves(aliases):
        return any(a in names for a in aliases)

    mixamo_aliases = []
    bip01_aliases = []
    for canonical, aliases in BONE_ALIASES.items():
        for alias in aliases:
            if isinstance(alias, str):
                if alias.startswith("mixamorig:") or alias.startswith("Left") or alias.startswith("Right"):
                    mixamo_aliases.append(alias)
                elif alias.startswith("Bip01"):
                    bip01_aliases.append(alias)

    rig_type = "unknown"
    if presets:
        if any_resolves(mixamo_aliases) and not any_resolves(bip01_aliases):
            rig_type = "mixamo"
        elif any_resolves(bip01_aliases):
            rig_type = "bip01"
        else:
            rig_type = "standard"

    if not presets:
        rig_type = "unknown"

    missing = total - matched
    coverage = (matched / total) if total else 0.0
    return {
        "rig_type": rig_type,
        "matched": matched,
        "missing": missing,
        "coverage": coverage,
        "preset_ids": presets,
        "matched_bones": matched_bones,
        "topology_ok": topology_ok,
        "topology_checked": topology_checked,
        "topology_bad": topology_bad,
    }


def resolved_bones_for_preset(preset_id, bone_names, mirror_lr=True):
    """Resolved origin/insertion bone names for a preset on a rig.

    Names are resolved through the aliases (Mixamo/Bip01/ARP/standard).
    With `mirror_lr` the mirrored (.R) counterparts are included as
    origin_r/insertion_r. Raise RigDetectError for an unknown preset.
    """
    if preset_id not in MUSCLE_PRESETS:
        raise RigDetectError("Unknown muscle preset '%s'." % preset_id)
    names = [str(name) for name in bone_names]
    origin, insertion = _PRESET_BONES[preset_id]
    result = {
        "origin": resolve_bone_name(origin, names),
        "insertion": resolve_bone_name(insertion, names),
    }
    if mirror_lr:
        result["origin_r"] = resolve_bone_name(
            invert_group_name(origin), names
        )
        result["insertion_r"] = resolve_bone_name(
            invert_group_name(insertion), names
        )
    return result


def detect_message(report):
    """Rig detection summary line, in English and unambiguous."""
    return (
        "FlexForge - rig: type=%s coverage=%.2f matched=%d missing=%d presets=%s"
        % (
            report["rig_type"],
            report["coverage"],
            report["matched"],
            report["missing"],
            ",".join(report["preset_ids"]) if report["preset_ids"] else "none",
        )
    )


def apply_full_body(obj, report, armature=None, mirror_lr=True):
    """Create and bind every available preset of a detected rig.

    Reuses create_preset_muscles/setup_preset_constraints via
    muscle_presets. Presets are only created when their origin/insertion
    bones actually resolve on the rig (canonical names present in
    bone_names); the mesh weights are not written here: binding
    (muscle_skinning) is a separate, already tested step. Must be called
    in Edit Mode when armature is given. Returns
    {created, report, message}.
    """
    from .muscle_presets import create_preset_muscles, setup_preset_constraints

    armature = armature if armature is not None else getattr(obj, "parent", None)
    bone_names = []
    if armature is not None:
        bone_names = [bone.name for bone in getattr(getattr(armature, "data", None), "bones", ())]
    if not report["preset_ids"] or not bone_names:
        return {
            "created": [],
            "report": report,
            "message": "FlexForge - rig: no presets available on this rig",
        }
    created = []
    chains = []
    for preset_id in report["preset_ids"]:
        resolved = resolved_bones_for_preset(preset_id, bone_names, mirror_lr)
        origin = resolved["origin"]
        insertion = resolved["insertion"]
        if origin not in bone_names or insertion not in bone_names:
            continue
        chains.extend(
            create_preset_muscles(armature, preset_id, mirror_lr=mirror_lr)
        )
        created.append(preset_id)
    if chains:
        setup_preset_constraints(armature, chains)
    return {
        "created": created,
        "report": report,
        "message": detect_message(report),
    }


class FLEXFORGE_OT_detect_rig(bpy.types.Operator):
    """Detect the rig convention of the active armature and print the report."""

    bl_idname = "flexforge.detect_rig"
    bl_label = "Detect rig"
    bl_description = "Detect the rig convention (standard, Mixamo, Bip01) from the active armature and print the available muscle presets"
    bl_options = {"REGISTER"}

    def execute(self, context):
        rig = context.view_layer.objects.active
        if rig is None or rig.type != "ARMATURE":
            self.report({"ERROR"}, "An active armature is required: select the rig and try again.")
            return {"CANCELLED"}
        bone_names = [bone.name for bone in getattr(getattr(rig, "data", None), "bones", ())]
        if not bone_names:
            self.report({"ERROR"}, "The armature has no bones to detect.")
            return {"CANCELLED"}
        parents = {
            bone.name: (bone.parent.name if bone.parent else "")
            for bone in getattr(getattr(rig, "data", None), "bones", ())
        }
        report = detect_rig(bone_names, parents)
        message = detect_message(report)
        print(message)
        self.report({"INFO"}, message)
        return {"FINISHED"}
