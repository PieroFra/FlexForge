# Deterministic headless test of the FlexForge muscle cleanup.
# Runs inside Blender: it builds real meshes and armatures, then checks the
# removal of the flexforge_* shape keys, of the muscle_* groups and bones.

import sys
import traceback
import types
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import bpy  # noqa: E402

from flexforge import muscle_clear  # noqa: E402


def _make_mesh(name):
    """A two-vertex mesh object linked to the scene, active and selected."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], [], [(0, 1)])
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    for other in bpy.context.view_layer.objects:
        other.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    return obj, mesh


def test_clear_shape_keys_driver_and_basis():
    obj, mesh = _make_mesh("flexforge_clear_keys")
    try:
        obj.shape_key_add(name="Basis", from_mix=False)
        key = obj.shape_key_add(name="flexforge_biceps", from_mix=False)
        obj.shape_key_add(name="jaw", from_mix=False)
        key.driver_add("value")
        assert len(obj.data.shape_keys.key_blocks) == 3

        report = muscle_clear.clear_flexforge_data(obj)
        assert report["shape_keys"] == 1, report
        names = [block.name for block in obj.data.shape_keys.key_blocks]
        assert names == ["Basis", "jaw"], names
        drivers = getattr(obj.data.shape_keys.animation_data, "drivers", [])
        assert len(drivers) == 0, [driver.data_path for driver in drivers]

        # Without another key the leftover Basis goes away as well.
        obj.shape_key_clear()
        obj.shape_key_add(name="Basis", from_mix=False)
        obj.shape_key_add(name="flexforge_triceps", from_mix=False)
        report = muscle_clear.clear_flexforge_data(obj)
        assert report["shape_keys"] == 1, report
        remaining = obj.data.shape_keys
        assert remaining is None or len(remaining.key_blocks) == 0, remaining
    finally:
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(mesh)


def test_clear_muscle_vertex_groups():
    obj, mesh = _make_mesh("flexforge_clear_groups")
    try:
        obj.vertex_groups.new(name="muscle_biceps")
        obj.vertex_groups.new(name="muscle_triceps")
        obj.vertex_groups.new(name="biceps")
        report = muscle_clear.clear_flexforge_data(obj)
        assert report["groups"] == 2, report
        assert report["bones"] == 0, report
        names = [group.name for group in obj.vertex_groups]
        assert names == ["biceps"], names
    finally:
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(mesh)


def test_clear_muscle_bones_from_active_mesh():
    obj, mesh = _make_mesh("flexforge_clear_bones")
    rig_data = bpy.data.armatures.new("flexforge_clear_rig")
    rig = bpy.data.objects.new("flexforge_clear_rig", rig_data)
    bpy.context.scene.collection.objects.link(rig)
    try:
        bpy.context.view_layer.objects.active = rig
        rig.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        for bone_name in ("spine", "muscle_biceps", "muscle_triceps"):
            bone = rig_data.edit_bones.new(bone_name)
            bone.head = (0.0, 0.0, 0.0)
            bone.tail = (0.0, 0.0, 1.0)
        bpy.ops.object.mode_set(mode="OBJECT")
        modifier = obj.modifiers.new(name="Armature", type="ARMATURE")
        modifier.object = rig
        obj.vertex_groups.new(name="muscle_biceps")

        bpy.context.view_layer.objects.active = obj
        report = muscle_clear.clear_flexforge_data(obj)
        assert report == {"bones": 2, "groups": 1, "shape_keys": 0}, report
        names = [bone.name for bone in rig_data.bones]
        assert names == ["spine"], names
        assert bpy.context.view_layer.objects.active is obj
        assert obj.mode == "OBJECT", obj.mode
    finally:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.objects.remove(rig, do_unlink=True)
        bpy.data.meshes.remove(mesh)
        bpy.data.armatures.remove(rig_data)


def test_clear_requires_active_object():
    cls = muscle_clear.FLEXFORGE_OT_clear_muscles
    assert cls.bl_idname == "flexforge.clear_muscles", cls.bl_idname
    assert cls.bl_label == "Clear muscles", cls.bl_label
    assert "REGISTER" in cls.bl_options, cls.bl_options
    assert "UNDO" in cls.bl_options, cls.bl_options

    for other in bpy.context.view_layer.objects:
        other.select_set(False)
    bpy.context.view_layer.objects.active = None
    bpy.utils.register_class(cls)
    try:
        try:
            outcome = bpy.ops.flexforge.clear_muscles()
        except RuntimeError:
            outcome = {"CANCELLED"}
    finally:
        bpy.utils.unregister_class(cls)
    assert outcome == {"CANCELLED"}, outcome

    try:
        muscle_clear.clear_flexforge_data(types.SimpleNamespace(type="CAMERA"))
    except muscle_clear.ClearError:
        pass
    else:
        raise AssertionError("a camera object must raise ClearError")


def _main():
    tests = [
        test_clear_shape_keys_driver_and_basis,
        test_clear_muscle_vertex_groups,
        test_clear_muscle_bones_from_active_mesh,
        test_clear_requires_active_object,
    ]

    passed = 0
    failed = 0
    for case in tests:
        try:
            case()
        except Exception:
            failed += 1
            traceback.print_exc()
        else:
            passed += 1

    total = passed + failed
    print("RISULTATO passati=%d falliti=%d totale=%d" % (passed, failed, total))
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(_main())
