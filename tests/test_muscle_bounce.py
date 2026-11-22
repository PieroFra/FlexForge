# Deterministic headless test of the FlexForge skin bounce.
# The spring math runs on plain lists; one test bakes real shape keys inside
# Blender and runs the operator end to end.

import sys
import traceback
import types
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

    installed = install_bpy_stub(props_default=True)
    return installed


_install_bpy_stub()

import bpy  # noqa: E402

from flexforge import muscle_bounce  # noqa: E402


def test_constants_and_empty():
    assert muscle_bounce.DEFAULT_STIFFNESS == 0.35, muscle_bounce.DEFAULT_STIFFNESS
    assert muscle_bounce.DEFAULT_DAMPING == 0.28, muscle_bounce.DEFAULT_DAMPING
    assert muscle_bounce.DEFAULT_OVERSHOOT == 1.35, muscle_bounce.DEFAULT_OVERSHOOT
    assert muscle_bounce.SHAPE_KEY_PREFIX == "flexforge_"
    # No input, no output: the curve keeps the length of its input.
    assert muscle_bounce.compute_spring_curve([]) == []
    # A constant signal stays on its own value, start included.
    flat = muscle_bounce.compute_spring_curve([0.5] * 5)
    assert len(flat) == 5, flat
    for value in flat:
        assert isinstance(value, float), value
        assert abs(value - 0.5) < 1e-12, flat
    single = muscle_bounce.compute_spring_curve([0.7])
    assert single == [0.7], single


def test_step_response_overshoot_then_settles():
    values = [0.0] + [1.0] * 59
    curve = muscle_bounce.compute_spring_curve(values)
    assert len(curve) == 60, len(curve)
    # The step overshoots past the target, then settles back on it.
    assert max(curve) > 1.0, max(curve)
    assert abs(max(curve) - muscle_bounce.DEFAULT_OVERSHOOT) < 1e-6, max(curve)
    assert abs(curve[-1] - 1.0) < 0.05, curve[-1]
    assert abs(curve[0]) < 1e-12, curve[0]
    # A softer target is followed without ever passing it wildly.
    ramp = muscle_bounce.compute_spring_curve([(frame - 1) / 9.0
                                               for frame in range(1, 11)])
    assert len(ramp) == 10, len(ramp)
    assert ramp[0] == 0.0 and ramp[-1] > 0.9, ramp


def test_high_damping_reduces_overshoot():
    values = [0.0] + [1.0] * 39
    soft = muscle_bounce.compute_spring_curve(values, damping=0.28)
    stiff = muscle_bounce.compute_spring_curve(values, damping=1.2)
    assert max(soft) > max(stiff), (max(soft), max(stiff))
    assert max(stiff) <= 1.0 + 1e-9, max(stiff)
    assert abs(stiff[-1] - 1.0) < 1e-6, stiff[-1]


def test_clamp_respected():
    values = [0.0] + [1.0] * 20
    # Undamped and very stiff: without the clamp the curve jumps far past 1.0.
    free = muscle_bounce.compute_spring_curve(values, stiffness=3.0, damping=0.0)
    assert max(free) > 1.3, max(free)
    capped = muscle_bounce.compute_spring_curve(values, stiffness=3.0,
                                                damping=0.0, clamp_max=0.9)
    assert max(capped) <= 0.9 + 1e-12, max(capped)
    assert max(capped) > 0.85, max(capped)
    # The lower clamp holds a decaying value above the floor too.
    falling = [1.0] + [0.0] * 20
    floored = muscle_bounce.compute_spring_curve(falling, stiffness=3.0,
                                                 damping=0.0, clamp_min=0.2)
    assert min(floored) >= 0.2 - 1e-12, min(floored)
    for value in capped + floored:
        assert 0.0 <= value <= 1.35, value


def test_find_flexforge_keys():
    keys = [types.SimpleNamespace(name=name)
            for name in ("Basis", "flexforge_biceps", "flexforge_triceps", "jaw")]
    obj = types.SimpleNamespace(
        data=types.SimpleNamespace(
            shape_keys=types.SimpleNamespace(key_blocks=keys)
        )
    )
    found = muscle_bounce.find_flexforge_keys(obj)
    assert [key.name for key in found] == ["flexforge_biceps",
                                           "flexforge_triceps"], found
    assert muscle_bounce.find_flexforge_keys(obj, "jaw") == [keys[3]]
    # A mesh without shape keys answers with an empty list, not an error.
    plain = types.SimpleNamespace(data=types.SimpleNamespace(shape_keys=None))
    assert muscle_bounce.find_flexforge_keys(plain) == []
    assert muscle_bounce.find_flexforge_keys(types.SimpleNamespace()) == []


