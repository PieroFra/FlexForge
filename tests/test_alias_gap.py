# Deterministic headless test of the FlexForge rig detection helper.
# Regression for the two-digit spine aliases of export-style rigs
# (Grab3D / Mixamo FBX export), where the spine chain is named
# `Spine`, `Spine01`, `Spine02` (two digits, no decimal point):
# these names must resolve so all 9 anchors are mapped.

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
from flexforge.weight_nomi import resolve_bone_name  # noqa: E402


# Export-style rig: side anchors keep the Quaternius aliases already
# known, the spine chain uses the two-digit names that used to be
# unrecognized (Spine01 / Spine02).
_EXPORT_NAMES = [
    "Spine", "Spine01", "Spine02",
    "LeftShoulder", "LeftUpperArm", "LeftLowerArm",
    "LeftUpLeg", "LeftLeg", "LeftFoot",
]


def test_export_two_digit_spine_maps_all_nine():
    report = rig_detect.detect_rig(_EXPORT_NAMES)
    assert report["coverage"] == 1.0, report
    assert report["matched"] == 9, report
    assert report["missing"] == 0, report
    assert report["matched_bones"]["spine"] == "Spine", report
    assert report["matched_bones"]["spine.001"] == "Spine01", report
    assert report["matched_bones"]["spine.002"] == "Spine02", report
    assert len(report["preset_ids"]) == 9, report


def test_spine_two_digit_aliases_resolve_and_keep_old_ones():
    assert resolve_bone_name("spine.001", ["Spine01"]) == "Spine01"
    assert resolve_bone_name("spine.002", ["Spine02"]) == "Spine02"
    # the pre-existing single-digit aliases must keep working
    assert resolve_bone_name("spine.001", ["Spine1"]) == "Spine1"
    assert resolve_bone_name("spine.002", ["Spine2"]) == "Spine2"


def _main():
    tests = [
        test_export_two_digit_spine_maps_all_nine,
        test_spine_two_digit_aliases_resolve_and_keep_old_ones,
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
