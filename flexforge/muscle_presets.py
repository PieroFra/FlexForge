# FlexForge — anatomical muscle preset catalog, custom spec and L/R mirror.
# Built on muscle.py (helper chain + pose constraints) and weight_nomi.py;
# no simulation, no shape key, no API newer than Blender 4.2.

import bpy

from .armatura import armature_of_mesh
from .muscle import (
    DEFAULT_BULGE,
    DEFAULT_SEGMENTS,
    SEGMENTS_MAX,
    SEGMENTS_MIN,
    MuscleError,
    MuscleSpec,
    create_muscle_chain,
    setup_muscle_constraints,
)
from .weight_nomi import invert_group_name, resolve_bone_name

# Preset ids shared by the operator, the panel and the tests.
DEFAULT_PRESET = "biceps"
CUSTOM_PRESET = "custom"
ALL_PRESETS = "all_available"
MIRROR_SUFFIX = "_r"

# Nine anatomical presets on standard `.L` bones and `spine.*` bones.
MUSCLE_PRESETS = {
    "biceps": MuscleSpec("biceps", "upper_arm.L", "forearm.L", 2),
    "triceps": MuscleSpec("triceps", "upper_arm.L", "forearm.L", 3, 1.2),
    "deltoid": MuscleSpec("deltoid", "shoulder.L", "upper_arm.L", 2, 1.4),
    "pectoral": MuscleSpec("pectoral", "spine.002", "upper_arm.L", 3, 1.3),
    "latissimus": MuscleSpec("latissimus", "spine.001", "upper_arm.L", 3),
    "quadriceps": MuscleSpec("quadriceps", "thigh.L", "shin.L", 3, 1.2),
    "hamstring": MuscleSpec("hamstring", "thigh.L", "shin.L", 2),
    "calf": MuscleSpec("calf", "shin.L", "foot.L", 2, 1.3),
    "gluteus": MuscleSpec("gluteus", "spine", "thigh.L", 2, 1.1),
}


def preset_spec(preset_id=DEFAULT_PRESET, custom_name="custom", origin_bone="",
                insertion_bone="", segments=0, bulge=-1.0):
    """MuscleSpec of a preset, a custom muscle or an override of a preset.

    Empty bone names, `segments <= 0` and `bulge < 0` fall back to the catalog
    value; for `custom` name and both bones are mandatory. Raises MuscleError.
    """
    name = str(custom_name or "").strip()
    origin = str(origin_bone or "").strip()
    insertion = str(insertion_bone or "").strip()

    if preset_id == CUSTOM_PRESET:
        if not name or not origin or not insertion:
            raise MuscleError(
                "Custom muscle: name, origin bone and insertion bone are required."
            )
        base = MuscleSpec(name, origin, insertion, DEFAULT_SEGMENTS, DEFAULT_BULGE)
    else:
        base = MUSCLE_PRESETS.get(preset_id)
        if base is None:
            raise MuscleError("Unknown muscle preset '%s'." % preset_id)

    segments = segments if segments > 0 else base.segments
    if not SEGMENTS_MIN <= segments <= SEGMENTS_MAX:
        raise MuscleError(
            "The number of segments must be between %d and %d."
            % (SEGMENTS_MIN, SEGMENTS_MAX)
        )
    return MuscleSpec(
        base.name,
        origin or base.origin_bone,
        insertion or base.insertion_bone,
        segments,
        bulge if bulge >= 0.0 else base.bulge,
    )


def mirror_spec_lr(spec):
    """Return the right side counterpart of a muscle spec (`<name>_r`)."""
    if spec.name.endswith(MIRROR_SUFFIX):
        name = spec.name
    else:
        name = spec.name + MIRROR_SUFFIX
    return MuscleSpec(name, invert_group_name(spec.origin_bone),
                      invert_group_name(spec.insertion_bone),
                      spec.segments, spec.bulge)


def _available_bones(armature):
    """Names of the armature bones, read from edit bones or object bones."""
    data = getattr(armature, "data", None)
    bones = getattr(data, "edit_bones", None)
    if bones is None:
        bones = getattr(data, "bones", None)
    return [] if bones is None else [str(getattr(b, "name", b)) for b in bones]


def _resolve_spec(spec, available):
    """Same spec with origin/insertion mapped onto the armature conventions."""
    return MuscleSpec(spec.name,
                      resolve_bone_name(spec.origin_bone, available),
                      resolve_bone_name(spec.insertion_bone, available),
                      spec.segments, spec.bulge)


def _missing_bones(spec, available):
    """Bones of the spec that are not present in the armature."""
    return [n for n in (spec.origin_bone, spec.insertion_bone) if n not in available]


