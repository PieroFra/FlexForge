# Deterministic headless test of the FlexForge muscle (biceps) module.
# No external dependency: if bpy is not available a minimal stub is installed
# in sys.modules with `props`, `types` and `ops`, so the test runs identically
# outside Blender; inside Blender it uses the real bpy and a real armature
# created in code (Edit Mode included).

import sys
import types
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

# Test geometry: bent left arm, two bones with the default names.
_GEOMETRY = {
    "upper_arm.L": ((0.0, 0.0, 1.5), (0.0, 0.0, 1.0)),
    "forearm.L": ((0.0, 0.0, 1.0), (0.0, 0.0, 0.5)),
}


def _install_bpy_stub():
    """Install the shared bpy stub only if the real module is missing."""
    try:
        import bpy  # noqa: F401
        return False
    except ImportError:
        pass

    stub_folder = "/home/pierofra/.cache/opencode/tmp"
    if stub_folder not in sys.path:
        sys.path.insert(0, stub_folder)
    from flexforge_stub import installa_stub_bpy as install_bpy_stub

    return install_bpy_stub(props_default=True, con_ops=True)


class _FakeBone:
    """Fake bone with the minimal interface of an EditBone."""

    def __init__(self, name, head, tail):
        self.name = name
        self.head = tuple(head)
        self.tail = tuple(tail)
        self.parent = None
        self.use_deform = False
        self.use_connect = True


class _FakeBones:
    """Fake collection with the minimal interface of `armature.edit_bones`."""

    def __init__(self):
        self._bones = {}

    def new(self, name):
        if name in self._bones:
            raise RuntimeError("duplicate bone: %s" % name)
        bone = _FakeBone(name, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        self._bones[name] = bone
        return bone

    def get(self, name):
        return self._bones.get(name)

    def __iter__(self):
        return iter(self._bones.values())

    def __len__(self):
        return len(self._bones)


def _create_armature(names=("upper_arm.L", "forearm.L")):
    """Create the test armature: real bpy if present, otherwise fake."""
    import bpy

    if hasattr(bpy, "_registrate"):
        bones = _FakeBones()
        for name in names:
            head, tail = _GEOMETRY[name]
            bone = bones.new(name)
            bone.head = head
            bone.tail = tail
        return types.SimpleNamespace(
            name="FakeRig",
            type="ARMATURE",
            data=types.SimpleNamespace(edit_bones=bones),
        )

    data = bpy.data.armatures.new("FlexForgeTestRig")
    obj = bpy.data.objects.new("FlexForgeTestRig", data)
    bpy.context.scene.collection.objects.link(obj)
    for other in bpy.context.view_layer.objects:
        other.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="EDIT")
    for name in names:
        head, tail = _GEOMETRY[name]
        bone = data.edit_bones.new(name)
        bone.head = head
        bone.tail = tail
    return obj


def _destroy_armature(armature):
    """Switch back to Object Mode and delete the test armature (real bpy only)."""
    import bpy

    if hasattr(bpy, "_registrate"):
        return
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    data = armature.data
    bpy.data.objects.remove(armature, do_unlink=True)
    bpy.data.armatures.remove(data)


def test_default_spec():
    from flexforge import muscle

    spec = muscle.MuscleSpec()
    assert spec.name == "biceps", spec.name
    assert spec.origin_bone == "upper_arm.L", spec.origin_bone
    assert spec.insertion_bone == "forearm.L", spec.insertion_bone
    assert spec.segments == 2, spec.segments


def test_chain_created():
    from flexforge import muscle

    armature = _create_armature()
    try:
        names = muscle.create_muscle_chain(armature, muscle.MuscleSpec())
        assert len(names) == 2, "expected 2 segments, got %d" % len(names)
        assert names == ["muscle_biceps_01", "muscle_biceps_02"], names
        bones = armature.data.edit_bones
        for name in names:
            assert name.startswith("muscle_"), name
            assert bones.get(name) is not None, "missing bone: %s" % name
    finally:
        _destroy_armature(armature)


