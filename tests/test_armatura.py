# Headless test of the public armature_of_mesh function.
import sys
import traceback
import types
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

from flexforge import armatura  # noqa: E402


def _armature(name="Rig"):
    return types.SimpleNamespace(type="ARMATURE", name=name)


def test_armature_from_modifier():
    rig = _armature()
    mesh = types.SimpleNamespace(
        modifiers=[types.SimpleNamespace(type="ARMATURE", object=rig)],
        parent=None,
    )
    assert armatura.armature_of_mesh(mesh) is rig


def test_armature_from_parent():
    rig = _armature()
    mesh = types.SimpleNamespace(modifiers=[], parent=rig)
    assert armatura.armature_of_mesh(mesh) is rig


def test_armature_missing():
    mesh = types.SimpleNamespace(modifiers=[], parent=None)
    assert armatura.armature_of_mesh(mesh) is None


def _main():
    tests = [
        test_armature_from_modifier,
        test_armature_from_parent,
        test_armature_missing,
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
