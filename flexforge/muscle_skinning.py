# FlexForge — capsule auto-skinning of the muscle helpers.
# The pure capsule math lives in `.muscle_capsule` and is re-imported here so
# the operator and existing callers keep the same names; this module keeps the
# bpy side: bone collection, group creation and the operator.

import bpy

from .armatura import armature_of_mesh
from .muscle import MUSCLE_PREFIX
from .muscle_side import is_torso_bone, passes_side, side_direction, unit_vector
from .muscle_capsule import (
    DEFAULT_BONE_RADIUS,
    DEFAULT_INTENSITY,
    DEFAULT_RADIUS,
    FOOT_EXCLUDE_TOKENS,
    SkinningError,
    _capsule_radius,
    _capsule_side,
    _chain_length,
    _distance,
    _excluded_vertices,
    _mask_vertices,
    _preserve_skeletal,
    _segment_of,
    bone_radius,
    capsule_weight,
    compute_muscle_weights,
    is_excluded_bone,
    segment_distance,
)
from .weights import (
    MAX_INFLUENCES_DEFAULT,
    MAX_INFLUENCES_MIN,
    WeightsError,
    read_weights,
    write_weights,
)

def _bone_segment(bone):
    """Local head/tail of a bone, falling back on the global head/tail."""
    head = getattr(bone, "head_local", None) or getattr(bone, "head", None)
    tail = getattr(bone, "tail_local", None) or getattr(bone, "tail", None)
    return tuple(head), tuple(tail)

def _armature_to_mesh_matrix(obj, armature):
    """Armature local space to mesh local space, with its uniform scale.

    A rig carrying `scale=(0.01,) * 3` and a 90 degree rotation (any FBX/GLB
    import) lives in a different space than the mesh: bone head/tail and the
    capsule radius must travel through this matrix. Returns `(None, 1.0)` when
    the objects have no world matrix, so the fake objects keep working.
    """
    world = getattr(armature, "matrix_world", None)
    mesh_world = getattr(obj, "matrix_world", None) if obj is not None else None
    if world is None or mesh_world is None:
        return None, 1.0
    matrix = mesh_world.inverted() @ world
    return matrix, max(abs(value) for value in matrix.to_scale()) or 1.0

def _matrix_point(matrix, point):
    """Apply a 4x4 matrix to a point; mathutils is imported on demand."""
    from mathutils import Vector
    return tuple(matrix @ Vector(tuple(point)))

def _parent_owner(bone):
    """Nearest non-muscle ancestor of a helper (its origin bone), or ''."""
    parent = getattr(bone, "parent", None)
    while parent is not None:
        name = str(getattr(parent, "name", ""))
        if not name.startswith(MUSCLE_PREFIX):
            return name
        parent = getattr(parent, "parent", None)
    return ""

def _owner_bones(bone, bones):
    """Non-muscle origin (parent) and insertion (nearest head to the tail)."""
    origin = _parent_owner(bone)
    owners = [origin] if origin else []
    tail = _bone_segment(bone)[1]
    others = [other for other in bones if not str(
        other.name).startswith(MUSCLE_PREFIX) and str(other.name) not in owners]
    if others:
        nearest = min(others, key=lambda item: _distance(_bone_segment(item)[0], tail))
        owners.append(str(nearest.name))
    return owners

def _mesh_diagonal(coordinates):
    """Bounding-box diagonal of the local vertex cloud, 0.0 when degenerate."""
    if not coordinates:
        return 0.0
    spans = [max(point[axis] for point in coordinates)
             - min(point[axis] for point in coordinates) for axis in range(3)]
    return sum(span * span for span in spans) ** 0.5

