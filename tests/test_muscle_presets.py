# Deterministic headless test of the FlexForge muscle preset catalog.
# No external dependency: if bpy is not available the shared stub is installed,
# and the armature is either a fake object or a real one created in code.

import sys
import types
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

PRESET_IDS = (
    "biceps",
    "triceps",
    "deltoid",
    "pectoral",
    "latissimus",
    "quadriceps",
    "hamstring",
    "calf",
    "gluteus",
)


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


def _is_fake():
    import bpy

    return hasattr(bpy, "_registrate")


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

    def __init__(self, names=()):
        self._bones = {}
        for name in names:
            self.add(name)

    def add(self, name):
        index = float(len(self._bones) + 1)
        bone = _FakeBone(name, (0.0, 0.0, index), (0.0, 0.0, index - 0.5))
        self._bones[name] = bone
        return bone

    def new(self, name):
        if name in self._bones:
            raise RuntimeError("duplicate bone: %s" % name)
        return self.add(name)

    def get(self, name):
        return self._bones.get(name)

    def __iter__(self):
        return iter(self._bones.values())

    def __len__(self):
        return len(self._bones)


def _bone_geometry(index):
    """Deterministic head/tail for the index-th bone of the test rig."""
    value = float(index) + 1.0
    return (0.0, 0.0, value), (0.0, 0.0, value - 0.5)


def _make_armature(names=("upper_arm.L", "forearm.L")):
    """Create the test armature: real bpy if present, otherwise fake.

    The real armature is left in Edit Mode, ready for the chain creation.
    """
    import bpy

    if _is_fake():
        return types.SimpleNamespace(
            name="FakeRig",
            type="ARMATURE",
            data=types.SimpleNamespace(edit_bones=_FakeBones(names)),
        )

    data = bpy.data.armatures.new("FlexForgePresetRig")
    obj = bpy.data.objects.new("FlexForgePresetRig", data)
    bpy.context.scene.collection.objects.link(obj)
    for other in bpy.context.view_layer.objects:
        other.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="EDIT")
    for index, name in enumerate(names):
        head, tail = _bone_geometry(index)
        bone = data.edit_bones.new(name)
        bone.head = head
        bone.tail = tail
    return obj


def _drop_armature(armature):
    """Switch back to Object Mode and delete the real test armature."""
    import bpy

    if _is_fake():
        return
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    data = armature.data
    bpy.data.objects.remove(armature, do_unlink=True)
    bpy.data.armatures.remove(data)


def test_catalog_presets():
    from flexforge import muscle, muscle_presets

    assert len(muscle_presets.MUSCLE_PRESETS) == 9, list(
        muscle_presets.MUSCLE_PRESETS
    )
    assert set(muscle_presets.MUSCLE_PRESETS) == set(PRESET_IDS), sorted(
        muscle_presets.MUSCLE_PRESETS
    )
    for preset_id, spec in muscle_presets.MUSCLE_PRESETS.items():
        assert isinstance(spec, muscle.MuscleSpec), preset_id
        assert spec.name == preset_id, (preset_id, spec.name)
        assert spec.origin_bone, preset_id
        assert spec.insertion_bone, preset_id
        assert spec.origin_bone != spec.insertion_bone, preset_id
        assert muscle.SEGMENTS_MIN <= spec.segments <= muscle.SEGMENTS_MAX, spec
        assert spec.bulge > 0.0, preset_id


def test_custom_spec():
    from flexforge import muscle_presets

    spec = muscle_presets.preset_spec(
        "custom",
        custom_name="soleus",
        origin_bone="shin.L",
        insertion_bone="foot.L",
        segments=3,
        bulge=1.7,
    )
    assert spec.name == "soleus", spec.name
    assert spec.origin_bone == "shin.L", spec.origin_bone
    assert spec.insertion_bone == "foot.L", spec.insertion_bone
    assert spec.segments == 3, spec.segments
    assert abs(spec.bulge - 1.7) < 1e-6, spec.bulge

    defaults = muscle_presets.preset_spec(
        "custom", custom_name="tiny", origin_bone="a.L", insertion_bone="b.L"
    )
    assert defaults.segments == 2, defaults.segments
    assert abs(defaults.bulge - 1.0) < 1e-6, defaults.bulge


def test_custom_invalid():
    from flexforge import muscle, muscle_presets

    cases = (
        dict(custom_name="", origin_bone="a.L", insertion_bone="b.L"),
        dict(custom_name="x", origin_bone="", insertion_bone="b.L"),
        dict(custom_name="x", origin_bone="a.L", insertion_bone="  "),
        dict(
            custom_name="x",
            origin_bone="a.L",
            insertion_bone="b.L",
            segments=99,
        ),
    )
    for case in cases:
        try:
            muscle_presets.preset_spec("custom", **case)
        except muscle.MuscleError:
            pass
        else:
            raise AssertionError("expected MuscleError for %r" % (case,))


