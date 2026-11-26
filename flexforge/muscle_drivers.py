# FlexForge - pose drivers for the baked corrective shape keys.
# Kept apart from muscle_bake so the bake module stays short; the math is a
# ROTATION_DIFF between the parent (`origin`) and the `STRETCH_TO` subtarget.
# APIs used are present on Blender 4.2 and 5.3.

from .muscle import MUSCLE_PREFIX
from .muscle_anatomy import ANATOMY_DIRECTIONS, _normalize, muscle_family_from_bone
from .muscle_shape import SHAPE_KEY_PREFIX, BakeError, shape_key_name_for_bone

STRETCH_TO_CONSTRAINT = "STRETCH_TO"
DEFAULT_MAX_ANGLE_RAD = 1.5708
DEFAULT_BULGE_SCALE = 1.0
MAX_BULGE_SCALE = 3.0
_ROT_AXES = ("ROT_X", "ROT_Y", "ROT_Z")


def scale_prop_name(key_name):
    """Custom property on the mesh object holding the bulge scale of a key."""
    return "%s_scale" % key_name


def contraction_axis_for_muscle(key_name, insertion_bone):
    """Return the insertion rotation axis and sign for directional contraction."""
    family = muscle_family_from_bone(str(key_name or "").replace(".", "_"))
    if family not in ANATOMY_DIRECTIONS or insertion_bone is None:
        return None
    head = getattr(insertion_bone, "head_local", None)
    tail = getattr(insertion_bone, "tail_local", None)
    if head is None or tail is None:
        return None
    bone_dir = _normalize((
        tail[0] - head[0], tail[1] - head[1], tail[2] - head[2],
    ))
    if bone_dir is None:
        return None
    anatomy = ANATOMY_DIRECTIONS[family]
    hinge = _normalize((
        bone_dir[1] * anatomy[2] - bone_dir[2] * anatomy[1],
        bone_dir[2] * anatomy[0] - bone_dir[0] * anatomy[2],
        bone_dir[0] * anatomy[1] - bone_dir[1] * anatomy[0],
    ))
    if hinge is None:
        return None
    matrix = getattr(insertion_bone, "matrix_local", None)
    try:
        axes = [
            _normalize((matrix[0][i], matrix[1][i], matrix[2][i]))
            for i in range(3)
        ]
    except (TypeError, IndexError, KeyError):
        axes = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    if any(axis is None for axis in axes):
        return None
    best_index = 0
    best_dot = 0.0
    for index, axis in enumerate(axes):
        dot = axis[0] * hinge[0] + axis[1] * hinge[1] + axis[2] * hinge[2]
        if abs(dot) > abs(best_dot):
            best_dot = dot
            best_index = index
    if abs(best_dot) <= 1e-5:
        return None
    return _ROT_AXES[best_index], (1.0 if best_dot > 0.0 else -1.0)

def _driver_bone_pair(armature, bones, key_name):
    """(origin, insertion) bone names driving a shape key, or (None, None)."""
    pose_bones = getattr(getattr(armature, "pose", None), "bones", None) or []
    for bone in bones:
        bone_name = getattr(bone, "name", "")
        origin = getattr(getattr(bone, "parent", None), "name", None)
        if (not origin or not str(bone_name).startswith(MUSCLE_PREFIX)
                or shape_key_name_for_bone(bone_name) != key_name):
            continue
        for pose_bone in pose_bones:
            if getattr(pose_bone, "name", None) != bone_name:
                continue
            for constraint in getattr(pose_bone, "constraints", None) or []:
                insertion = getattr(constraint, "subtarget", "")
                if (getattr(constraint, "type", None) == STRETCH_TO_CONSTRAINT
                        and insertion != origin):
                    return origin, insertion
    return None, None

def attach_pose_drivers(obj, armature, max_angle_rad=DEFAULT_MAX_ANGLE_RAD):
    """Drive each `flexforge_*` key from the angle of its muscle bone.

    Needs a parent (`origin`) and a `STRETCH_TO` subtarget (`insertion`).
    `max_angle_rad` is the angle that saturates the driver and must be positive.
    """
    if max_angle_rad <= 0.0:
        raise BakeError("max_angle_rad must be positive.")
    bones = getattr(getattr(armature, "data", None), "bones", None) or []
    by_name = {getattr(bone, "name", ""): bone for bone in bones}
    shape_keys = getattr(getattr(obj, "data", None), "shape_keys", None)
    key_blocks = getattr(shape_keys, "key_blocks", None) or []
    created = 0
    for key_block in key_blocks:
        key_name = getattr(key_block, "name", "")
        if not str(key_name).startswith(SHAPE_KEY_PREFIX):
            continue
        origin, insertion = _driver_bone_pair(armature, bones, key_name)
        if origin not in by_name or insertion not in by_name:
            continue
        ins_bone = by_name[insertion]
        contraction_axis = contraction_axis_for_muscle(key_name, ins_bone)
        # The slider ceiling must leave room for the user-editable scale. Shape
        # keys cannot hold ID properties, so the scale lives on the mesh object.
        key_block.slider_max = max(float(getattr(key_block, "slider_max", 1.0)),
                                   MAX_BULGE_SCALE)
        prop_name = scale_prop_name(key_name)
        obj[prop_name] = float(obj.get(prop_name, DEFAULT_BULGE_SCALE))
        try:
            obj.id_properties_ui(prop_name).update(
                min=0.0, max=MAX_BULGE_SCALE, soft_min=0.0, soft_max=2.0)
        except AttributeError:
            pass
        key_block.driver_remove("value")
        driver = key_block.driver_add("value").driver
        driver.type = "SCRIPTED"
        variable = driver.variables.new()
        variable.name = "ang"
        if contraction_axis is not None:
            rot_axis, sign = contraction_axis
            variable.type = "TRANSFORMS"
            variable.targets[0].id = armature
            variable.targets[0].bone_target = insertion
            variable.targets[0].transform_type = rot_axis
            variable.targets[0].transform_space = "LOCAL_SPACE"
            expr = "min(1.0, max(0.0, %sang / %.6f)) * scale" % (
                "" if sign > 0 else "-", max_angle_rad)
        else:
            rest_angle = by_name[origin].matrix_local.to_quaternion().rotation_difference(
                ins_bone.matrix_local.to_quaternion()).angle
            variable.type = "ROTATION_DIFF"
            variable.targets[0].id = armature
            variable.targets[0].bone_target = origin
            variable.targets[1].id = armature
            variable.targets[1].bone_target = insertion
            expr = ("min(1.0, max(0.0, abs(ang - %.6f) / %.6f)) * scale"
                    % (rest_angle, max_angle_rad))
        scale_var = driver.variables.new()
        scale_var.name = "scale"
        scale_var.type = "SINGLE_PROP"
        scale_var.targets[0].id_type = "OBJECT"
        scale_var.targets[0].id = obj
        scale_var.targets[0].data_path = '["%s"]' % prop_name
        driver.expression = expr
        created += 1
    return created
