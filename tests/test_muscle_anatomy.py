# Headless test of the anatomical muscle shaping helpers.
import sys
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from flexforge import muscle_anatomy  # noqa: E402


def test_family_from_bone_lr():
    assert muscle_anatomy.muscle_family_from_bone("muscle_biceps_r_02") == "biceps"
    assert muscle_anatomy.muscle_family_from_bone("muscle_biceps_l_02") == "biceps"
    assert muscle_anatomy.muscle_family_from_bone("muscle_pectoral_01") == "pectoral"
    assert muscle_anatomy.muscle_family_from_bone("muscle_gluteus_l") == "gluteus"


def test_directional_factor_biceps():
    front = muscle_anatomy.directional_factor("muscle_biceps_r_01", (0.0, -1.0, 0.0))
    back = muscle_anatomy.directional_factor("muscle_biceps_r_01", (0.0, 1.0, 0.0))
    assert abs(front - 1.0) < 1e-9
    assert abs(back - 0.15) < 1e-9
    same = muscle_anatomy.directional_factor("muscle_biceps_r_01", (0.0, -5.0, 0.0))
    assert abs(same - 1.0) < 1e-9


def test_directional_factor_triceps():
    back = muscle_anatomy.directional_factor("muscle_triceps_l_03", (0.0, 1.0, 0.0))
    front = muscle_anatomy.directional_factor("muscle_triceps_l_03", (0.0, -1.0, 0.0))
    assert abs(back - 1.0) < 1e-9
    assert abs(front - 0.15) < 1e-9
    side = muscle_anatomy.directional_factor("muscle_triceps_l_03", (1.0, 0.0, 0.0))
    assert 0.15 < side < 1.0


def test_directional_factor_custom_fallback():
    assert muscle_anatomy.directional_factor("custom_bone", (0.0, 1.0, 0.0)) == 1.0
    assert muscle_anatomy.directional_factor("", (0.0, 1.0, 0.0)) == 1.0


def test_smooth_shape_deltas_diffuses():
    deltas = {0: (1.0, 0.0, 0.0)}
    edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
    result = muscle_anatomy.smooth_shape_deltas(deltas, edges, iterations=2)
    assert abs(result[0][0] - 1.0) > 1e-6
    assert abs(result[0][0]) < 1.0
    assert abs(result[1][0]) > 1e-6
    assert abs(result[3][0]) > 1e-6
    total = sum(delta[0] for delta in result.values())
    assert abs(total - 1.0) < 1e-9
    assert 0 in result and 2 in result


def test_smooth_shape_deltas_empty_edges():
    result = muscle_anatomy.smooth_shape_deltas({0: (0.5, 0.0, 0.0)}, [], iterations=3)
    assert list(result.keys()) == [0]
    assert abs(result[0][0] - 0.5) < 1e-9
    empty = muscle_anatomy.smooth_shape_deltas({}, [], iterations=1)
    assert empty == {}


def _main():
    tests = [
        test_family_from_bone_lr,
        test_directional_factor_biceps,
        test_directional_factor_triceps,
        test_directional_factor_custom_fallback,
        test_smooth_shape_deltas_diffuses,
        test_smooth_shape_deltas_empty_edges,
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
