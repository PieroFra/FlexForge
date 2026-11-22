# Headless test of the public functions of weight_nomi.
import sys
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def _install_stub():
    try:
        import bpy  # noqa: F401
        return False
    except ImportError:
        pass
    folder = "/tmp/flexforge_test"
    if folder not in sys.path:
        sys.path.insert(0, folder)
    from flexforge_stub import installa_stub_bpy as install_bpy_stub

    return install_bpy_stub(props_default=True, con_ops=True)


_install_stub()

from flexforge import weight_nomi  # noqa: E402


def test_invert_group_name():
    assert weight_nomi.invert_group_name("arm.L") == "arm.R"
    assert weight_nomi.invert_group_name("hand_R") == "hand_L"
    assert weight_nomi.invert_group_name("spine") == "spine"


def test_map_groups():
    mapping = weight_nomi.map_groups(["a.L", "b"], ["a.L", "b", "c"])
    assert mapping == {"a.L": "a.L", "b": "b"}, mapping
    inverted = weight_nomi.map_groups(["a.L"], ["a.R"], True)
    assert inverted == {"a.L": "a.R"}, inverted
    empty = weight_nomi.map_groups(["x"], ["y"])
    assert empty == {}, empty


def test_resolve_bone_name_and_infix_lr():
    assert weight_nomi.invert_group_name("hand.l") == "hand.r"
    assert weight_nomi.invert_group_name("arm_l") == "arm_r"
    assert weight_nomi.invert_group_name("LeftUpperArm") == "RightUpperArm"
    assert weight_nomi.invert_group_name("J_Bip_L_UpperArm") == "J_Bip_R_UpperArm"
    assert weight_nomi.invert_group_name("mixamorig:LeftArm") == "mixamorig:RightArm"

    def resolve(name, bones):
        return weight_nomi.resolve_bone_name(name, bones)

    assert resolve("upper_arm.L", ["DEF-upper_arm.L"]) == "DEF-upper_arm.L"
    assert resolve("forearm.L", ["arm_stretch.l", "forearm_stretch.l"]) == "forearm_stretch.l"
    assert resolve("upper_arm.L", ["mixamorig:LeftArm"]) == "mixamorig:LeftArm"
    assert resolve("forearm.L", ["lowerarm_l"]) == "lowerarm_l"
    assert resolve("upper_arm.L", ["LeftUpperArm"]) == "LeftUpperArm"
    assert resolve("forearm.L", ["J_Bip_L_LowerArm"]) == "J_Bip_L_LowerArm"
    assert resolve("thigh.L", ["DEF_Leg.L"]) == "DEF_Leg.L"
    assert resolve("spine", ["DEF_Spine.01"]) == "DEF_Spine.01"
    assert resolve("upper_arm.R", ["upperarm_r"]) == "upperarm_r"
    assert resolve("shin.R", ["calf_r"]) == "calf_r"
    assert resolve("existing", ["existing"]) == "existing"
    assert resolve("nowhere", ["other"]) == "nowhere"


def test_resolve_bone_name_namespaced_aliases():
    bones = ["LeftArm", "RightArm", "LeftForeArm", "RightForeArm",
             "LeftShoulder", "RightShoulder", "LeftUpLeg", "RightUpLeg",
             "LeftLeg", "RightLeg", "LeftFoot", "RightFoot",
             "Spine", "Spine1", "Spine2"]

    def resolve(name):
        return weight_nomi.resolve_bone_name(name, bones)

    assert resolve("upper_arm.L") == "LeftArm"
    assert resolve("forearm.L") == "LeftForeArm"
    assert resolve("thigh.L") == "LeftUpLeg"
    assert resolve("shin.L") == "LeftLeg"
    assert resolve("spine.002") == "Spine2"
    assert resolve("upper_arm.R") == "RightArm"
    assert resolve("forearm.R") == "RightForeArm"
    assert resolve("thigh.R") == "RightUpLeg"
    assert resolve("shin.R") == "RightLeg"
    assert weight_nomi.strip_namespace("mixamorig:LeftArm") == "LeftArm"
    assert weight_nomi.strip_namespace("LeftArm") == "LeftArm"
    prefixed = ["mixamorig1:LeftArm", "mixamorig1:Spine2"]
    assert weight_nomi.resolve_bone_name("upper_arm.L", prefixed) == "mixamorig1:LeftArm"
    assert weight_nomi.resolve_bone_name("spine.002", prefixed) == "mixamorig1:Spine2"


def test_resolve_bip01_aliases():
    bones = ["Bip01 L UpperArm", "Bip01 R UpperArm", "Bip01 L Forearm",
             "Bip01 R Forearm", "Bip01 L Clavicle", "Bip01 R Clavicle",
             "Bip01 L Thigh", "Bip01 R Thigh", "Bip01 L Calf", "Bip01 R Calf",
             "Bip01 L Foot", "Bip01 R Foot", "Bip01 Spine", "Bip01 Pelvis",
             "Bip01 Spine1", "Bip01 Spine2"]
    assert weight_nomi.invert_group_name("Bip01 L UpperArm") == "Bip01 R UpperArm"
    assert weight_nomi.invert_group_name("Bip01 L Calf") == "Bip01 R Calf"
    assert weight_nomi.invert_group_name("Bip01 L Foot") == "Bip01 R Foot"

    def resolve(name):
        return weight_nomi.resolve_bone_name(name, bones)

    assert resolve("upper_arm.L") == "Bip01 L UpperArm"
    assert resolve("forearm.L") == "Bip01 L Forearm"
    assert resolve("shoulder.L") == "Bip01 L Clavicle"
    assert resolve("thigh.L") == "Bip01 L Thigh"
    assert resolve("shin.L") == "Bip01 L Calf"
    assert resolve("foot.L") == "Bip01 L Foot"
    assert resolve("spine") == "Bip01 Spine"
    assert resolve("spine.001") == "Bip01 Spine1"
    assert resolve("spine.002") == "Bip01 Spine2"
    assert resolve("upper_arm.R") == "Bip01 R UpperArm"
    assert resolve("forearm.R") == "Bip01 R Forearm"
    assert resolve("shoulder.R") == "Bip01 R Clavicle"
    assert resolve("thigh.R") == "Bip01 R Thigh"
    assert resolve("shin.R") == "Bip01 R Calf"
    assert resolve("foot.R") == "Bip01 R Foot"
    assert weight_nomi.resolve_bone_name("spine", ["Bip01 Pelvis"]) == "Bip01 Pelvis"


def _main():
    tests = [test_invert_group_name, test_map_groups,
             test_resolve_bone_name_and_infix_lr,
             test_resolve_bone_name_namespaced_aliases,
             test_resolve_bip01_aliases]
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
