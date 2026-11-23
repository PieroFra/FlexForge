# Deterministic headless test of the FlexForge rig detection helper.
# Pure functions on bone name lists, no bpy objects needed beyond the
# package import, so they run identically inside and outside Blender.

import sys
import traceback
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


_install_bpy_stub()

from flexforge import rig_detect  # noqa: E402


def test_detect_standard():
    bones = [
        "upper_arm.L", "upper_arm.R", "forearm.L", "forearm.R",
        "shoulder.L", "shoulder.R", "thigh.L", "thigh.R",
        "shin.L", "shin.R", "foot.L", "foot.R",
        "spine", "spine.001", "spine.002",
    ]
    report = rig_detect.detect_rig(bones)
    assert report["rig_type"] == "standard", report
    assert report["coverage"] == 1.0, report
    assert report["preset_ids"] == [
        "biceps", "triceps", "deltoid", "pectoral",
        "latissimus", "quadriceps", "hamstring", "calf", "gluteus",
    ], report


def test_detect_mixamo():
    bones = [
        "mixamorig:Hips", "mixamorig:LeftArm", "mixamorig:RightArm",
        "mixamorig:LeftForeArm", "mixamorig:RightForeArm",
        "mixamorig:LeftShoulder", "mixamorig:RightShoulder",
        "mixamorig:LeftUpLeg", "mixamorig:RightUpLeg",
        "mixamorig:LeftLeg", "mixamorig:RightLeg",
        "mixamorig:LeftFoot", "mixamorig:RightFoot",
        "mixamorig:Spine", "mixamorig:Spine1", "mixamorig:Spine2",
    ]
    report = rig_detect.detect_rig(bones)
    assert report["rig_type"] == "mixamo", report
    assert report["coverage"] == 1.0, report
    assert "biceps" in report["preset_ids"], report
    assert "pectoral" in report["preset_ids"], report


def test_detect_bip01():
    bones = [
        "Bip01 L UpperArm", "Bip01 R UpperArm",
        "Bip01 L Forearm", "Bip01 R Forearm",
        "Bip01 L Clavicle", "Bip01 R Clavicle",
        "Bip01 L Thigh", "Bip01 R Thigh",
        "Bip01 L Calf", "Bip01 R Calf",
        "Bip01 L Foot", "Bip01 R Foot",
        "Bip01 Spine", "Bip01 Pelvis", "Bip01 Spine1", "Bip01 Spine2",
    ]
    report = rig_detect.detect_rig(bones)
    assert report["rig_type"] == "bip01", report
    assert report["coverage"] == 1.0, report
    assert "gluteus" in report["preset_ids"], report


def test_detect_unknown():
    report = rig_detect.detect_rig(["totally_unknown", "another_one"])
    assert report["rig_type"] == "unknown", report
    assert report["coverage"] == 0.0, report
    assert report["preset_ids"] == [], report
    assert report["missing"] != 0, report


def test_detect_partial():
    bones = ["upper_arm.L", "forearm.L"]  # only biceps sides
    report = rig_detect.detect_rig(bones)
    assert report["rig_type"] == "standard", report
    assert report["coverage"] < 1.0, report
    assert "biceps" in report["preset_ids"], report
    assert "quadriceps" not in report["preset_ids"], report
    # full report message is readable
    message = rig_detect.detect_message(report)
    assert "biceps" in message, message
    assert "coverage" in message, message


def test_resolved_bones_for_preset():
    bones = ["mixamorig:LeftArm", "mixamorig:RightArm", "mixamorig:LeftForeArm"]
    resolved = rig_detect.resolved_bones_for_preset("biceps", bones, mirror_lr=True)
    assert resolved["origin"] == "mixamorig:LeftArm", resolved
    assert resolved["insertion"] == "mixamorig:LeftForeArm", resolved
    # mirrored counterparts resolved too
    assert resolved["origin_r"] == "mixamorig:RightArm", resolved

    single = rig_detect.resolved_bones_for_preset("biceps", bones, mirror_lr=False)
    assert single["origin"] == "mixamorig:LeftArm", single
    assert "origin_r" not in single, single


def test_invalid_preset_error():
    error = None
    try:
        rig_detect.resolved_bones_for_preset("nope", ["a", "b"])
    except rig_detect.RigDetectError as exception:
        error = exception
    assert error is not None, "expected RigDetectError with unknown preset"


def _main():
    tests = [
        test_detect_standard,
        test_detect_mixamo,
        test_detect_bip01,
        test_detect_unknown,
        test_detect_partial,
        test_resolved_bones_for_preset,
        test_invalid_preset_error,
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
