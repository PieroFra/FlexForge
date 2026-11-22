# FlexForge — minimal muscle representation (biceps only).
# No simulation and no shape key: the muscle is a chain of deforming helper
# bones interpolated between origin bone and insertion bone.
# APIs used are present on both Blender 4.2 and 5.3 (no 4.3+ APIs).

from dataclasses import dataclass

import bpy

# Constants shared by operator, panel and tests.
MUSCLE_PREFIX = "muscle_"
DEFAULT_MUSCLE_NAME = "biceps"
DEFAULT_ORIGIN_BONE = "upper_arm.L"
DEFAULT_INSERTION_BONE = "forearm.L"
DEFAULT_SEGMENTS = 2
SEGMENTS_MIN = 1
SEGMENTS_MAX = 8
DEFAULT_BULGE = 1.0
CONSTRAINT_NAME = "FlexForge Stretch"


class MuscleError(Exception):
    """Muscle module domain error, with an English message."""


@dataclass
class MuscleSpec:
    """Minimal description of a muscle as a chain of helper bones."""

    name: str = DEFAULT_MUSCLE_NAME
    origin_bone: str = DEFAULT_ORIGIN_BONE
    insertion_bone: str = DEFAULT_INSERTION_BONE
    segments: int = DEFAULT_SEGMENTS
    bulge: float = DEFAULT_BULGE


def muscle_bone_name(muscle_name, index):
    """Deterministic helper bone name, with the `muscle_` prefix."""
    return "%s%s_%02d" % (MUSCLE_PREFIX, muscle_name, index)


def _interpolate(point_a, point_b, factor):
    """Linear per-component interpolation (tuple or Vector)."""
    return tuple(
        point_a[i] + (point_b[i] - point_a[i]) * factor for i in range(3)
    )


def compute_segments(point_a, point_b, segments):
    """Return `segments` contiguous (head, tail) pairs between the two points."""
    if segments < SEGMENTS_MIN:
        raise MuscleError(
            "The number of segments must be at least %d." % SEGMENTS_MIN
        )
    points = [
        _interpolate(point_a, point_b, i / float(segments))
        for i in range(segments + 1)
    ]
    return [(points[i], points[i + 1]) for i in range(segments)]


def create_muscle_chain(armature, spec=None):
    """Create the deforming helper bone chain and return the created names.

    Must be called with the armature in Edit Mode: it works on
    `data.edit_bones`. Each helper bone is linearly interpolated between the
    head of the origin bone and the head of the insertion bone: the chain stops
    at the joint, so a helper never reaches into the next bone of the limb. The
    first bone is a child of the origin bone, the others form a chain; no
    constraints.
    """
    if spec is None:
        spec = MuscleSpec()
    if getattr(armature, "type", None) != "ARMATURE":
        raise MuscleError("The active object is not an armature.")
    if spec.segments < SEGMENTS_MIN:
        raise MuscleError(
            "The number of segments must be at least %d." % SEGMENTS_MIN
        )

    bones = armature.data.edit_bones
    origin_bone = bones.get(spec.origin_bone)
    if origin_bone is None:
        raise MuscleError(
            "Origin bone '%s' missing in the armature."
            % spec.origin_bone
        )
    insertion_bone = bones.get(spec.insertion_bone)
    if insertion_bone is None:
        raise MuscleError(
            "Insertion bone '%s' missing in the armature."
            % spec.insertion_bone
        )

    names = [
        muscle_bone_name(spec.name, index + 1)
        for index in range(spec.segments)
    ]
    for name in names:
        if bones.get(name) is not None:
            raise MuscleError(
                "Bone '%s' already present in the armature." % name
            )

    segments = compute_segments(
        origin_bone.head, insertion_bone.head, spec.segments
    )
    previous = origin_bone
    for name, (head, tail) in zip(names, segments):
        bone = bones.new(name)
        bone.head = head
        bone.tail = tail
        bone.use_deform = True
        bone.use_connect = False
        bone.parent = previous
        previous = bone

    return names