def apply_muscle_skinning(obj, armature=None, radius=DEFAULT_RADIUS,
                          intensity=DEFAULT_INTENSITY,
                          max_influences=MAX_INFLUENCES_DEFAULT):
    """Create the missing `muscle_*` groups, skin the mesh and write weights."""
    if obj is None or getattr(obj, "type", None) != "MESH":
        raise SkinningError("An active mesh is required: select it first.")
    if radius <= 0.0:
        raise SkinningError("The capsule radius must be greater than zero.")
    if armature is None:
        armature = armature_of_mesh(obj)
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        raise SkinningError("An armature is required: add an Armature modifier.")

    matrix, scale = _armature_to_mesh_matrix(obj, armature)
    bones = list(armature.data.bones)
    segments = {}
    bone_masks = {}
    for bone in bones:
        if bone.use_deform and bone.name.startswith(MUSCLE_PREFIX):
            head, tail = _bone_segment(bone)
            if matrix is not None:
                head, tail = _matrix_point(matrix, head), _matrix_point(matrix, tail)
            segment = {"head_local": head, "tail_local": tail,
                       "radius": bone_radius(bone) * scale}
            if is_torso_bone(_parent_owner(bone)):
                segment["side_filter"] = True
            segments[bone.name] = segment
            bone_masks[bone.name] = _owner_bones(bone, bones)
    if not segments:
        raise SkinningError(
            "No deforming '%s*' helper bones on the armature." % MUSCLE_PREFIX
        )

    present = {group.name for group in obj.vertex_groups}
    for name in sorted(set(segments) - present):
        obj.vertex_groups.new(name=name)

    coordinates = [tuple(vertex.co) for vertex in obj.data.vertices]
    report = compute_muscle_weights(
        read_weights(obj), coordinates, segments, radius, intensity,
        max_influences, bone_masks, FOOT_EXCLUDE_TOKENS,
        _mesh_diagonal(coordinates),
    )
    write_weights(obj, report["weights"])
    return report

def skinning_message(report):
    """Muscle skinning summary line, in English and unambiguous."""
    return (
        "FlexForge - skinning: vertices=%d vertices_bound=%d muscles_bound=%d"
        % (report["vertices"], report["vertices_bound"], report["muscles_bound"])
    )

class FLEXFORGE_OT_bind_muscles(bpy.types.Operator):
    """Skin the active mesh on the muscle helper capsules."""

    bl_idname = "flexforge.bind_muscles"
    bl_label = "Bind muscles"
    bl_description = (
        "Bind the deforming muscle_* helper bones to the active mesh with a "
        "volumetric capsule falloff and print the report to the console"
    )
    bl_options = {"REGISTER", "UNDO"}

    radius: bpy.props.FloatProperty(name="Radius", default=DEFAULT_RADIUS,
                                    min=0.001, max=10.0)
    intensity: bpy.props.FloatProperty(name="Intensity", default=DEFAULT_INTENSITY,
                                       min=0.0, max=1.0)
    max_influences: bpy.props.IntProperty(name="Max influences",
                                          default=MAX_INFLUENCES_DEFAULT,
                                          min=MAX_INFLUENCES_MIN, max=8)

    def execute(self, context):
        obj = context.view_layer.objects.active
        if obj is None or obj.type != "MESH":
            self.report(
                {"ERROR"},
                "An active mesh is required: select the object and try again.",
            )
            return {"CANCELLED"}

        radius = getattr(self, "radius", DEFAULT_RADIUS)
        if not isinstance(radius, (int, float)) or radius <= 0.0:
            radius = DEFAULT_RADIUS
        intensity = getattr(self, "intensity", DEFAULT_INTENSITY)
        if not isinstance(intensity, (int, float)) or intensity < 0.0:
            intensity = DEFAULT_INTENSITY
        max_influences = getattr(self, "max_influences", None)
        if not isinstance(max_influences, int) or max_influences < MAX_INFLUENCES_MIN:
            max_influences = MAX_INFLUENCES_DEFAULT

        try:
            report = apply_muscle_skinning(
                obj, radius=radius, intensity=intensity,
                max_influences=max_influences,
            )
        except (SkinningError, WeightsError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        message = skinning_message(report)
        print(message)
        self.report({"INFO"}, message)
        return {"FINISHED"}
