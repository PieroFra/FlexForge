# FlexForge - bake muscle weights into corrective shape keys.
# The pure delta math lives in muscle_shape and is re-exported here, so
# `muscle_bake.compute_muscle_shape_deltas` keeps working; this module owns the
# Blender pass that creates `Basis` + corrective keys and the operator.
# APIs used are present on Blender 4.2 and 5.3.

import bpy

from .armatura import armature_of_mesh
from .muscle import MUSCLE_PREFIX
from .muscle_anatomy import smooth_shape_deltas
from .muscle_skinning import _armature_to_mesh_matrix, _matrix_point
from .muscle_drivers import (attach_pose_drivers, contraction_axis_for_muscle,
                             DEFAULT_MAX_ANGLE_RAD, STRETCH_TO_CONSTRAINT,
                             _driver_bone_pair)
from .muscle_shape import (BakeError, DEFAULT_BONE_RADIUS, DEFAULT_DISPLACEMENT,
                           MAX_DISPLACEMENT_RATIO, SHAPE_KEY_PREFIX, bone_radius,
                           compute_muscle_shape_deltas, shape_key_name_for_bone)
from .weights import (EPS, MAX_INFLUENCES_DEFAULT, limit_influences, read_weights, write_weights)

BASIS_KEY_NAME = "Basis"

def _non_muscle_ancestor(name, bone_parents):
    """First non-`muscle_*` parent of a helper bone, or None."""
    seen = set()
    current = bone_parents.get(name)
    while current is not None and str(current) not in seen:
        if not str(current).startswith(MUSCLE_PREFIX):
            return current
        seen.add(str(current))
        current = bone_parents.get(current)
    return None

def collapse_muscle_weights_to_parent(weights, bone_parents,
                                      max_influences=MAX_INFLUENCES_DEFAULT):
    """Strip `muscle_*` weights, falling back to the ancestor only when no skeletal weight exists."""
    collapsed = {}
    for vertex, groups in weights.items():
        skeletal = {}
        muscles = {}
        for name, weight in groups.items():
            if abs(weight) <= EPS:
                continue
            if str(name).startswith(MUSCLE_PREFIX):
                muscles[name] = muscles.get(name, 0.0) + weight
            else:
                skeletal[name] = skeletal.get(name, 0.0) + weight
        if skeletal:
            collapsed[vertex] = skeletal
            continue
        merged = {}
        for name, weight in muscles.items():
            target = _non_muscle_ancestor(name, bone_parents)
            if target is not None:
                merged[target] = merged.get(target, 0.0) + weight
        collapsed[vertex] = merged
    return limit_influences(collapsed, max_influences)

def _muscle_segments_of_armature(armature, obj=None):
    """Return ({bone: (head, tail)}, {bone: parent_name}, {bone: radius}).

    With `obj` the head/tail and the envelope are moved into the mesh space, so
    a rig scaled to centimetres and turned 90 degrees still maps its capsules.
    """
    segments = {}
    bone_parents = {}
    radii = {}
    matrix, scale = _armature_to_mesh_matrix(obj, armature)
    bones = getattr(getattr(armature, "data", None), "bones", None) or []
    for bone in bones:
        name = getattr(bone, "name", "")
        parent = getattr(bone, "parent", None)
        bone_parents[name] = getattr(parent, "name", None)
        if not str(name).startswith(MUSCLE_PREFIX):
            continue
        head = getattr(bone, "head_local", None) or getattr(bone, "head", None)
        tail = getattr(bone, "tail_local", None) or getattr(bone, "tail", None)
        if head is None or tail is None:
            raise BakeError("Bone '%s' has no rest head/tail." % name)
        if matrix is not None:
            head, tail = _matrix_point(matrix, head), _matrix_point(matrix, tail)
        segments[name] = (tuple(head), tuple(tail))
        # A tiny FBX envelope (e.g. 1 mm after transform_apply) would squash the
        # bulge cap to nothing: under the default radius the segment length is
        # a firmer floor, standard bones keep their own envelope untouched.
        radius = bone_radius(bone) * scale
        if radius < DEFAULT_BONE_RADIUS:
            span = sum((tuple(tail)[i] - tuple(head)[i]) ** 2
                       for i in range(3)) ** 0.5
            radius = max(radius, 0.25 * span)
        radii[name] = radius
    return segments, bone_parents, radii

