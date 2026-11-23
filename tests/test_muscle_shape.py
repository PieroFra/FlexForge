# Deterministic headless test of the FlexForge muscle shape core.
# The math runs on plain lists; no Blender scene is created.

import sys
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

try:
    import bpy  # noqa: F401
except ImportError:
    stub_folder = "/tmp/flexforge_test"
    if stub_folder not in sys.path:
        sys.path.insert(0, stub_folder)
    from flexforge_stub import installa_stub_bpy as install_bpy_stub

    install_bpy_stub(props_default=True)

from flexforge import muscle_shape  # noqa: E402

# Two contiguous segments on the X axis, one muscle of total length 2.
SEGMENTS = {
    "muscle_biceps_01": ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
    "muscle_biceps_02": ((1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
    "muscle_triceps_01": ((0.0, 1.0, 0.0), (0.0, 3.0, 0.0)),
}


def test_compute_rest_length():
    lengths = muscle_shape.compute_rest_length(SEGMENTS)
    assert lengths["flexforge_biceps"] == 2.0, lengths
    assert lengths["flexforge_triceps"] == 2.0, lengths
    raised = False
    try:
        muscle_shape.compute_rest_length({})
    except muscle_shape.BakeError:
        raised = True
    assert raised


def test_solve_length():
    assert muscle_shape.solve_length(2.0, 0.0) == 2.0
    assert muscle_shape.solve_length(2.0, 0.5) == 1.0
    assert muscle_shape.solve_length(2.0, 1.0) == 0.0
    raised = False
    try:
        muscle_shape.solve_length(2.0, 1.5)
    except muscle_shape.BakeError:
        raised = True
    assert raised


def test_preserve_volume():
    # Halving the length multiplies the radius by sqrt(2): volume unchanged.
    radius = muscle_shape.preserve_volume(0.5, 2.0, 1.0)
    assert abs(radius - 0.5 * 2.0 ** 0.5) < 1e-9, radius
    rest = muscle_shape.preserve_volume(0.5, 2.0, 2.0)
    assert rest == 0.5, rest
    raised = False
    try:
        muscle_shape.preserve_volume(0.5, 2.0, 0.0)
    except muscle_shape.BakeError:
        raised = True
    assert raised


def test_capsule_chain_points():
    chains = muscle_shape.capsule_chain_points(SEGMENTS, steps_per_segment=2)
    biceps = chains["flexforge_biceps"]
    assert len(biceps) == 5, biceps  # 2 segments remap onto 5 points
    assert biceps[0] == (0.0, 0.0, 0.0), biceps[0]
    assert biceps[-1] == (2.0, 0.0, 0.0), biceps[-1]
    assert biceps[2] == (1.0, 0.0, 0.0), biceps[2]  # shared joint, once
    triceps = chains["flexforge_triceps"]
    assert len(triceps) == 3, triceps
    assert triceps[-1] == (0.0, 3.0, 0.0), triceps[-1]
    raised = False
    try:
        muscle_shape.capsule_chain_points(SEGMENTS, steps_per_segment=0)
    except muscle_shape.BakeError:
        raised = True
    assert raised


def _main():
    tests = [
        test_compute_rest_length,
        test_solve_length,
        test_preserve_volume,
        test_capsule_chain_points,
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
