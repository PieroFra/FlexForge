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


def test_rbf_weight():
    assert muscle_shape.rbf_weight(0.0, 1.0) == 1.0
    assert muscle_shape.rbf_weight(1.0, 1.0) == 0.0
    assert muscle_shape.rbf_weight(2.0, 1.0) == 0.0
    half = muscle_shape.rbf_weight(0.5, 1.0)
    assert abs(half - 0.1875) < 1e-12, half  # (1-t)**4 * (4t+1) at t=0.5
    raised = False
    try:
        muscle_shape.rbf_weight(0.0, 0.0)
    except muscle_shape.BakeError:
        raised = True
    assert raised


def test_pose_correction():
    controls = [((0.0, 0.0), (1.0, 0.0)), ((2.0, 0.0), (0.0, 1.0))]
    assert muscle_shape.pose_correction((0.0, 0.0), controls) == (1.0, 0.0)
    assert muscle_shape.pose_correction((2.0, 0.0), controls) == (0.0, 1.0)
    mid = muscle_shape.pose_correction((1.0, 0.0), controls, radius=2.0)
    assert abs(mid[0] - 0.5) < 1e-9 and abs(mid[1] - 0.5) < 1e-9, mid
    far = muscle_shape.pose_correction((10.0, 0.0), controls)
    assert far == (0.0, 0.0), far
    raised = False
    try:
        muscle_shape.pose_correction((0.0,), [])
    except muscle_shape.BakeError:
        raised = True
    assert raised


def test_apply_pose_correction():
    base = {"muscle_biceps_01": {0: (0.1, 0.0, 0.0)}}
    shape = {"muscle_biceps_01": {0: (0.0, 0.2, 0.0)}}
    controls = [((0.0, 0.0), {"muscle_biceps_01": {0: (0.0, 0.0, 0.3)}})]
    corrected = muscle_shape.apply_pose_correction(base, (0.0, 0.0), controls)
    assert corrected == {"muscle_biceps_01": {0: (0.1, 0.0, 0.3)}}, corrected
    assert base == {"muscle_biceps_01": {0: (0.1, 0.0, 0.0)}}, base
    beyond = muscle_shape.apply_pose_correction(
        base, (9.0, 0.0), controls, fallback_deltas=shape)
    assert beyond == shape, beyond
    no_controls = muscle_shape.apply_pose_correction(
        base, (0.0, 0.0), [], fallback_deltas=shape)
    assert no_controls == shape, no_controls
    as_mapping = muscle_shape.apply_pose_correction(
        base, (0.0, 0.0), dict(controls), fallback_deltas=shape)
    assert as_mapping == corrected, as_mapping


def test_bake_morph_target():
    deltas = {"muscle_biceps_01": {0: (0.1, 0.0, 0.0), 2: (0.0, 0.2, 0.0)}}
    target = muscle_shape.bake_morph_target(deltas, "flex_biceps", factor=2.0)
    assert target["name"] == "flex_biceps", target
    assert target["factor"] == 2.0, target
    assert target["deltas"]["muscle_biceps_01"][0] == (0.2, 0.0, 0.0), target
    assert deltas["muscle_biceps_01"][0] == (0.1, 0.0, 0.0), deltas
    raised = False
    try:
        muscle_shape.bake_morph_target({"b": {0: (1.0, 0.0)}}, "flex")
    except muscle_shape.BakeError:
        raised = True
    assert raised


def test_export_cache():
    target = muscle_shape.bake_morph_target(
        {"muscle_biceps_01": {0: (0.1, 0.0, 0.0)}}, "flex_biceps", factor=2.0)
    cache = muscle_shape.export_cache(target)
    assert cache["version"] == 1, cache
    assert cache["targets"][0]["name"] == "flex_biceps", cache
    assert cache["targets"][0]["factor"] == 2.0, cache
    assert cache["targets"][0]["deltas"]["muscle_biceps_01"]["0"] == [0.2, 0.0, 0.0], cache
    multi = muscle_shape.export_cache([target, target])
    assert len(multi["targets"]) == 2, multi
    raised = False
    try:
        muscle_shape.export_cache([])
    except muscle_shape.BakeError:
        raised = True
    assert raised


def test_import_cache():
    target = muscle_shape.bake_morph_target(
        {"muscle_biceps_01": {0: (0.1, 0.0, 0.0)}}, "flex_biceps", factor=2.0)
    restored = muscle_shape.import_cache(
        muscle_shape.export_cache([target]))[0]
    assert restored == target, restored
    assert isinstance(next(iter(restored["deltas"]["muscle_biceps_01"])), int)
    raised = False
    try:
        muscle_shape.import_cache({"version": 99, "targets": []})
    except muscle_shape.BakeError:
        raised = True
    assert raised


def test_roundtrip_check():
    deltas = {"muscle_biceps_01": {0: (0.1, 0.0, 0.0), 2: (0.0, 0.2, 0.0)},
              "muscle_triceps_01": {1: (0.01, 0.02, 0.03)}}
    report = muscle_shape.roundtrip_check(deltas, "flex_all", factor=0.5)
    assert report["ok"] is True, report
    assert report["max_error"] == 0.0, report
    assert report["target_count"] == 1, report
    assert report["vertex_count"] == 3, report


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
        test_rbf_weight,
        test_pose_correction,
        test_apply_pose_correction,
        test_bake_morph_target,
        test_export_cache,
        test_import_cache,
        test_roundtrip_check,
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