def apply_one_hot_values(created_keys):
    """Zero every baked key but the active one: one muscle at a time.

    Blender makes the last key active: it gets 1.0, the others stay at 0.0.
    """
    if not created_keys:
        return 0
    for key in created_keys:
        key.value = 0.0
    created_keys[-1].value = 1.0
    return len(created_keys)

def apply_muscle_bake(obj, armature=None, displacement=DEFAULT_DISPLACEMENT,
                      strip_muscle_weights=True,
                      max_influences=MAX_INFLUENCES_DEFAULT,
                      max_displacement_ratio=MAX_DISPLACEMENT_RATIO,
                      drive_by_pose=False,
                      anatomical_taper=False,
                      directional_bias=False,
                      smooth_iterations=0):
    """Create `Basis` + one corrective key per muscle on the active mesh.

    The segments of a muscle share its key, which is one-hot: 1.0 on the last
    baked muscle, 0.0 on the others. With `strip_muscle_weights` the helper
    weights go on the parent bone and the `muscle_*` groups are removed.
    `max_displacement_ratio` is the share of the bone envelope the push may
    reach. With `drive_by_pose` every corrective key also gets a pose driver.
    With `anatomical_taper` the push follows a fusiform curve, zero at the
    tendons and one at the belly of the muscle. With `directional_bias` the push
    follows the anatomical side of the muscle family, and with
    `smooth_iterations` above zero the deltas are Laplacian-smoothed over the
    mesh edges before the keys are created.
    Return {shape_keys, vertices_displaced, stripped_muscles, drivers_added}.
    """
    if getattr(obj, "type", None) != "MESH":
        raise BakeError("The active object is not a mesh.")
    if armature is None:
        armature = armature_of_mesh(obj)
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        raise BakeError("An armature is required: add an Armature modifier or pass one.")
    segments, bone_parents, radii = _muscle_segments_of_armature(armature, obj)
    if not segments:
        raise BakeError("No 'muscle_' bones found in the armature.")
    weights = read_weights(obj)
    coordinates = {vertex.index: (vertex.co[0], vertex.co[1], vertex.co[2])
                   for vertex in obj.data.vertices}
    deltas = compute_muscle_shape_deltas(coordinates, weights, segments,
                                         displacement, radii,
                                         max_displacement_ratio,
                                         anatomical_taper=anatomical_taper,
                                         directional_bias=directional_bias)
    shape_keys = getattr(obj.data, "shape_keys", None)
    if shape_keys is None or BASIS_KEY_NAME not in getattr(
            shape_keys, "key_blocks", {}):
        obj.shape_key_add(name=BASIS_KEY_NAME, from_mix=False)
    shapes = {}
    for bone_name in sorted(deltas):
        bucket = shapes.setdefault(shape_key_name_for_bone(bone_name), {})
        for vertex, delta in deltas[bone_name].items():
            accumulated = bucket.get(vertex, (0.0, 0.0, 0.0))
            bucket[vertex] = tuple(accumulated[i] + delta[i] for i in range(3))
    if smooth_iterations > 0:
        edges = [(edge.vertices[0], edge.vertices[1])
                 for edge in getattr(obj.data, "edges", [])]
        for key_name in shapes:
            shapes[key_name] = smooth_shape_deltas(shapes[key_name], edges,
                                                   iterations=smooth_iterations)
    displaced = set()
    created = []
    for key_name in sorted(shapes):
        key_blocks = getattr(getattr(obj.data, "shape_keys", None), "key_blocks", None)
        if key_blocks and key_name in key_blocks:
            existing = key_blocks[key_name]
            try:
                existing.driver_remove("value")
            except Exception:
                pass
            obj.shape_key_remove(existing)
        key = obj.shape_key_add(name=key_name, from_mix=False)
        created.append(key)
        for vertex, delta in shapes[key_name].items():
            base = coordinates[vertex]
            key.data[vertex].co = tuple(base[i] + delta[i] for i in range(3))
            displaced.add(vertex)
    apply_one_hot_values(created)
    drivers_added = 0
    if drive_by_pose:
        drivers_added = attach_pose_drivers(obj, armature)
    stripped = 0
    if strip_muscle_weights:
        collapsed = collapse_muscle_weights_to_parent(weights, bone_parents,
                                                      max_influences)
        write_weights(obj, collapsed)
        for group in list(obj.vertex_groups):
            if str(group.name).startswith(MUSCLE_PREFIX):
                obj.vertex_groups.remove(group)
                stripped += 1
    return {"shape_keys": len(created), "vertices_displaced": len(displaced),
            "stripped_muscles": stripped, "drivers_added": drivers_added}

