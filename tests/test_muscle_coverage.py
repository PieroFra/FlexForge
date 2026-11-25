# Deterministic headless test of the FlexForge capsule skin COVERAGE.
# A short helper whose span cap keeps the capsule off the skin used to bind no
# vertex at all; the radius must reach the nearest masked skin vertex instead.
# The same test pins the opposite guard: the widened capsule stops just past
# the skin, so a far vertex of the mask (another body part) keeps its bone
# weight and never takes a muscle weight.
# No external dependency: if bpy is missing the shared stub is installed.

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

from flexforge import muscle_skinning  # noqa: E402

# A short helper: its span cap is 0.25 * 0.02 = 0.005, well below the 0.03 skin
# offset, so before the coverage floor the capsule bound nothing.
_SHORT_HEAD = (0.0, 0.0, 0.0)
_SHORT_TAIL = (0.0, 0.0, 0.02)
_SKIN_OFFSET = 0.03
_OWNER = "upper_arm.L"


def _short_segments(radius=0.1, head=_SHORT_HEAD, tail=_SHORT_TAIL):
    return {"muscle_short": {"head_local": head, "tail_local": tail,
                             "radius": radius}}


def test_the_span_cap_alone_leaves_the_short_helper_off_the_skin():
    """Characterisation: without the coverage floor the cap is 0.005 < 0.03."""
    capped = muscle_skinning._capsule_radius(
        0.1, _SHORT_HEAD, _SHORT_TAIL, 0.02
    )
    assert abs(capped - 0.005) < 1e-9, capped
    assert capped < _SKIN_OFFSET, capped


def test_short_helper_reaches_the_skin():
    """RED: the short helper must bind the skin 0.03 from its axis.

    The old span cap (0.005) left the vertex out, so the helper bound no
    vertex; the radius now reaches the nearest masked skin vertex.
    """
    segments = _short_segments()
    existing = {0: {_OWNER: 1.0}}
    bone_masks = {"muscle_short": [_OWNER]}
    coordinates = [(_SKIN_OFFSET, 0.0, 0.01)]
    report = muscle_skinning.compute_muscle_weights(
        existing, coordinates, segments, bone_masks=bone_masks
    )
    assert "muscle_short" in report["weights"][0], report["weights"]
    assert report["vertices_bound"] == 1, report
    assert report["muscles_bound"] == 1, report


def test_reach_stops_just_past_the_skin():
    """Guard: a masked vertex beyond k * skin stays unbound (no run-away)."""
    segments = _short_segments()
    # 0.072 is past the 1.9 * 0.03 = 0.057 reach, so the capsule stops.
    beyond = 2.4 * _SKIN_OFFSET
    existing = {0: {_OWNER: 1.0}, 1: {_OWNER: 1.0}}
    bone_masks = {"muscle_short": [_OWNER]}
    coordinates = [(_SKIN_OFFSET, 0.0, 0.01), (beyond, 0.0, 0.01)]
    report = muscle_skinning.compute_muscle_weights(
        existing, coordinates, segments, bone_masks=bone_masks
    )
    assert "muscle_short" in report["weights"][0], report["weights"]
    assert "muscle_short" not in report["weights"][1], report["weights"]
    assert abs(report["weights"][1][_OWNER] - 1.0) < 1e-6, report["weights"]
    assert report["vertices_bound"] == 1, report


def test_no_bleeding_to_the_other_body_part():
    """Guard: a far masked vertex (another part) keeps its bone weight.

    The mask alone does not protect here: the far vertex belongs to the same
    origin bone, so only the coverage ceiling keeps the muscle off it.
    """
    segments = _short_segments()
    other_arm = 0.6
    existing = {0: {_OWNER: 1.0}, 1: {_OWNER: 1.0}}
    bone_masks = {"muscle_short": [_OWNER]}
    coordinates = [(_SKIN_OFFSET, 0.0, 0.01), (other_arm, 0.0, 0.01)]
    report = muscle_skinning.compute_muscle_weights(
        existing, coordinates, segments, bone_masks=bone_masks
    )
    assert "muscle_short" in report["weights"][0], report["weights"]
    assert "muscle_short" not in report["weights"][1], report["weights"]
    assert abs(report["weights"][1][_OWNER] - 1.0) < 1e-6, report["weights"]


def test_coverage_is_scale_invariant():
    """A centimetre rig (unit_scale 100) reaches the same skin as the metre rig."""
    metre = muscle_skinning.compute_muscle_weights(
        {0: {_OWNER: 1.0}}, [(_SKIN_OFFSET, 0.0, 0.01)],
        _short_segments(), bone_masks={"muscle_short": [_OWNER]}, unit_scale=1.0,
    )
    centimetre = muscle_skinning.compute_muscle_weights(
        {0: {_OWNER: 1.0}}, [(100.0 * _SKIN_OFFSET, 0.0, 1.0)],
        _short_segments(radius=10.0, head=(0.0, 0.0, 0.0),
                        tail=(0.0, 0.0, 2.0)),
        bone_masks={"muscle_short": [_OWNER]}, unit_scale=100.0,
    )
    assert metre["muscles_bound"] == 1, metre
    assert centimetre["muscles_bound"] == 1, centimetre
    assert centimetre["vertices_bound"] == metre["vertices_bound"], (
        centimetre, metre
    )


def _main():
    tests = [
        test_the_span_cap_alone_leaves_the_short_helper_off_the_skin,
        test_short_helper_reaches_the_skin,
        test_reach_stops_just_past_the_skin,
        test_no_bleeding_to_the_other_body_part,
        test_coverage_is_scale_invariant,
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