def setup_muscle_constraints(armature, names, spec=None):
    """Add a pose-driven STRETCH_TO constraint to each helper bone.

    Must be called after leaving Edit Mode (it works on `armature.pose`): the
    stretch follows the insertion bone so the muscle deforms with the pose.
    Existing FlexForge constraints are updated instead of duplicated. Returns
    the number of helper bones handled.
    """
    if spec is None:
        spec = MuscleSpec()
    pose = getattr(armature, "pose", None)
    if pose is None:
        return 0

    handled = 0
    for name in names:
        pose_bone = pose.bones.get(name)
        if pose_bone is None:
            continue
        existing = [
            constraint
            for constraint in pose_bone.constraints
            if constraint.name == CONSTRAINT_NAME
        ]
        if existing:
            constraint = existing[0]
        else:
            constraint = pose_bone.constraints.new(type="STRETCH_TO")
            constraint.name = CONSTRAINT_NAME
        constraint.target = armature
        constraint.subtarget = spec.insertion_bone
        constraint.head_tail = 0.0
        constraint.volume = "VOLUME_XZX"
        constraint.bulge = spec.bulge
        handled += 1

    return handled


class FLEXFORGE_OT_create_biceps(bpy.types.Operator):
    """Create the biceps helper bone chain on the active armature."""

    bl_idname = "flexforge.create_biceps"
    bl_label = "Create biceps"
    bl_description = (
        "Create the deforming helper bones of the biceps (no simulation)"
    )
    bl_options = {"REGISTER", "UNDO"}

    origin_bone: bpy.props.StringProperty(
        name="Origin bone", default=DEFAULT_ORIGIN_BONE
    )
    insertion_bone: bpy.props.StringProperty(
        name="Insertion bone", default=DEFAULT_INSERTION_BONE
    )
    segments: bpy.props.IntProperty(
        name="Segments",
        default=DEFAULT_SEGMENTS,
        min=SEGMENTS_MIN,
        max=SEGMENTS_MAX,
    )
    bulge: bpy.props.FloatProperty(
        name="Bulge", default=DEFAULT_BULGE, min=0.0, max=5.0
    )

    def execute(self, context):
        armature = context.view_layer.objects.active
        if armature is None or armature.type != "ARMATURE":
            self.report(
                {"ERROR"}, "An active armature is required: select the rig and try again."
            )
            return {"CANCELLED"}

        spec = MuscleSpec(
            origin_bone=self.origin_bone,
            insertion_bone=self.insertion_bone,
            segments=self.segments,
            bulge=self.bulge,
        )

        initial_mode = armature.mode
        if initial_mode != "EDIT":
            try:
                bpy.ops.object.mode_set(mode="EDIT")
            except RuntimeError as error:
                self.report({"ERROR"}, f"Cannot switch to Edit Mode: {error}")
                return {"CANCELLED"}
        exit_error = None
        try:
            names = create_muscle_chain(armature, spec)
        except MuscleError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        finally:
            # `edit_bones` populate `pose.bones` only once Edit Mode is left.
            if armature.mode == "EDIT":
                try:
                    bpy.ops.object.mode_set(mode="OBJECT")
                except RuntimeError as error:
                    exit_error = error
        if exit_error is not None:
            self.report({"ERROR"}, f"Cannot return to Object Mode: {exit_error}")
            return {"CANCELLED"}

        setup_muscle_constraints(armature, names, spec)

        if initial_mode == "EDIT":
            try:
                bpy.ops.object.mode_set(mode="EDIT")
            except RuntimeError as error:
                self.report({"ERROR"}, f"Cannot return to Edit Mode: {error}")

        self.report(
            {"INFO"}, "Created %d segments: %s" % (len(names), ", ".join(names))
        )
        return {"FINISHED"}