def bake_message(report):
    """Bake summary line, in English and unambiguous."""
    return ("FlexForge - bake: shape_keys=%d vertices_displaced=%d stripped_muscles=%d"
            % (report["shape_keys"], report["vertices_displaced"], report["stripped_muscles"]))

class FLEXFORGE_OT_bake_shape_keys(bpy.types.Operator):
    """Bake the muscle helpers into corrective shape keys."""

    bl_idname = "flexforge.bake_shape_keys"
    bl_label = "Bake shape keys"
    bl_description = ("Create Basis + corrective shape keys from the muscle_* bones and optionally move their weights to the parent bone")
    bl_options = {"REGISTER", "UNDO"}

    displacement: bpy.props.FloatProperty(name="Displacement", default=DEFAULT_DISPLACEMENT, min=0.001, max=5.0)
    strip_muscle_weights: bpy.props.BoolProperty(name="Strip muscle weights", default=True)
    max_influences: bpy.props.IntProperty(name="Max influences", default=MAX_INFLUENCES_DEFAULT, min=1, max=8)
    max_displacement_ratio: bpy.props.FloatProperty(name="Max displacement ratio", default=MAX_DISPLACEMENT_RATIO, min=0.01, max=1.0)
    drive_by_pose: bpy.props.BoolProperty(name="Drive by pose", default=False)
    anatomical_taper: bpy.props.BoolProperty(name="Anatomical taper", default=False)
    directional_bias: bpy.props.BoolProperty(name="Directional bias", default=False)
    smooth_iterations: bpy.props.IntProperty(name="Smooth iterations", default=0, min=0, max=5)

    def execute(self, context):
        obj = context.view_layer.objects.active
        if obj is None or obj.type != "MESH":
            self.report({"ERROR"}, "An active mesh is required: select the object and try again.")
            return {"CANCELLED"}
        displacement = getattr(self, "displacement", DEFAULT_DISPLACEMENT)
        if not isinstance(displacement, (int, float)) or displacement <= 0.0:
            displacement = DEFAULT_DISPLACEMENT
        max_influences = getattr(self, "max_influences", MAX_INFLUENCES_DEFAULT)
        if not isinstance(max_influences, int) or max_influences < 1:
            max_influences = MAX_INFLUENCES_DEFAULT
        strip = bool(getattr(self, "strip_muscle_weights", True))
        max_displacement_ratio = getattr(self, "max_displacement_ratio",
                                         MAX_DISPLACEMENT_RATIO)
        if (not isinstance(max_displacement_ratio, (int, float))
                or max_displacement_ratio <= 0.0):
            max_displacement_ratio = MAX_DISPLACEMENT_RATIO
        try:
            report = apply_muscle_bake(obj, displacement=displacement,
                                       strip_muscle_weights=strip,
                                       max_influences=max_influences,
                                       max_displacement_ratio=max_displacement_ratio,
                                       drive_by_pose=bool(getattr(self, "drive_by_pose", False)),
                                       anatomical_taper=bool(getattr(self, "anatomical_taper", False)),
                                       directional_bias=bool(getattr(self, "directional_bias", False)),
                                       smooth_iterations=int(getattr(self, "smooth_iterations", 0)))
        except BakeError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        message = bake_message(report)
        print(message)
        self.report({"INFO"}, message)
        return {"FINISHED"}
