# Deterministic headless test of the FlexForge engine budget helper.
# The tested functions are pure (no bpy objects needed beyond the package
# import), so they run identically inside and outside Blender.

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

from flexforge import engine_budget  # noqa: E402


def test_report_within_budget():
    weights_map = {0: {"a": 0.6, "b": 0.4}, 1: {"a": 1.0}}
    report = engine_budget.engine_budget_report(
        weights_map, ["k1", "k2"], ["bone_a", "bone_b"], 4, 10, 60
    )
    assert report["vertices"] == 2, report
    assert report["over_budget"] == 0, report
    assert report["max_influences"] == 2, report
    assert report["shape_keys"] == 2, report
    assert report["bones"] == 2, report
    assert report["within_budget"] is True, report
    assert report["lod"] == 1, report


def test_report_over_budget():
    weights_map = {0: {"a": 0.2, "b": 0.2, "c": 0.2, "d": 0.2, "e": 0.2}}
    report = engine_budget.engine_budget_report(
        weights_map, ["k%d" % i for i in range(12)], ["b%d" % i for i in range(70)],
        4, 10, 60, lod=3,
    )
    assert report["over_budget"] == 1, report
    assert report["max_influences"] == 5, report
    assert report["shape_keys"] == 12, report
    assert report["bones"] == 70, report
    assert report["within_budget"] is False, report
    assert report["lod"] == 3, report


def test_fit_applies_limit():
    weights_map = {0: {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4, "e": 0.5}}
    result = engine_budget.fit_engine_budget(
        weights_map, ["k%d" % i for i in range(5)], ["b%d" % i for i in range(3)],
        4, 3, 10,
    )
    after = result["report"]
    assert after["over_budget"] == 0, after
    assert after["max_influences"] == 4, after
    assert after["shape_keys"] == 3, after
    assert after["bones"] == 3, after
    assert after["within_budget"] is True, after
    # input not modified by pure fit when weights are related? input lifecycle is not mutating the given shape keys/bones
    assert result["shape_keys"] == ["k0", "k1", "k2"], result["shape_keys"]
    assert len(result["weights"][0]) == 4, result["weights"]


def test_fit_respects_bone_budget():
    weights_map = {0: {"a": 1.0}}
    bones = ["b%d" % i for i in range(15)]
    result = engine_budget.fit_engine_budget(
        weights_map, [], bones, 4, 10, 10, lod=2,
    )
    assert len(result["bones"]) == 10, result["bones"]
    assert result["bones"] == bones[:10], result["bones"]
    assert result["report"]["bones"] == 10, result["report"]
    assert result["report"]["within_budget"] is True, result["report"]


def test_invalid_lod_error():
    error = None
    try:
        engine_budget.engine_budget_report({0: {"a": 1.0}}, [], [], 4, 10, 60, lod=5)
    except engine_budget.BudgetError as exception:
        error = exception
    assert error is not None, "expected BudgetError with lod=5"


def test_invalid_limits_error():
    error = None
    try:
        engine_budget.fit_engine_budget({0: {"a": 1.0}}, [], [], 0, 10, 60)
    except engine_budget.BudgetError as exception:
        error = exception
    assert error is not None, "expected BudgetError with max_influences=0"


def test_budget_message():
    message = engine_budget.budget_message(
        {
            "vertices": 3,
            "over_budget": 0,
            "max_influences": 4,
            "shape_keys": 2,
            "bones": 5,
            "within_budget": True,
            "lod": 1,
            "max_shape_keys": 10,
            "max_bones": 60,
        }
    )
    expected = (
        "FlexForge - budget: vertices=3 over_budget=0 max_influences=4 "
        "shape_keys=2/10 bones=5/60 within_budget=yes lod=1"
    )
    assert message == expected, message


def _main():
    tests = [
        test_report_within_budget,
        test_report_over_budget,
        test_fit_applies_limit,
        test_fit_respects_bone_budget,
        test_invalid_lod_error,
        test_invalid_limits_error,
        test_budget_message,
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
    total = passed + failed
    print("RISULTATO passati=%d falliti=%d totale=%d" % (passed, failed, total))
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(_main())