def test_bake_real_blender():
    cls = muscle_bounce.FLEXFORGE_OT_bake_bounce
    assert cls.bl_idname == "flexforge.bake_bounce", cls.bl_idname
    assert cls.bl_label == "Bake skin bounce", cls.bl_label
    assert "REGISTER" in cls.bl_options, cls.bl_options
    assert "UNDO" in cls.bl_options, cls.bl_options
    annotations = getattr(cls, "__annotations__", {})
    for name in ("stiffness", "damping", "overshoot_limit"):
        assert name in annotations, "missing property: %s" % name

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 10
    mesh = bpy.data.meshes.new("flexforge_bounce_mesh")
    mesh.from_pydata([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], [], [(0, 1)])
    obj = bpy.data.objects.new("flexforge_bounce_mesh", mesh)
    scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    obj.shape_key_add(name="Basis", from_mix=False)
    key = obj.shape_key_add(name="flexforge_biceps", from_mix=False)

    try:
        for frame in range(1, 11):
            key.value = (frame - 1) / 9.0
            key.keyframe_insert("value", frame=frame)
        scene.frame_set(1)
        report = muscle_bounce.apply_muscle_bounce(obj, scene)
        assert report == {"keys": 1, "frames": 10, "drivers_removed": 0}, report
        assert scene.frame_current == 1, scene.frame_current
        # The baked curve lags the linear ramp: the keyframes were replaced.
        scene.frame_set(4)
        baked = key.value
        assert abs(baked - 0.2207) < 1e-3, baked
        assert abs(baked - (3 / 9.0)) > 0.05, baked
        scene.frame_set(10)
        assert abs(key.value - 1.0292) < 1e-3, key.value

        bpy.utils.register_class(cls)
        try:
            bpy.context.view_layer.objects.active = obj
            outcome = bpy.ops.flexforge.bake_bounce(stiffness=0.35,
                                                    damping=0.28,
                                                    overshoot_limit=1.35)
        finally:
            bpy.utils.unregister_class(cls)
        assert outcome == {"FINISHED"}, outcome
    finally:
        scene.frame_start = 1
        scene.frame_end = 250
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(mesh)


def test_bake_bounce_removes_existing_driver():
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 10
    mesh = bpy.data.meshes.new("flexforge_bounce_driver_mesh")
    mesh.from_pydata([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], [], [(0, 1)])
    obj = bpy.data.objects.new("flexforge_bounce_driver_mesh", mesh)
    scene.collection.objects.link(obj)
    obj.shape_key_add(name="Basis", from_mix=False)
    key = obj.shape_key_add(name="flexforge_biceps", from_mix=False)

    try:
        for frame in range(1, 11):
            key.value = (frame - 1) / 9.0
            key.keyframe_insert("value", frame=frame)
        curve = key.driver_add("value")
        assert curve.driver is not None, curve
        scene.frame_set(1)
        report = muscle_bounce.apply_muscle_bounce(obj, scene)
        assert report == {"keys": 1, "frames": 10, "drivers_removed": 1}, report
        animation_data = key.id_data.animation_data
        assert animation_data is not None, "the baked keyframes must stay"
        assert len(animation_data.drivers) == 0, [
            driver.data_path for driver in animation_data.drivers]
        assert scene.frame_current == 1, scene.frame_current
        # With the driver gone the value follows the baked spring curve.
        scene.frame_set(4)
        baked = key.value
        assert abs(baked - 0.2207) < 1e-3, baked
        assert abs(baked - (3 / 9.0)) > 0.05, baked
        scene.frame_set(10)
        assert abs(key.value - 1.0292) < 1e-3, key.value
    finally:
        scene.frame_start = 1
        scene.frame_end = 250
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.meshes.remove(mesh)


def _main():
    tests = [
        test_constants_and_empty,
        test_step_response_overshoot_then_settles,
        test_high_damping_reduces_overshoot,
        test_clamp_respected,
        test_find_flexforge_keys,
        test_bake_real_blender,
        test_bake_bounce_removes_existing_driver,
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