def test_interpolated_geometry():
    from flexforge import muscle

    armature = _create_armature()
    try:
        names = muscle.create_muscle_chain(
            armature, muscle.MuscleSpec(segments=2)
        )
        bones = armature.data.edit_bones
        origin = bones.get("upper_arm.L")
        insertion = bones.get("forearm.L")
        first = bones.get(names[0])
        last = bones.get(names[-1])
        assert tuple(first.head) == tuple(origin.head), (first.head, origin.head)
        # The chain stops at the insertion joint: it never reaches the tail of
        # the next bone into the forearm.
        assert tuple(last.tail) == tuple(insertion.head), (
            last.tail,
            insertion.head,
        )
        assert tuple(last.tail) != tuple(insertion.tail), (
            "chain still reaches the insertion tail"
        )
        assert tuple(first.tail) == tuple(bones.get(names[1]).head), (
            "chain not contiguous"
        )
        # With 2 segments the junction must fall halfway.
        expected = tuple(
            (origin.head[i] + insertion.head[i]) / 2.0 for i in range(3)
        )
        assert all(
            abs(first.tail[i] - expected[i]) < 1e-5 for i in range(3)
        ), (tuple(first.tail), expected)
    finally:
        _destroy_armature(armature)


def test_chain_stops_at_insertion_head():
    """Regression: a chain reaching insertion.tail skins the whole forearm."""
    from flexforge import muscle

    armature = _create_armature()
    try:
        names = muscle.create_muscle_chain(armature, muscle.MuscleSpec())
        bones = armature.data.edit_bones
        insertion = bones.get("forearm.L")
        last = bones.get(names[-1])
        # Span from the origin head to the insertion head: the last helper
        # stops at the elbow instead of running 0.5 further into the forearm.
        assert all(
            abs(last.tail[i] - insertion.head[i]) < 1e-5 for i in range(3)
        ), (tuple(last.tail), tuple(insertion.head))
        assert any(
            abs(last.tail[i] - insertion.tail[i]) > 1e-5 for i in range(3)
        ), "chain still reaches the insertion tail"
    finally:
        _destroy_armature(armature)


def test_use_deform_and_parent():
    from flexforge import muscle

    armature = _create_armature()
    try:
        names = muscle.create_muscle_chain(armature, muscle.MuscleSpec())
        bones = armature.data.edit_bones
        first = bones.get(names[0])
        second = bones.get(names[1])
        assert first.use_deform is True, "use_deform not enabled on the first bone"
        assert second.use_deform is True, "use_deform not enabled on the second bone"
        assert first.parent is not None, "first bone without parent"
        assert first.parent.name == "upper_arm.L", first.parent.name
        assert second.parent is not None, "second bone without parent"
        assert second.parent.name == names[0], second.parent.name
    finally:
        _destroy_armature(armature)


def test_custom_segments():
    from flexforge import muscle

    armature = _create_armature()
    try:
        names = muscle.create_muscle_chain(
            armature, muscle.MuscleSpec(segments=4)
        )
        assert len(names) == 4, "expected 4 segments, got %d" % len(names)
        assert names[-1] == "muscle_biceps_04", names[-1]
        for name in names:
            assert armature.data.edit_bones.get(name) is not None, name
    finally:
        _destroy_armature(armature)


def test_missing_bone_error():
    from flexforge import muscle

    armature = _create_armature(names=("upper_arm.L",))
    try:
        try:
            muscle.create_muscle_chain(armature, muscle.MuscleSpec())
        except muscle.MuscleError as error:
            assert "forearm.L" in str(error), str(error)
        else:
            raise AssertionError("expected MuscleError for a missing bone")
        assert armature.data.edit_bones.get("muscle_biceps_01") is None, (
            "chain created despite the error"
        )
    finally:
        _destroy_armature(armature)


def test_invalid_segments_error():
    from flexforge import muscle

    armature = _create_armature()
    try:
        try:
            muscle.create_muscle_chain(
                armature, muscle.MuscleSpec(segments=0)
            )
        except muscle.MuscleError as error:
            assert "segments" in str(error), str(error)
        else:
            raise AssertionError("expected MuscleError for segments=0")
    finally:
        _destroy_armature(armature)


def test_operator_registered():
    import flexforge
    from flexforge import muscle

    cls = muscle.FLEXFORGE_OT_create_biceps
    assert cls.bl_idname == "flexforge.create_biceps", cls.bl_idname
    assert cls in flexforge._CLASSES, "operator not present in _CLASSES"


class _FakeConstraints(list):
    """Minimal constraint collection with `new()` for the fake pose bones."""

    def new(self, type):
        constraint = types.SimpleNamespace(type=type, name="")
        self.append(constraint)
        return constraint


