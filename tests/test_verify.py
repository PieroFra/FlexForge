# Deterministic headless test of the FlexForge deformation verification.
# If bpy is missing the shared stub is installed; the tested functions are pure
# on dictionaries, so they run identically inside and outside Blender.

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

import bpy  # noqa: E402

from flexforge import verify, weights  # noqa: E402


def test_valid_integrity():
    weights_map = {
        0: {"muscle_biceps_00": 0.8, "muscle_biceps_01": 0.2},
        1: {"muscle_biceps_00": 0.3, "muscle_biceps_01": 0.7},
    }
    report = verify.validate_deformation(
        weights_map, ["muscle_biceps_00", "muscle_biceps_01"], 4
    )
    assert report["vertices"] == 2, report
    assert report["over_budget"] == 0, report
    assert report["max_influences"] == 2, report
    assert report["helpers_present"] == 2, report
    assert report["valid"] is True, report


def test_valid_over_budget():
    weights_map = {
        0: {"a": 0.4, "b": 0.2, "c": 0.2, "d": 0.1, "e": 0.1},
    }
    report = verify.validate_deformation(weights_map, ["a"], 4)
    assert report["over_budget"] == 1, report
    assert report["max_influences"] == 5, report
    assert report["helpers_present"] == 1, report
    assert report["valid"] is False, report


def test_valid_missing_helpers():
    weights_map = {
        0: {"muscle_biceps_00": 1.0},
    }
    report = verify.validate_deformation(
        weights_map, ["muscle_biceps_00", "muscle_biceps_01"], 4
    )
    assert report["over_budget"] == 0, report
    assert report["helpers_present"] == 1, report
    assert report["valid"] is False, report


def test_valid_ignores_residuals():
    weights_map = {
        0: {"a": 0.5, "b": 0.25, "c": 0.25, "d": 1e-9},
        1: {"a": 1.0, "muscle_biceps_00": 1e-9},
    }
    report = verify.validate_deformation(
        weights_map, ["a", "muscle_biceps_00"], 4
    )
    assert report["over_budget"] == 0, report
    assert report["max_influences"] == 3, report
    assert report["helpers_present"] == 1, report
    assert report["valid"] is False, report


def test_valid_invalid_limit_error():
    error = None
    try:
        verify.validate_deformation({0: {"a": 1.0}}, ["a"], 0)
    except weights.WeightsError as exception:
        error = exception
    assert error is not None, "expected WeightsError with max_influences=0"
    # Single tolerance source: verify does not redefine EPS.
    assert verify.EPS is weights.EPS, (verify.EPS, weights.EPS)
    below = verify.validate_deformation(
        {0: {"a": 1.0, "b": weights.EPS / 2.0}}, ["a"], 4
    )
    assert below["max_influences"] == 1, below
    above = verify.validate_deformation(
        {0: {"a": 1.0, "b": weights.EPS * 2.0}}, ["a"], 4
    )
    assert above["max_influences"] == 2, above


def test_valid_negative_sum():
    error = None
    try:
        verify.validate_deformation({0: {"a": 0.2, "b": -1.0}}, ["a"], 4)
    except weights.WeightsError as exception:
        error = exception
    assert error is not None, "expected WeightsError with a negative sum"
    assert "Negative" in str(error), error


def test_valid_negative_weight():
    # Positive sum (1.0 - 0.5 = 0.5): the rejection concerns the single weight.
    error = None
    try:
        verify.validate_deformation({0: {"a": 1.0, "b": -0.5}}, ["a"], 4)
    except weights.WeightsError as exception:
        error = exception
    assert error is not None, "expected WeightsError with a negative weight"
    assert "Negative weight" in str(error), error


def test_valid_empty_helpers():
    weights_map = {0: {"a": 1.0}}
    report = verify.validate_deformation(weights_map, [], 4)
    assert report["over_budget"] == 0, report
    assert report["helpers_present"] == 0, report
    assert report["valid"] is False, report
    assert report["reason"] != "", report


def _main():
    tests = [
        test_valid_integrity,
        test_valid_over_budget,
        test_valid_missing_helpers,
        test_valid_ignores_residuals,
        test_valid_invalid_limit_error,
        test_valid_negative_sum,
        test_valid_negative_weight,
        test_valid_empty_helpers,
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
