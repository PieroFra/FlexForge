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


def test_check_collision_muscle_muscle():
    # Biceps (y=0) and triceps (x=0, y=1..3) stay 1 apart: with radius 0.1
    # each all envelopes are disjoint, with radius 0.6 they overlap by 0.2.
    assert muscle_shape.check_collision_muscle_muscle(SEGMENTS) == []
    collisions = muscle_shape.check_collision_muscle_muscle(
        SEGMENTS, {"muscle_biceps_01": 0.6, "muscle_triceps_01": 0.6})
    assert len(collisions) == 1, collisions
    assert collisions[0][0] == "flexforge_biceps", collisions
    assert collisions[0][1] == "flexforge_triceps", collisions
    assert abs(collisions[0][2] - 0.2) < 1e-6, collisions
    raised = False
    try:
        muscle_shape.check_collision_muscle_muscle({})
    except muscle_shape.BakeError:
        raised = True
    assert raised


def test_check_collision_muscle_bone():
    # A bone on the X axis overlaps the biceps, a far bone does not.
    assert muscle_shape.check_collision_muscle_bone(
        SEGMENTS, {"humerus": ((0.0, 0.0, 5.0), (1.0, 0.0, 5.0))}) == []
    collisions = muscle_shape.check_collision_muscle_bone(
        SEGMENTS, {"humerus": ((0.0, 0.1, 0.0), (1.0, 0.1, 0.0))},
        {"muscle_biceps_01": 0.2, "muscle_biceps_02": 0.2, "humerus": 0.2})
    assert len(collisions) == 1, collisions
    assert collisions[0][0] == "flexforge_biceps", collisions
    assert collisions[0][1] == "humerus", collisions
    assert abs(collisions[0][2] - 0.3) < 1e-6, collisions
    raised = False
    try:
        muscle_shape.check_collision_muscle_bone(SEGMENTS, {})
    except muscle_shape.BakeError:
        raised = True
    assert raised


def test_skin_limit_check():
    vertices = {
        0: (0.5, 0.0, 0.0),   # on the biceps segment
        1: (0.5, 0.01, 0.0),  # within the 0.05 skin limit
        2: (5.0, 5.0, 5.0),   # far from every muscle
    }
    assert muscle_shape.skin_limit_check(SEGMENTS, vertices) == [2]
    assert muscle_shape.skin_limit_check(
        SEGMENTS, vertices, skin_limit=10.0) == []
    raised = False
    try:
        muscle_shape.skin_limit_check({}, vertices)
    except muscle_shape.BakeError:
        raised = True
    assert raised


def test_collision_report():
    report = muscle_shape.collision_report(
        SEGMENTS,
        {"humerus": ((0.0, 0.0, 5.0), (1.0, 0.0, 5.0))},
        vertex_coordinates={0: (0.5, 0.0, 0.0), 3: (9.0, 9.0, 9.0)})
    assert report["muscle_muscle"] == [], report
    assert report["muscle_bone"] == [], report
    assert report["skin_limit"] == [3], report
    empty = muscle_shape.collision_report(SEGMENTS)
    assert empty == {"muscle_muscle": [], "muscle_bone": [],
                     "skin_limit": []}, empty


def _main():
    tests = [
        test_compute_rest_length,
        test_solve_length,
        test_preserve_volume,
        test_capsule_chain_points,
        test_check_collision_muscle_muscle,
        test_check_collision_muscle_bone,
        test_skin_limit_check,
        test_collision_report,
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