def test_pose_constraints_created():
    import bpy

    from flexforge import muscle

    fake = hasattr(bpy, "_registrate")
    armature = _create_armature()
    if fake:
        armature.pose = types.SimpleNamespace(bones={})
    try:
        names = muscle.create_muscle_chain(armature, muscle.MuscleSpec())
        if fake:
            armature.pose.bones = {
                name: types.SimpleNamespace(constraints=_FakeConstraints())
                for name in names
            }
        else:
            bpy.ops.object.mode_set(mode="OBJECT")
        handled = muscle.setup_muscle_constraints(
            armature, names, muscle.MuscleSpec(bulge=2.5)
        )
        assert handled == len(names), handled
        for name in names:
            pose_bone = armature.pose.bones[name]
            stretch = [
                constraint
                for constraint in pose_bone.constraints
                if constraint.type == "STRETCH_TO"
            ]
            assert len(stretch) == 1, "missing STRETCH_TO on %s" % name
            constraint = stretch[0]
            assert constraint.name == "FlexForge Stretch", constraint.name
            assert constraint.target == armature, constraint.target
            assert constraint.subtarget == "forearm.L", constraint.subtarget
            assert abs(constraint.head_tail) < 1e-6, constraint.head_tail
            assert constraint.volume == "VOLUME_XZX", constraint.volume
            assert abs(constraint.bulge - 2.5) < 1e-6, constraint.bulge
        cls = muscle.FLEXFORGE_OT_create_biceps
        assert "bulge" in cls.__annotations__, cls.__annotations__
    finally:
        _destroy_armature(armature)

    if fake:
        return

    # Real Blender: the registered operator itself must create the constraints.
    import flexforge

    armature = _create_armature()
    flexforge.register()
    try:
        result = bpy.ops.flexforge.create_biceps(bulge=1.5)
        assert result == {"FINISHED"}, result
        for name in ("muscle_biceps_01", "muscle_biceps_02"):
            stretch = [
                constraint
                for constraint in armature.pose.bones[name].constraints
                if constraint.type == "STRETCH_TO"
            ]
            assert len(stretch) == 1, "operator missing STRETCH_TO on %s" % name
            assert abs(stretch[0].bulge - 1.5) < 1e-6, stretch[0].bulge
    finally:
        flexforge.unregister()
        _destroy_armature(armature)


def test_tiny_rig_segments_get_the_span_cap():
    """Regression: a 0.0063 rig chain must not keep its body-sized envelope.

    The rig reports a 0.1 envelope on 0.0063 helpers, and 0.1 is 85% of the
    0.1179 mesh diagonal: uncapped the helper takes the forearm weight. The cap
    follows the helper span at any mesh scale, so a normal 0.25 helper keeps
    its 0.05 envelope while the tiny one drops to its own span.
    """
    from flexforge import muscle, muscle_skinning

    tiny = muscle.compute_segments((0.0, 0.0, 0.0), (0.0, 0.0, 0.0063), 2)
    head, tail = tiny[0]
    span = sum((tail[axis] - head[axis]) ** 2 for axis in range(3)) ** 0.5
    assert abs(span - 0.00315) < 1e-9, span
    tiny_radius = muscle_skinning._capsule_radius(0.1, head, tail, span)
    assert tiny_radius <= 0.5 * span, tiny_radius
    assert tiny_radius < 0.1, tiny_radius
    # A mesh-space helper of a normal rig keeps the reported 0.05 envelope.
    normal = muscle.compute_segments((0.0, 0.0, 1.5), (0.0, 0.0, 1.0), 2)
    normal_head, normal_tail = normal[0]
    normal_span = sum(
        (normal_tail[axis] - normal_head[axis]) ** 2 for axis in range(3)
    ) ** 0.5
    assert abs(normal_span - 0.25) < 1e-9, normal_span
    normal_radius = muscle_skinning._capsule_radius(
        0.05, normal_head, normal_tail, normal_span
    )
    assert abs(normal_radius - 0.05) < 1e-9, normal_radius


def _main():
    _install_bpy_stub()

    tests = [
        test_default_spec,
        test_chain_created,
        test_interpolated_geometry,
        test_chain_stops_at_insertion_head,
        test_use_deform_and_parent,
        test_custom_segments,
        test_missing_bone_error,
        test_invalid_segments_error,
        test_operator_registered,
        test_pose_constraints_created,
        test_tiny_rig_segments_get_the_span_cap,
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