def test_preset_override():
    from flexforge import muscle_presets

    base = muscle_presets.MUSCLE_PRESETS["pectoral"]
    spec = muscle_presets.preset_spec("pectoral")
    assert spec.name == base.name, spec.name
    assert spec.origin_bone == base.origin_bone, spec.origin_bone
    assert spec.segments == base.segments, spec.segments

    overridden = muscle_presets.preset_spec(
        "pectoral", insertion_bone="hand.L", segments=4, bulge=2.0
    )
    assert overridden.name == "pectoral", overridden.name
    assert overridden.origin_bone == base.origin_bone, overridden.origin_bone
    assert overridden.insertion_bone == "hand.L", overridden.insertion_bone
    assert overridden.segments == 4, overridden.segments
    assert abs(overridden.bulge - 2.0) < 1e-6, overridden.bulge


def test_unknown_preset():
    from flexforge import muscle, muscle_presets

    try:
        muscle_presets.preset_spec("nope")
    except muscle.MuscleError as error:
        assert "nope" in str(error), str(error)
    else:
        raise AssertionError("expected MuscleError for an unknown preset")


def test_mirror_spec_lr():
    from flexforge import muscle_presets

    spec = muscle_presets.preset_spec("biceps")
    mirrored = muscle_presets.mirror_spec_lr(spec)
    assert mirrored.name == "biceps_r", mirrored.name
    assert mirrored.origin_bone == "upper_arm.R", mirrored.origin_bone
    assert mirrored.insertion_bone == "forearm.R", mirrored.insertion_bone
    assert mirrored.segments == spec.segments, mirrored.segments
    assert mirrored.name != spec.name, "mirror returned the same name"
    # Already mirrored specs keep a single suffix.
    again = muscle_presets.mirror_spec_lr(mirrored)
    assert again.name == "biceps_r", again.name
    assert again.origin_bone == "upper_arm.L", again.origin_bone
    # Central bones (spine.*) stay unchanged.
    pectoral = muscle_presets.mirror_spec_lr(
        muscle_presets.preset_spec("pectoral")
    )
    assert pectoral.origin_bone == "spine.002", pectoral.origin_bone
    assert pectoral.insertion_bone == "upper_arm.R", pectoral.insertion_bone


def test_create_preset_muscles():
    from flexforge import muscle_presets

    armature = _make_armature(("upper_arm.L", "forearm.L"))
    try:
        created = muscle_presets.create_preset_muscles(armature, "biceps")
        assert len(created) == 1, len(created)
        spec, names = created[0]
        assert spec.name == "biceps", spec.name
        assert names == ["muscle_biceps_01", "muscle_biceps_02"], names
        bones = armature.data.edit_bones
        for name in names:
            assert bones.get(name) is not None, "missing bone: %s" % name
    finally:
        _drop_armature(armature)


def test_create_preset_muscles_missing_bone():
    from flexforge import muscle, muscle_presets

    armature = _make_armature(("thigh.L",))
    try:
        try:
            muscle_presets.create_preset_muscles(armature, "biceps")
        except muscle.MuscleError as error:
            assert "forearm.L" in str(error) or "upper_arm.L" in str(error), str(
                error
            )
        else:
            raise AssertionError("expected MuscleError for a missing bone")
        assert armature.data.edit_bones.get("muscle_biceps_01") is None, (
            "chain created despite the error"
        )
    finally:
        _drop_armature(armature)


def test_all_available():
    from flexforge import muscle_presets

    armature = _make_armature(("upper_arm.L", "forearm.L"))
    try:
        created = muscle_presets.create_preset_muscles(
            armature, muscle_presets.ALL_PRESETS
        )
        names = sorted(spec.name for spec, _ in created)
        # Only presets whose origin and insertion bones exist are created.
        assert names == ["biceps", "triceps"], names
        bones = armature.data.edit_bones
        assert bones.get("muscle_biceps_01") is not None
        assert bones.get("muscle_triceps_03") is not None
        assert bones.get("muscle_pectoral_01") is None, "pectoral created anyway"
        assert bones.get("muscle_calf_01") is None, "calf created anyway"
    finally:
        _drop_armature(armature)


def test_all_available_nothing_matches():
    from flexforge import muscle, muscle_presets

    armature = _make_armature(("root",))
    try:
        try:
            muscle_presets.create_preset_muscles(
                armature, muscle_presets.ALL_PRESETS
            )
        except muscle.MuscleError as error:
            assert "preset" in str(error).lower(), str(error)
        else:
            raise AssertionError("expected MuscleError with no matching preset")
    finally:
        _drop_armature(armature)