def create_preset_muscles(armature, preset_id=DEFAULT_PRESET, mirror_lr=False,
                          **overrides):
    """Create one preset chain, or every preset matching the armature bones.

    Must be called in Edit Mode and returns [(spec, names)] without any
    constraint: the caller leaves Edit Mode then calls
    `setup_preset_constraints`. `all_available` keeps the presets whose bones
    exist; `mirror_lr` adds the right side. A missing bone raises MuscleError
    before anything is created.
    """
    if getattr(armature, "type", None) != "ARMATURE":
        raise MuscleError("The active object is not an armature.")
    available = _available_bones(armature)

    if preset_id == ALL_PRESETS:
        specs = []
        for _, preset in sorted(MUSCLE_PRESETS.items()):
            resolved = _resolve_spec(preset, available)
            if resolved.origin_bone == resolved.insertion_bone:
                continue
            if not _missing_bones(resolved, available):
                specs.append(resolved)
        if not specs:
            raise MuscleError("No muscle preset matches the bones of the armature.")
    else:
        specs = [_resolve_spec(preset_spec(preset_id, **overrides), available)]

    wanted = list(specs)
    if mirror_lr:
        for spec in specs:
            mirrored = _resolve_spec(mirror_spec_lr(spec), available)
            if mirrored.origin_bone == mirrored.insertion_bone:
                continue
            if preset_id != ALL_PRESETS or not _missing_bones(mirrored, available):
                wanted.append(mirrored)

    # Validate every spec first: a missing bone must not leave a half done rig.
    for spec in wanted:
        missing = _missing_bones(spec, available)
        if missing:
            raise MuscleError("Bones missing for '%s': %s."
                              % (spec.name, ", ".join(missing)))

    return [(spec, create_muscle_chain(armature, spec)) for spec in wanted]


def setup_preset_constraints(armature, created):
    """Pose-driven STRETCH_TO constraints for every created chain."""
    handled = 0
    for spec, names in created:
        handled += setup_muscle_constraints(armature, names, spec)
    return handled


def _set_mode(armature, mode):
    """Switch the armature to `mode`; return the RuntimeError or None."""
    if armature.mode == mode:
        return None
    try:
        bpy.ops.object.mode_set(mode=mode)
    except RuntimeError as error:
        return error


def _select_only(active, selected):
    """Reselect exactly `selected` and make `active` the active object."""
    view_layer = bpy.context.view_layer
    for obj in view_layer.objects:
        obj.select_set(False)
    for obj in selected:
        if obj.name in view_layer.objects:
            obj.select_set(True)
    if active is not None:
        view_layer.objects.active = active


class FLEXFORGE_OT_create_muscle_preset(bpy.types.Operator):
    """Create the helper bone chains of a muscle preset on the active armature."""

    bl_idname = "flexforge.create_muscle_preset"
    bl_label = "Create muscle preset"
    bl_description = "Create the deforming helper bones of a muscle preset"
    bl_options = {"REGISTER", "UNDO"}

    preset: bpy.props.StringProperty(name="Preset", default=DEFAULT_PRESET)
    mirror_lr: bpy.props.BoolProperty(name="Mirror L/R", default=False)
    custom_name: bpy.props.StringProperty(name="Custom name", default="custom")
    origin_bone: bpy.props.StringProperty(name="Origin bone", default="")
    insertion_bone: bpy.props.StringProperty(name="Insertion bone", default="")
    segments: bpy.props.IntProperty(name="Segments", default=0, min=0, max=SEGMENTS_MAX)
    bulge: bpy.props.FloatProperty(name="Bulge", default=-1.0, min=-1.0, max=5.0)

    def execute(self, context):
        previous_active = context.view_layer.objects.active
        previous_selected = [obj for obj in context.selected_objects]
        armature = previous_active
        if armature is not None and getattr(armature, "type", None) == "MESH":
            armature = armature_of_mesh(armature)
        if armature is None or armature.type != "ARMATURE":
            self.report({"ERROR"}, "Select the rig: an active armature is required.")
            return {"CANCELLED"}

        initial_mode = armature.mode
        # The rig must be the active object, otherwise `mode_set` edits the mesh.
        _select_only(armature, [armature])
        error = _set_mode(armature, "EDIT")
        if error is not None:
            _select_only(previous_active, previous_selected)
            self.report({"ERROR"}, f"Cannot switch to Edit Mode: {error}")
            return {"CANCELLED"}

        created = None
        try:
            created = create_preset_muscles(
                armature,
                self.preset,
                self.mirror_lr,
                custom_name=self.custom_name,
                origin_bone=self.origin_bone,
                insertion_bone=self.insertion_bone,
                segments=self.segments,
                bulge=self.bulge,
            )
        except MuscleError as error:
            self.report({"ERROR"}, str(error))
        finally:
            # `edit_bones` populate `pose.bones` only once Edit Mode is left.
            exit_error = _set_mode(armature, "OBJECT")
            _select_only(previous_active, previous_selected)
        if created is None:
            return {"CANCELLED"}
        if exit_error is not None:
            self.report({"ERROR"}, f"Cannot return to Object Mode: {exit_error}")
            return {"CANCELLED"}

        _select_only(armature, [armature])
        setup_preset_constraints(armature, created)
        _select_only(previous_active, previous_selected)
        if initial_mode == "EDIT":
            error = _set_mode(armature, "EDIT")
            if error is not None:
                self.report({"ERROR"}, f"Cannot return to Edit Mode: {error}")

        names = [name for _, chain in created for name in chain]
        self.report(
            {"INFO"}, "Created %d segments: %s" % (len(names), ", ".join(names))
        )
        return {"FINISHED"}
