# Headless test of the FlexForge full-body operator.
# Real bpy when available, otherwise the shared stub; the operator execution
# is skipped on the stub, which has no real operator stack or armature modes.
import importlib.util
import sys
import traceback
import types
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def _install_bpy_stub():
    """Install the shared bpy stub only if the real module is missing."""
    try:
        import bpy  # noqa: F401
        return False
    except ImportError:
        pass
    stub_folder = "/tmp/flexforge_test"
    if stub_folder not in sys.path:
        sys.path.insert(0, stub_folder)
    from flexforge_stub import installa_stub_bpy as install_bpy_stub
    return install_bpy_stub(props_default=True, con_ops=True)


_FAKE = _install_bpy_stub()

from flexforge import muscle_fullbody, rig_detect  # noqa: E402


FAKE_REPORT = {
    "preset_ids": [],
    "rig_type": "unknown",
    "coverage": 0.0,
    "matched": 0,
    "missing": 0,
    "topology_ok": None,
    "topology_checked": 0,
    "topology_bad": [],
    "matched_bones": {},
}


def _mixamo_data():
    """The Mixamo names/parents of the rig detect suite, reused when possible."""
    path = BASE / "tests" / "test_rig_detect.py"
    try:
        spec = importlib.util.spec_from_file_location("test_rig_detect_suite", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module._MIXAMO_NAMES, module._MIXAMO_PARENTS
    except Exception:
        names = [
            "mixamorig:Hips", "mixamorig:LeftArm", "mixamorig:RightArm",
            "mixamorig:LeftForeArm", "mixamorig:RightForeArm",
            "mixamorig:LeftShoulder", "mixamorig:RightShoulder",
            "mixamorig:LeftUpLeg", "mixamorig:RightUpLeg",
            "mixamorig:LeftLeg", "mixamorig:RightLeg",
            "mixamorig:LeftFoot", "mixamorig:RightFoot",
            "mixamorig:Spine", "mixamorig:Spine1", "mixamorig:Spine2",
        ]
        parents = {
            "mixamorig:Hips": "",
            "mixamorig:Spine": "mixamorig:Hips",
            "mixamorig:Spine1": "mixamorig:Spine",
            "mixamorig:Spine2": "mixamorig:Spine1",
            "mixamorig:LeftShoulder": "mixamorig:Spine1",
            "mixamorig:RightShoulder": "mixamorig:Spine1",
            "mixamorig:LeftArm": "mixamorig:LeftShoulder",
            "mixamorig:RightArm": "mixamorig:RightShoulder",
            "mixamorig:LeftForeArm": "mixamorig:LeftArm",
            "mixamorig:RightForeArm": "mixamorig:RightArm",
            "mixamorig:LeftUpLeg": "mixamorig:Hips",
            "mixamorig:RightUpLeg": "mixamorig:Hips",
            "mixamorig:LeftLeg": "mixamorig:LeftUpLeg",
            "mixamorig:RightLeg": "mixamorig:RightUpLeg",
            "mixamorig:LeftFoot": "mixamorig:LeftLeg",
            "mixamorig:RightFoot": "mixamorig:RightLeg",
        }
        return names, parents


def test_operator_definition():
    cls = muscle_fullbody.FLEXFORGE_OT_apply_full_body
    assert cls.bl_idname == "flexforge.apply_full_body", cls.bl_idname
    assert cls.bl_label == "Create full body", cls.bl_label
    assert "mirror_lr" in cls.__annotations__, cls.__annotations__


def test_apply_full_body_no_presets():
    from flexforge.rig_detect import apply_full_body

    mesh = types.SimpleNamespace(
        type="MESH", modifiers=(), parent=None, data=types.SimpleNamespace()
    )
    report = apply_full_body(mesh, dict(FAKE_REPORT), mirror_lr=True)
    assert report["created"] == [], report
    assert "no presets available" in report["message"], report["message"]

    armature = types.SimpleNamespace(
        type="ARMATURE", data=types.SimpleNamespace(bones=[])
    )
    report = apply_full_body(
        armature, dict(FAKE_REPORT), armature=armature, mirror_lr=False
    )
    assert report["created"] == [], report
    assert "no presets available" in report["message"], report["message"]


def test_detect_rig_mixamo_nine_presets():
    names, parents = _mixamo_data()
    report = rig_detect.detect_rig(names, parents)
    assert report["rig_type"] == "mixamo", report
    assert report["topology_ok"] is True, report
    assert len(report["preset_ids"]) == 9, report
    assert report["preset_ids"] == [
        "biceps", "triceps", "deltoid", "pectoral",
        "latissimus", "quadriceps", "hamstring", "calf", "gluteus",
    ], report["preset_ids"]


def test_operator_registered():
    import bpy

    assert hasattr(bpy.ops.flexforge, "apply_full_body"), (
        "operator not exposed in bpy.ops.flexforge"
    )


def _make_mixamo_armature(parents):
    """Create a real Mixamo rig in Object Mode, ready for the operator."""
    import bpy

    rig_data = bpy.data.armatures.new("FlexForgeFullBodyRig")
    rig = bpy.data.objects.new("FlexForgeFullBodyRig", rig_data)
    bpy.context.scene.collection.objects.link(rig)
    for other in bpy.context.view_layer.objects:
        other.select_set(False)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="EDIT")
    for name, parent_name in parents.items():
        parent = rig_data.edit_bones.get(parent_name) if parent_name else None
        bone = rig_data.edit_bones.new(name)
        bone.parent = parent
        bone.head = (0.0, 0.0, 0.0)
        bone.tail = (0.0, 0.0, 1.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def test_operator_execute():
    import bpy

    if _FAKE:
        # The stub has no real operator stack nor armature mode switch.
        return
    parents = _mixamo_data()[1]
    rig = _make_mixamo_armature(parents)
    rig_data = rig.data
    bpy.utils.register_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
    try:
        result = bpy.ops.flexforge.apply_full_body(mirror_lr=True)
        assert result == {"FINISHED"}, result
        assert rig.mode == "OBJECT", rig.mode
        assert bpy.context.view_layer.objects.active == rig
        assert rig.select_get()
        for name in (
            "muscle_biceps_01", "muscle_biceps_r_01",
            "muscle_gluteus_01", "muscle_gluteus_r_01",
        ):
            assert rig.data.bones.get(name) is not None, name
    finally:
        bpy.utils.unregister_class(
            muscle_fullbody.FLEXFORGE_OT_apply_full_body
        )
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.data.objects.remove(rig, do_unlink=True)
        if rig_data.users == 0:
            bpy.data.armatures.remove(rig_data)


def test_full_body_message_counts_created():
    report = {
        "rig_type": "standard",
        "coverage": 1.0,
        "matched": 9,
        "missing": 0,
        "preset_ids": ["biceps", "triceps"],
        "topology_ok": None,
        "topology_checked": 0,
        "topology_bad": [],
        "matched_bones": {},
    }
    message = muscle_fullbody.full_body_message(report, 4, ["biceps", "triceps"])
    assert message.startswith("FlexForge - rig: type=standard"), message
    assert "created 4 bones on 2 presets" in message, message
    empty = muscle_fullbody.full_body_message(report, 0, [])
    assert "created" not in empty, empty


def _main():
    tests = [
        test_operator_definition,
        test_apply_full_body_no_presets,
        test_detect_rig_mixamo_nine_presets,
        test_full_body_message_counts_created,
        test_operator_registered,
        test_operator_execute,
    ]
    passed = failed = 0
    for case in tests:
        try:
            case()
        except Exception:
            failed += 1
            traceback.print_exc()
        else:
            passed += 1
    print("RISULTATO passati=%d falliti=%d totale=%d" % (passed, failed, passed + failed))
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(_main())