def test_mirror_lr_creates_right_side():
    from flexforge import muscle, muscle_presets

    both = (
        "upper_arm.L",
        "forearm.L",
        "upper_arm.R",
        "forearm.R",
    )
    armature = _make_armature(both)
    try:
        created = muscle_presets.create_preset_muscles(
            armature, "biceps", mirror_lr=True
        )
        names = sorted(spec.name for spec, _ in created)
        assert names == ["biceps", "biceps_r"], names
        bones = armature.data.edit_bones
        assert bones.get("muscle_biceps_01") is not None
        assert bones.get("muscle_biceps_r_01") is not None
        assert bones.get("muscle_biceps_r_02") is not None
        mirrored = [spec for spec, _ in created if spec.name == "biceps_r"][0]
        assert mirrored.origin_bone == "upper_arm.R", mirrored.origin_bone
        assert mirrored.insertion_bone == "forearm.R", mirrored.insertion_bone
    finally:
        _drop_armature(armature)


def test_mirror_lr_missing_right_side():
    from flexforge import muscle, muscle_presets

    armature = _make_armature(("upper_arm.L", "forearm.L"))
    try:
        try:
            muscle_presets.create_preset_muscles(
                armature, "biceps", mirror_lr=True
            )
        except muscle.MuscleError as error:
            assert ".R" in str(error), str(error)
        else:
            raise AssertionError("expected MuscleError for a missing right side")
        # Nothing must be left behind from the left side either.
        assert armature.data.edit_bones.get("muscle_biceps_01") is None, (
            "left chain created before the mirror failed"
        )
    finally:
        _drop_armature(armature)


class _FakeConstraints(list):
    """Minimal constraint collection with `new()` for the fake pose bones."""

    def new(self, type):
        constraint = types.SimpleNamespace(type=type, name="")
        self.append(constraint)
        return constraint


def test_pose_constraints():
    import bpy

    from flexforge import muscle_presets

    fake = _is_fake()
    armature = _make_armature(("upper_arm.L", "forearm.L"))
    try:
        created = muscle_presets.create_preset_muscles(
            armature, "biceps", bulge=2.5
        )
        names = [name for _, chain in created for name in chain]
        if fake:
            armature.pose = types.SimpleNamespace(bones={})
            armature.pose.bones = {
                name: types.SimpleNamespace(constraints=_FakeConstraints())
                for name in names
            }
        else:
            bpy.ops.object.mode_set(mode="OBJECT")
        handled = muscle_presets.setup_preset_constraints(armature, created)
        assert handled == len(names), handled
        for name in names:
            stretch = [
                constraint
                for constraint in armature.pose.bones[name].constraints
                if constraint.type == "STRETCH_TO"
            ]
            assert len(stretch) == 1, "missing STRETCH_TO on %s" % name
            constraint = stretch[0]
            assert constraint.subtarget == "forearm.L", constraint.subtarget
            assert constraint.volume == "VOLUME_XZX", constraint.volume
            assert abs(constraint.bulge - 2.5) < 1e-6, constraint.bulge
    finally:
        _drop_armature(armature)


def test_operator_definition():
    from flexforge import muscle_presets

    cls = muscle_presets.FLEXFORGE_OT_create_muscle_preset
    assert cls.bl_idname == "flexforge.create_muscle_preset", cls.bl_idname
    assert cls.bl_label == "Create muscle preset", cls.bl_label
    for prop in ("preset", "mirror_lr", "segments", "bulge"):
        assert prop in cls.__annotations__, prop


def test_operator_execute():
    import bpy

    from flexforge import muscle_presets

    if _is_fake():
        # Same pattern as test_muscle: the stub has no real operator stack.
        return

    armature = _make_armature(("upper_arm.L", "forearm.L"))
    bpy.utils.register_class(muscle_presets.FLEXFORGE_OT_create_muscle_preset)
    try:
        result = bpy.ops.flexforge.create_muscle_preset(
            preset="biceps", segments=3
        )
        assert result == {"FINISHED"}, result
        names = ["muscle_biceps_0%d" % index for index in (1, 2, 3)]
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for name in names:
            assert armature.data.bones.get(name) is not None, name
            stretch = [
                constraint
                for constraint in armature.pose.bones[name].constraints
                if constraint.type == "STRETCH_TO"
            ]
            assert len(stretch) == 1, "operator missing STRETCH_TO on %s" % name
    finally:
        bpy.utils.unregister_class(
            muscle_presets.FLEXFORGE_OT_create_muscle_preset
        )
        _drop_armature(armature)


def _main():
    _install_bpy_stub()

    tests = [
        test_catalog_presets,
        test_custom_spec,
        test_custom_invalid,
        test_preset_override,
        test_unknown_preset,
        test_mirror_spec_lr,
        test_create_preset_muscles,
        test_create_preset_muscles_missing_bone,
        test_all_available,
        test_all_available_nothing_matches,
        test_mirror_lr_creates_right_side,
        test_mirror_lr_missing_right_side,
        test_pose_constraints,
        test_operator_definition,
        test_operator_execute,
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
