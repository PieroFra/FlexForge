# FlexForge - pose drivers for the baked corrective shape keys.
# Kept apart from muscle_bake so the bake module stays short; the math is a
# ROTATION_DIFF between the parent (`origin`) and the `STRETCH_TO` subtarget.
# APIs used are present on Blender 4.2 and 5.3.

from .muscle import MUSCLE_PREFIX
from .muscle_shape import SHAPE_KEY_PREFIX, BakeError, shape_key_name_for_bone

STRETCH_TO_CONSTRAINT = "STRETCH_TO"
DEFAULT_MAX_ANGLE_RAD = 1.5708
DEFAULT_BULGE_SCALE = 1.0
MAX_BULGE_SCALE = 3.0


def scale_prop_name(key_name):
    """Custom property on the mesh object holding the bulge scale of a key."""
    return "%s_scale" % key_name

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
        rest_angle = by_name[origin].matrix_local.to_quaternion().rotation_difference(by_name[insertion].matrix_local.to_quaternion()).angle
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
        variable.type = "ROTATION_DIFF"
        variable.targets[0].id = armature
        variable.targets[0].bone_target = origin
        variable.targets[1].id = armature
        variable.targets[1].bone_target = insertion
        scale_var = driver.variables.new()
        scale_var.name = "scale"
        scale_var.type = "SINGLE_PROP"
        scale_var.targets[0].id_type = "OBJECT"
        scale_var.targets[0].id = obj
        scale_var.targets[0].data_path = '["%s"]' % prop_name
        driver.expression = ("min(1.0, max(0.0, abs(ang - %.6f) / %.6f)) * scale"
                             % (rest_angle, max_angle_rad))
        created += 1
    return created
