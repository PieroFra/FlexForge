# Deterministic headless test of the FlexForge muscle capsule skinning.
# No external dependency: if bpy is missing the shared stub is installed;
# the test mesh and armature are fake (same minimal interface as
# Mesh/VertexGroup/Bone) and work identically inside Blender too.

import math
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

    return install_bpy_stub(props_default=True, con_ops=True)


_install_bpy_stub()

import bpy  # noqa: E402

from flexforge import muscle_skinning, verify  # noqa: E402


class _FakeGroupElement:
    """Minimal element of `MeshVertex.groups`."""

    def __init__(self, group, weight):
        self.group = group
        self.weight = weight


class _FakeGroup:
    """Fake VertexGroup that writes into the mesh weight map."""

    def __init__(self, mesh, name, index):
        self._mesh = mesh
        self.name = name
        self.index = index

    def add(self, indices, weight, mode="REPLACE"):
        for index in indices:
            self._mesh.weights.setdefault(index, {})[self.index] = weight

    def remove(self, indices):
        for index in indices:
            self._mesh.weights.setdefault(index, {}).pop(self.index, None)


class _FakeGroups(list):
    """Fake VertexGroups collection exposing `new(name=...)`."""

    def __init__(self, mesh, names=()):
        super().__init__()
        self._mesh = mesh
        for name in names:
            self.new(name)

    def new(self, name):
        group = _FakeGroup(self._mesh, name, len(self))
        self.append(group)
        return group


class _FakeVertex:
    """Fake vertex exposing `groups` by reading the mesh weight map."""

    def __init__(self, mesh, index, coordinate):
        self._mesh = mesh
        self.index = index
        self.co = coordinate

    @property
    def groups(self):
        present = self._mesh.weights.get(self.index, {})
        return [
            _FakeGroupElement(index, weight)
            for index, weight in sorted(present.items())
        ]


class _FakeObject:
    """Fake mesh object with coordinates, vertex groups and modifiers."""

    def __init__(self, coordinates, groups=(), modifiers=()):
        self.type = "MESH"
        self.parent = None
        self.modifiers = list(modifiers)
        self.weights = {}
        self.vertex_groups = _FakeGroups(self, groups)
        self.data = types.SimpleNamespace(
            vertices=[
                _FakeVertex(self, index, coordinate)
                for index, coordinate in enumerate(coordinates)
            ]
        )

    def weights_by_name(self, vertex):
        names = {group.index: group.name for group in self.vertex_groups}
        return {
            names[index]: weight
            for index, weight in self.weights.get(vertex, {}).items()
        }

    def set_weights(self, vertex, values):
        """Write the initial weights of a vertex, by group name."""
        indices = {group.name: group.index for group in self.vertex_groups}
        self.weights[vertex] = {
            indices[name]: weight for name, weight in values.items()
        }

    def group_names(self):
        return [group.name for group in self.vertex_groups]


class _FakeBone:
    """Fake bone with local head/tail (or only the global fallback)."""

    def __init__(self, name, head, tail, use_deform=True, local=True,
                 parent=None, head_radius=None, tail_radius=None):
        self.name = name
        self.use_deform = use_deform
        self.head = head
        self.tail = tail
        self.parent = parent
        self.head_radius = head_radius
        self.tail_radius = tail_radius
        if local:
            self.head_local = head
            self.tail_local = tail


class _FakeArmature:
    """Fake armature exposing the bones list."""

    def __init__(self, bones):
        self.type = "ARMATURE"
        self.data = types.SimpleNamespace(bones=list(bones))


def _armature_modifier(armature):
    return types.SimpleNamespace(type="ARMATURE", object=armature)


def test_segment_distance_midpoint_and_endpoints():
    head = (0.0, 0.0, 0.0)
    tail = (0.0, 2.0, 0.0)
    assert abs(muscle_skinning.segment_distance((0.0, 0.0, 0.0), head, tail)) < 1e-9
    assert abs(muscle_skinning.segment_distance((1.0, 1.0, 0.0), head, tail) - 1.0) < 1e-9
    assert abs(muscle_skinning.segment_distance((0.0, 2.0, 0.0), head, tail)) < 1e-9


def test_segment_distance_clamped_and_degenerate():
    head = (0.0, 0.0, 0.0)
    tail = (0.0, 2.0, 0.0)
    # Beyond the tail: the distance is measured from the tail itself.
    assert abs(muscle_skinning.segment_distance((0.0, 5.0, 0.0), head, tail) - 3.0) < 1e-9
    # Before the head: the distance is measured from the head itself.
    assert abs(muscle_skinning.segment_distance((0.0, -1.0, 0.0), head, tail) - 1.0) < 1e-9
    # Degenerate segment: a single point.
    assert abs(muscle_skinning.segment_distance((3.0, 4.0, 0.0), head, head) - 5.0) < 1e-9


def test_capsule_weight_falloff():
    head = (0.0, 0.0, 0.0)
    tail = (0.0, 1.0, 0.0)
    radius = 0.15
    assert abs(muscle_skinning.capsule_weight(head, head, tail, radius) - 1.0) < 1e-9
    expected = (1.0 - 0.05 / radius) ** 2
    assert abs(expected - 4.0 / 9.0) < 1e-9, expected
    got = muscle_skinning.capsule_weight((0.05, 0.5, 0.0), head, tail, radius)
    assert abs(got - expected) < 1e-9, got
    assert muscle_skinning.capsule_weight((0.15, 0.5, 0.0), head, tail, radius) == 0.0
    assert muscle_skinning.capsule_weight((1.0, 0.5, 0.0), head, tail, radius) == 0.0
    # The per-capsule radius comes from the bone envelope, the larger of the two.
    bone = types.SimpleNamespace(head_radius=0.04, tail_radius=0.09)
    assert abs(muscle_skinning.bone_radius(bone) - 0.09) < 1e-9
    empty = types.SimpleNamespace()
    assert muscle_skinning.bone_radius(empty) == (
        muscle_skinning.DEFAULT_BONE_RADIUS
    ), muscle_skinning.bone_radius(empty)


def test_capsule_weight_invalid_radius():
    error = None
    try:
        muscle_skinning.capsule_weight((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), 0.0)
    except muscle_skinning.SkinningError as exception:
        error = exception
    assert error is not None, "expected SkinningError with radius=0"
    assert "radius" in str(error), str(error)


def test_compute_muscle_weights_basic():
    segments = {"muscle_a": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))}
    report = muscle_skinning.compute_muscle_weights(
        {}, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], segments
    )
    assert report["vertices"] == 2, report
    assert report["vertices_bound"] == 1, report
    assert report["muscles_bound"] == 1, report
    assert abs(report["weights"][0]["muscle_a"] - 1.0) < 1e-6, report["weights"]
    assert report["weights"][1] == {}, report["weights"]
    # A tighter bone radius beats the 0.15 fallback: the vertex at 0.10 from
    # the axis falls outside the 0.05 capsule and is not bound.
    tight = {
        "muscle_a": {
            "head_local": (0.0, 0.0, 0.0),
            "tail_local": (0.0, 1.0, 0.0),
            "radius": 0.05,
        }
    }
    tightened = muscle_skinning.compute_muscle_weights(
        {}, [(0.1, 0.5, 0.0)], tight
    )
    assert tightened["vertices_bound"] == 0, tightened
    assert tightened["weights"][0] == {}, tightened["weights"]


def test_compute_muscle_weights_keeps_existing():
    segments = {"muscle_a": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))}
    report = muscle_skinning.compute_muscle_weights(
        {0: {"arm.L": 0.5}}, [(0.0, 0.0, 0.0)], segments, intensity=0.5
    )
    written = report["weights"][0]
    assert abs(written["muscle_a"] - 0.5) < 1e-6, written
    assert abs(written["arm.L"] - 0.5) < 1e-6, written
    assert abs(sum(written.values()) - 1.0) < 1e-6, written
    # The mask keeps the capsule off the vertices weighted on other bones.
    masked = muscle_skinning.compute_muscle_weights(
        {0: {"arm.L": 0.5}, 1: {"leg.L": 1.0}},
        [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        segments,
        intensity=0.5,
        bone_masks={"muscle_a": ["arm.L", "chest"]},
    )
    assert "muscle_a" in masked["weights"][0], masked["weights"]
    assert "muscle_a" not in masked["weights"][1], masked["weights"]
    assert abs(masked["weights"][1]["leg.L"] - 1.0) < 1e-6, masked["weights"]
    # With no vertex on the origin/insertion bones the surface is kept whole.
    unmasked = muscle_skinning.compute_muscle_weights(
        {}, [(0.0, 0.0, 0.0)], segments, intensity=0.5,
        bone_masks={"muscle_a": ["arm.L"]},
    )
    assert abs(unmasked["weights"][0]["muscle_a"] - 1.0) < 1e-6, unmasked


def test_compute_muscle_weights_global_fallback():
    # Dict segments: head_local/tail_local win, head/tail are the fallback.
    segments = {
        "muscle_local": {
            "head_local": (0.0, 0.0, 0.0),
            "tail_local": (0.0, 1.0, 0.0),
        },
        "muscle_global": {"head": (0.0, 0.0, 0.0), "tail": (0.0, 1.0, 0.0)},
    }
    report = muscle_skinning.compute_muscle_weights(
        {}, [(0.0, 0.5, 0.0)], segments
    )
    written = report["weights"][0]
    assert set(written) == {"muscle_local", "muscle_global"}, written
    assert abs(sum(written.values()) - 1.0) < 1e-6, written


def test_tiny_helper_radius_capped():
    """Regression: a body-sized radius on a hair-thin helper steals the forearm.

    A rig reports a 0.1 envelope on 0.0002-long elbow helpers: uncapped, the
    capsule wraps the forearm and takes its weight away from the insertion bone.
    """
    segments = {
        "muscle_biceps_01": {
            "head_local": (0.0, 0.0, 0.0),
            "tail_local": (0.0, 0.0, 0.0002),
            "radius": 0.1,
        }
    }
    coordinates = [(-0.1, -0.1, -0.1), (0.1, 0.1, 0.1)]
    existing = {0: {"forearm.L": 1.0}, 1: {"forearm.L": 1.0}}
    report = muscle_skinning.compute_muscle_weights(
        existing, coordinates, segments
    )
    assert "muscle_biceps_01" not in report["weights"][0], report["weights"]
    assert "muscle_biceps_01" not in report["weights"][1], report["weights"]
    assert abs(report["weights"][0]["forearm.L"] - 1.0) < 1e-6, report["weights"]
    assert abs(report["weights"][1]["forearm.L"] - 1.0) < 1e-6, report["weights"]
    assert report["vertices_bound"] == 0, report


def test_compute_muscle_weights_respects_budget():
    segments = {
        "muscle_%d" % index: ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        for index in range(5)
    }
    report = muscle_skinning.compute_muscle_weights(
        {}, [(0.0, 0.0, 0.0)], segments, max_influences=2
    )
    written = report["weights"][0]
    assert len(written) == 2, written
    assert abs(sum(written.values()) - 1.0) < 1e-6, written


def test_apply_muscle_skinning_creates_groups():
    parent = _FakeBone("upper_arm.L", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    muscle = _FakeBone(
        "muscle_a", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), parent=parent,
        head_radius=0.05, tail_radius=0.05,
    )
    armature = _FakeArmature([parent, muscle])
    obj = _FakeObject(
        [(0.0, 0.0, 0.0), (0.1, 0.5, 0.0)],
        groups=("upper_arm.L", "spine"),
        modifiers=[_armature_modifier(armature)],
    )
    obj.set_weights(0, {"upper_arm.L": 1.0})
    obj.set_weights(1, {"spine": 1.0})
    report = muscle_skinning.apply_muscle_skinning(obj)
    assert "muscle_a" in obj.group_names(), obj.group_names()
    # Vertex 0 is on the capsule and weighted on the origin bone: the capsule
    # weight (1.0 * 0.5 intensity) is normalized against the existing 1.0.
    written = obj.weights_by_name(0)
    assert abs(written["muscle_a"] - 1.0 / 3.0) < 1e-6, written
    assert abs(written["upper_arm.L"] - 2.0 / 3.0) < 1e-6, written
    assert abs(sum(written.values()) - 1.0) < 1e-6, written
    # Vertex 1 is on another bone and outside the 0.05 bone radius.
    assert "muscle_a" not in obj.weights_by_name(1), obj.weights_by_name(1)
    assert abs(obj.weights_by_name(1)["spine"] - 1.0) < 1e-6, obj.weights_by_name(1)
    assert report["vertices_bound"] == 1, report
    assert report["muscles_bound"] == 1, report


def test_apply_muscle_skinning_uses_global_fallback_bone():
    bone = _FakeBone(
        "muscle_a", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), local=False
    )
    armature = _FakeArmature([bone])
    obj = _FakeObject([(0.0, 0.0, 0.0)], modifiers=[_armature_modifier(armature)])
    report = muscle_skinning.apply_muscle_skinning(obj, armature=armature)
    assert report["vertices_bound"] == 1, report
    assert abs(obj.weights_by_name(0)["muscle_a"] - 1.0) < 1e-6, obj.weights_by_name(0)


def test_apply_muscle_skinning_errors():
    def _fails(call):
        try:
            call()
        except muscle_skinning.SkinningError as error:
            return str(error)
        return None

    assert _fails(lambda: muscle_skinning.apply_muscle_skinning(None)) is not None
    empty = _FakeObject([(0.0, 0.0, 0.0)])
    message = _fails(lambda: muscle_skinning.apply_muscle_skinning(empty))
    assert message is not None and "armature" in message, message
    armature = _FakeArmature([_FakeBone("spine", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))])
    obj = _FakeObject([(0.0, 0.0, 0.0)], modifiers=[_armature_modifier(armature)])
    message = _fails(lambda: muscle_skinning.apply_muscle_skinning(obj))
    assert message is not None and "helper bones" in message, message
    message = _fails(
        lambda: muscle_skinning.apply_muscle_skinning(obj, radius=0.0)
    )
    assert message is not None and "radius" in message, message


def test_apply_muscle_skinning_rejects_non_armature():
    """Regression: a non-armature object must not pass as the rig.

    The bind reads `armature.data.bones`: an object without the ARMATURE type
    (a mesh, an empty) used to reach the bone loop and fail far from the cause.
    """
    obj = _FakeObject([(0.0, 0.0, 0.0)], groups=("spine",))
    error = None
    try:
        muscle_skinning.apply_muscle_skinning(
            obj, armature=types.SimpleNamespace(type="MESH")
        )
    except muscle_skinning.SkinningError as exception:
        error = exception
    assert error is not None, "expected SkinningError for a non-armature"
    assert "armature" in str(error), str(error)
    # A bare object with no `type` at all is rejected the same way.
    try:
        muscle_skinning.apply_muscle_skinning(
            obj, armature=types.SimpleNamespace()
        )
    except muscle_skinning.SkinningError as exception:
        assert "armature" in str(exception), str(exception)
    else:
        raise AssertionError("a non-armature object must be rejected")


def test_capsule_weights_drive_muscle_shape():
    """The capsule mask is what keeps the shape deltas one-hot."""
    from flexforge import muscle_shape

    segments = {"muscle_a": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))}
    coordinates = [(0.05, 0.5, 0.0), (0.5, 0.5, 0.0)]
    report = muscle_skinning.compute_muscle_weights(
        {}, coordinates, segments, radius=0.15
    )
    # The far vertex is outside the capsule: no weight, therefore no delta.
    assert report["weights"][1] == {}, report["weights"]
    deltas = muscle_shape.compute_muscle_shape_deltas(
        dict(enumerate(coordinates)), report["weights"], segments, 0.045
    )
    assert sorted(deltas["muscle_a"]) == [0], deltas
    delta = deltas["muscle_a"][0]
    assert abs(delta[0] - 0.03) < 1e-9, delta  # single muscle, 0.3 * 0.1 cap
    assert abs(delta[1]) < 1e-9 and abs(delta[2]) < 1e-9, delta


def test_validate_deformation_integration():
    segments = {
        "muscle_a": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        "muscle_b": ((1.0, 0.0, 0.0), (1.0, 1.0, 0.0)),
    }
    report = muscle_skinning.compute_muscle_weights(
        {}, [(0.0, 0.5, 0.0), (1.0, 0.5, 0.0)], segments
    )
    verdict = verify.validate_deformation(report["weights"], ["muscle_a", "muscle_b"])
    assert verdict["valid"] is True, verdict
    assert verdict["helpers_present"] == 2, verdict
    assert verdict["over_budget"] == 0, verdict


def test_is_excluded_bone():
    for name in ("foot.L", "toe.R", "ankle.L", "shin.L", "calf.R", "tibia_01",
                 "LeftLeg", "upper_leg.L"):
        assert muscle_skinning.is_excluded_bone(name), name
    for name in ("thigh.L", "quadriceps", "spine", "muscle_quad_01"):
        assert not muscle_skinning.is_excluded_bone(name), name
    # Explicit tokens win over the leg default.
    assert not muscle_skinning.is_excluded_bone("foot.L", ("hand",))
    assert muscle_skinning.is_excluded_bone("hand.L", ("hand",))


def test_compute_muscle_weights_excludes_foot():
    segments = {"muscle_quad": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))}
    coordinates = [(0.0, 0.5, 0.0), (0.0, 1.0, 0.0)]
    existing = {0: {"thigh.L": 1.0}, 1: {"foot.L": 0.6, "toe.L": 0.4}}
    report = muscle_skinning.compute_muscle_weights(
        existing, coordinates, segments,
        exclude_tokens=muscle_skinning.FOOT_EXCLUDE_TOKENS,
    )
    assert "muscle_quad" in report["weights"][0], report["weights"]
    assert "muscle_quad" not in report["weights"][1], report["weights"]
    assert abs(report["weights"][1]["foot.L"] - 0.6) < 1e-6, report["weights"]
    assert report["vertices_bound"] == 1, report
    assert report["muscles_bound"] == 1, report
    # Without the exclusion the helper bleeds on the foot vertex.
    leaked = muscle_skinning.compute_muscle_weights(existing, coordinates, segments)
    assert "muscle_quad" in leaked["weights"][1], leaked["weights"]


def test_exclude_keeps_the_owner_vertices():
    """Regression: the quadriceps_02/03 mask went empty after the subtraction.

    Owners `UpLeg`+`Leg` both carry the "leg" token, so every owner vertex was
    in the excluded set and the subtraction left an empty mask: the capsule
    bound nothing at all. A vertex already weighted on the muscle's own owners
    is kept, while a real shin vertex stays out.
    """
    assert muscle_skinning.is_excluded_bone("UpLeg.L"), "UpLeg.L"
    assert muscle_skinning.is_excluded_bone("Leg.L"), "Leg.L"
    head, tail = (0.0, 0.0, 0.0), (0.0, 0.0, 0.01)
    segments = {"muscle_quadriceps_02": {"head_local": head, "tail_local": tail,
                                         "radius": 0.1}}
    coordinates = [(0.0, 0.0, 0.005), (0.0, 0.0, 0.005)]
    existing = {0: {"UpLeg.L": 1.0}, 1: {"shin.L": 1.0}}
    report = muscle_skinning.compute_muscle_weights(
        existing, coordinates, segments,
        bone_masks={"muscle_quadriceps_02": ["UpLeg.L", "Leg.L"]},
        exclude_tokens=muscle_skinning.FOOT_EXCLUDE_TOKENS,
    )
    assert "muscle_quadriceps_02" in report["weights"][0], report["weights"]
    assert "muscle_quadriceps_02" not in report["weights"][1], report["weights"]
    assert abs(report["weights"][1]["shin.L"] - 1.0) < 1e-6, report["weights"]
    assert report["vertices_bound"] == 1, report


def test_body_scale_mesh_lifts_the_span_cap():
    """Regression: the mesh floor was min'd into the span cap, not applied.

    A 0.0063 helper on a 0.12-diagonal mesh capped the radius at 0.00315, below
    the 0.005 offset of the skin: no inner quadriceps vertex bound, only the
    biceps did. The floor is a lower bound now, so the capsule reaches the skin
    at a quarter of the mesh diagonal and still respects the `radius` ceiling.
    """
    head, tail = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0063)
    diagonal = 0.12
    lifted = muscle_skinning._capsule_radius(0.1, head, tail, 0.0063, diagonal)
    assert abs(lifted - 0.25 * diagonal) < 1e-9, lifted
    # Without the mesh scale the span cap alone stays below the skin distance.
    assert muscle_skinning._capsule_radius(0.1, head, tail, 0.0063) < 0.005
    assert muscle_skinning._capsule_radius(0.02, head, tail, 0.0063, diagonal) == 0.02
    segments = {"muscle_quadriceps_02": {"head_local": head, "tail_local": tail,
                                         "radius": 0.1}}
    existing = {0: {"UpLeg.L": 1.0}}
    report = muscle_skinning.compute_muscle_weights(
        existing, [(0.005, 0.0, 0.00315)], segments, mesh_diagonal=diagonal
    )
    assert "muscle_quadriceps_02" in report["weights"][0], report["weights"]
    assert abs(report["weights"][0]["UpLeg.L"]) < 1.0, report["weights"]
    assert report["vertices_bound"] == 1, report


def test_apply_muscle_skinning_excludes_foot():
    thigh = _FakeBone("thigh.L", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    shin = _FakeBone("shin.L", (0.0, 1.0, 0.0), (0.0, 2.0, 0.0), parent=thigh)
    foot = _FakeBone("foot.L", (0.0, 2.0, 0.0), (0.0, 2.0, 0.5), parent=shin)
    helper = _FakeBone(
        "muscle_quad", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), parent=thigh,
        head_radius=0.2, tail_radius=0.2,
    )
    armature = _FakeArmature([thigh, shin, foot, helper])
    obj = _FakeObject(
        [(0.0, 0.5, 0.0), (0.0, 1.5, 0.0), (0.0, 2.0, 0.1)],
        groups=("thigh.L", "shin.L", "foot.L"),
        modifiers=[_armature_modifier(armature)],
    )
    obj.set_weights(0, {"thigh.L": 1.0})
    obj.set_weights(1, {"shin.L": 1.0})
    obj.set_weights(2, {"foot.L": 1.0})
    owners = muscle_skinning._owner_bones(helper, [thigh, shin, foot, helper])
    assert owners == ["thigh.L", "shin.L"], owners
    report = muscle_skinning.apply_muscle_skinning(obj)
    assert "muscle_quad" in obj.weights_by_name(0), obj.weights_by_name(0)
    # The capsule stops at the knee insert (0.0, 1.0, 0.0): the shin vertex at
    # y=1.5 is 0.5 past it, beyond the 0.15 radius, and the foot vertex sits
    # outside the origin/insertion mask, so no squashed foot and no stiff ankle.
    assert "muscle_quad" not in obj.weights_by_name(1), obj.weights_by_name(1)
    assert "muscle_quad" not in obj.weights_by_name(2), obj.weights_by_name(2)
    assert abs(obj.weights_by_name(1)["shin.L"] - 1.0) < 1e-6, obj.weights_by_name(1)
    assert abs(obj.weights_by_name(2)["foot.L"] - 1.0) < 1e-6, obj.weights_by_name(2)
    assert report["vertices_bound"] == 1, report


def test_side_filter_drops_the_opposite_side():
    head = (0.0, 0.0, 0.0)
    tail = (1.0, 0.0, 0.0)
    assert muscle_skinning.side_direction(head, tail) == (1.0, 0.0, 0.0)
    assert muscle_skinning.side_direction(head, head) is None
    assert muscle_skinning.is_torso_bone("spine.002"), "spine.002"
    assert muscle_skinning.is_torso_bone("chest"), "chest"
    assert not muscle_skinning.is_torso_bone("upper_arm.L"), "upper_arm.L"
    # A torso capsule keeps only the vertices in front of the head plane.
    segments = {
        "muscle_pectoral": {
            "head_local": head,
            "tail_local": tail,
            "radius": 0.5,
            "side_filter": True,
        }
    }
    coordinates = [(0.5, 0.1, 0.0), (-0.2, 0.05, 0.0)]
    report = muscle_skinning.compute_muscle_weights({}, coordinates, segments)
    assert "muscle_pectoral" in report["weights"][0], report["weights"]
    assert "muscle_pectoral" not in report["weights"][1], report["weights"]
    assert report["vertices_bound"] == 1, report
    # Unchanged limbs: a plain capsule still binds both sides of its head.
    plain = {"muscle_pectoral": (head, tail)}
    leaked = muscle_skinning.compute_muscle_weights(
        {}, coordinates, plain, radius=0.5
    )
    assert "muscle_pectoral" in leaked["weights"][1], leaked["weights"]


def test_apply_muscle_skinning_torso_side_filter():
    spine = _FakeBone("spine.002", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    arm = _FakeBone("upper_arm.L", (1.0, 0.0, 0.0), (1.0, 1.0, 0.0))
    chest = _FakeBone(
        "muscle_pectoral", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), parent=spine,
        head_radius=0.5, tail_radius=0.5,
    )
    biceps = _FakeBone(
        "muscle_biceps", (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), parent=arm,
        head_radius=0.5, tail_radius=0.5,
    )
    armature = _FakeArmature([spine, arm, chest, biceps])
    obj = _FakeObject(
        [(0.5, 0.0, 0.0), (-0.3, 0.0, 0.0), (1.1, 0.5, 0.0), (0.9, 0.5, 0.0)],
        groups=("spine.002", "upper_arm.L"),
        modifiers=[_armature_modifier(armature)],
    )
    obj.set_weights(0, {"spine.002": 1.0})
    obj.set_weights(1, {"spine.002": 1.0})
    obj.set_weights(2, {"upper_arm.L": 1.0})
    obj.set_weights(3, {"upper_arm.L": 1.0})
    muscle_skinning.apply_muscle_skinning(obj)
    # The pectoral helper is born on the spine: the back vertex stays clean.
    assert "muscle_pectoral" in obj.weights_by_name(0), obj.weights_by_name(0)
    assert "muscle_pectoral" not in obj.weights_by_name(1), obj.weights_by_name(1)
    assert abs(obj.weights_by_name(1)["spine.002"] - 1.0) < 1e-6, obj.weights_by_name(1)
    # The biceps helper belongs to an arm: both sides of its capsule stay bound.
    assert "muscle_biceps" in obj.weights_by_name(2), obj.weights_by_name(2)
    assert "muscle_biceps" in obj.weights_by_name(3), obj.weights_by_name(3)


def test_apply_muscle_skinning_with_scaled_rotated_armature():
    """A rig with scale 0.01 and a 90 degree turn on X must still bind.

    Real FBX/GLB rigs (any Mixamo import) live in a different space than the
    mesh: the bone head/tail and the envelope have to travel through
    `mesh.matrix_world.inverted() @ armature.matrix_world`, otherwise the
    capsule sits at the origin of the mesh space and binds nothing.
    """
    from mathutils import Matrix

    armature_data = bpy.data.armatures.new("flexforge_skinned_rig")
    armature = bpy.data.objects.new("flexforge_skinned_rig", armature_data)
    bpy.context.scene.collection.objects.link(armature)
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    parent_bone = armature_data.edit_bones.new("upper_arm.L")
    parent_bone.head = (0.0, 0.0, 0.0)
    parent_bone.tail = (0.0, 10.0, 0.0)
    muscle_bone = armature_data.edit_bones.new("muscle_biceps_01")
    muscle_bone.head = (0.0, 0.0, 0.0)
    muscle_bone.tail = (0.0, 10.0, 0.0)
    muscle_bone.parent = parent_bone
    for bone in (parent_bone, muscle_bone):
        bone.head_radius = 2.0
        bone.tail_radius = 2.0
    bpy.ops.object.mode_set(mode="OBJECT")
    # 10 centimetres of armature become 0.1 m on the mesh, turned 90 degrees.
    armature.matrix_world = (Matrix.Rotation(math.pi / 2.0, 4, "X")
                             @ Matrix.Diagonal((0.01, 0.01, 0.01, 1.0)))

    mesh = bpy.data.meshes.new("flexforge_skinned_mesh")
    mesh.from_pydata(
        [(0.005, 0.0, 0.01), (0.005, 0.0, 0.05), (0.005, 0.0, 0.09)],
        [], [(0, 1), (1, 2)],
    )
    obj = bpy.data.objects.new("flexforge_skinned_mesh", mesh)
    bpy.context.scene.collection.objects.link(obj)
    assert tuple(obj.scale) == (1.0, 1.0, 1.0), tuple(obj.scale)
    parent_group = obj.vertex_groups.new(name="upper_arm.L")
    for index in range(3):
        parent_group.add([index], 1.0, "REPLACE")
    modifier = obj.modifiers.new(name="Armature", type="ARMATURE")
    modifier.object = armature

    try:
        report = muscle_skinning.apply_muscle_skinning(obj)
        assert report["vertices_bound"] > 0, report
        assert report["muscles_bound"] == 1, report
        names = {group.name for group in obj.vertex_groups}
        assert "muscle_biceps_01" in names, names
        by_index = {group.index: group.name for group in obj.vertex_groups}
        bound = [
            vertex.index for vertex in obj.data.vertices
            if any(by_index[element.group] == "muscle_biceps_01"
                   for element in vertex.groups)
        ]
        assert len(bound) == report["vertices_bound"], (bound, report)
    finally:
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.objects.remove(armature, do_unlink=True)
        bpy.data.meshes.remove(mesh)
        bpy.data.armatures.remove(armature_data)


def test_skinning_message():
    message = muscle_skinning.skinning_message(
        {"vertices": 8, "vertices_bound": 5, "muscles_bound": 2}
    )
    expected = "FlexForge - skinning: vertices=8 vertices_bound=5 muscles_bound=2"
    assert message == expected, message


def test_operator_properties():
    cls = muscle_skinning.FLEXFORGE_OT_bind_muscles
    assert cls.bl_idname == "flexforge.bind_muscles", cls.bl_idname
    assert cls.bl_label == "Bind muscles", cls.bl_label
    annotations = getattr(cls, "__annotations__", {})
    for name in ("radius", "intensity", "max_influences"):
        assert name in annotations, "missing property: %s" % name


def _fake_operator(radius=0.15, intensity=0.5, max_influences=4):
    class _Operator:
        execute = muscle_skinning.FLEXFORGE_OT_bind_muscles.execute

        def __init__(self, radius, intensity, max_influences):
            self.radius = radius
            self.intensity = intensity
            self.max_influences = max_influences
            self.reported = []

        def report(self, levels, message):
            self.reported.append((levels, message))

    return _Operator(radius, intensity, max_influences)


def _context(obj):
    return types.SimpleNamespace(
        view_layer=types.SimpleNamespace(objects=types.SimpleNamespace(active=obj))
    )


def test_operator_execute_cancelled():
    operator = _fake_operator()
    assert operator.execute(_context(None)) == {"CANCELLED"}, operator.reported
    assert operator.reported[0][0] == {"ERROR"}, operator.reported
    assert "active mesh" in operator.reported[0][1], operator.reported

    non_mesh = types.SimpleNamespace(type="EMPTY")
    operator = _fake_operator()
    assert operator.execute(_context(non_mesh)) == {"CANCELLED"}
    assert "active mesh" in operator.reported[0][1], operator.reported


def test_operator_execute_finished():
    armature = _FakeArmature(
        [_FakeBone("muscle_a", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))]
    )
    obj = _FakeObject([(0.0, 0.0, 0.0)], modifiers=[_armature_modifier(armature)])
    operator = _fake_operator()
    outcome = operator.execute(_context(obj))
    assert outcome == {"FINISHED"}, operator.reported
    assert operator.reported[0][0] == {"INFO"}, operator.reported
    assert "FlexForge - skinning" in operator.reported[0][1], operator.reported
    assert "muscles_bound=1" in operator.reported[0][1], operator.reported
    assert "muscle_a" in obj.group_names(), obj.group_names()


def test_chain_length_is_local_to_each_muscle():
    """Regression: the cap uses the muscle's own span, not the global max.

    A short `muscle_short` helper next to a far `muscle_far` one used to be
    capped by the 10+ unit span of the other capsule, so the quarter-chain cap
    read 2.7 and the short capsule wrapped vertices it must not reach. The cap
    is now local to the helper span, at any mesh scale.
    """
    segments = {
        "muscle_short": {
            "head_local": (0.0, 0.0, 0.0),
            "tail_local": (0.0, 0.0, 0.4),
            "radius": 0.15,
        },
        "muscle_far": {
            "head_local": (10.0, 0.0, 0.0),
            "tail_local": (10.0, 0.0, 4.0),
            "radius": 0.15,
        },
    }
    coordinates = [(0.05, 0.0, 0.2), (0.12, 0.0, 0.2), (600.0, 0.0, 0.0)]
    report = muscle_skinning.compute_muscle_weights({}, coordinates, segments)
    # Its own span 0.4 caps the radius at 0.1: 0.05 is inside, 0.12 outside.
    assert "muscle_short" in report["weights"][0], report["weights"]
    assert "muscle_short" not in report["weights"][1], report["weights"]
    assert "muscle_far" not in report["weights"][0], report["weights"]
    assert report["vertices_bound"] == 1, report


def test_tiny_helper_radius_follows_its_span():
    """Regression: the 0.1 envelope on a 0.0063 helper swallowed the forearm.

    The rig reports a body-sized 0.1 envelope on 0.0063 elbow helpers, and 0.1
    is 85% of the 0.1187 mesh diagonal: uncapped the capsule reached the whole
    forearm and took 64% of its weight from the insertion bone. The effective
    radius follows the helper span (0.0016), so the vertex at 0.02 keeps its
    insertion weight while the helper still binds its own vertices.
    """
    segments = {
        "muscle_elbow": {
            "head_local": (0.0, 0.0, 0.0),
            "tail_local": (0.0, 0.0, 0.0063),
            "radius": 0.1,
        }
    }
    coordinates = [(0.02, 0.0, 0.003), (0.1, 0.05, 0.04), (0.0, 0.0, 0.0063)]
    existing = {0: {"forearm.L": 1.0}}
    report = muscle_skinning.compute_muscle_weights(existing, coordinates, segments)
    assert "muscle_elbow" not in report["weights"][0], report["weights"]
    assert abs(report["weights"][0]["forearm.L"] - 1.0) < 1e-6, report["weights"]
    assert report["weights"][1] == {}, report["weights"]
    assert abs(report["weights"][2]["muscle_elbow"] - 1.0) < 1e-6, report["weights"]
    assert report["vertices_bound"] == 1, report


def test_compute_muscle_weights_keeps_the_joint_bone():
    """Regression: the helpers must not evict the joint bone over the budget.

    The capsule adds its weight on top of three bone influences; with a
    3-influence budget `limit_influences` kept the two strongest bones plus the
    helper and dropped the weakest one, so the knee lost its joint bone. The
    helpers now fill only the spare slots: none here, one with a 4 budget.
    """
    segments = {"muscle_a": {"head_local": (0.0, 0.0, 0.0),
                             "tail_local": (0.0, 1.0, 0.0), "radius": 0.5}}
    existing = {0: {"upper_arm.L": 0.6, "forearm.L": 0.3, "hand.L": 0.1}}
    report = muscle_skinning.compute_muscle_weights(
        existing, [(0.0, 0.5, 0.0)], segments, intensity=1.0, max_influences=3
    )
    written = report["weights"][0]
    assert "hand.L" in written, written
    assert abs(written["hand.L"] - 0.1) < 1e-6, written
    assert "muscle_a" not in written, written
    assert abs(sum(written.values()) - 1.0) < 1e-6, written
    spare = muscle_skinning.compute_muscle_weights(
        existing, [(0.0, 0.5, 0.0)], segments, intensity=1.0, max_influences=4
    )
    assert "muscle_a" in spare["weights"][0], spare["weights"]
    assert abs(sum(spare["weights"][0].values()) - 1.0) < 1e-6, spare["weights"]


def test_capsule_radius_keeps_span_cap_on_human_scale():
    """Regression: the mesh floor must not bloat the capsule on a human mesh.

    On a 2 m diagonal a quarter of the diagonal is 0.5, so the floor would raise
    a 0.0315 span cap to the full 0.1 helper radius and the biceps/triceps would
    invade the forearms. The floor only applies to tiny-scale meshes.
    """
    head, tail = (0.0, 0.0, 0.0), (0.0, 0.0, 0.126)
    radius = muscle_skinning._capsule_radius(0.1, head, tail, 0.126, 2.15)
    assert abs(radius - 0.25 * 0.126) < 1e-9, radius
    assert radius == 0.25 * 0.126, radius


def test_sixteen_helpers_bind_on_a_body_scale_mesh():
    """Regression: a 0.0016 cap on a 0.12 mesh binds no vertex at all.

    The rig reports 0.1 envelopes on 0.0063 elbow helpers on a mesh whose
    local diagonal is 0.12: the quarter-span cap read 0.0016, below the
    0.0019 bone-to-skin distance, so all 16 helpers stayed at n_in = 0 and
    the bind reported 0 vertices. The cap now has a floor at a quarter of the
    mesh diagonal, so the same helpers reach the skin at 0.002 from its axis.
    That floor is a lower bound, not a second cap: the radius reaches 0.03 and
    the capsules overlap, so each vertex keeps its nearest helper plus the two
    next strongest within the budget instead of exactly one helper.
    """
    parent = _FakeBone("forearm.L", (0.0, 0.0, 0.0), (0.0, 0.0, 0.1))
    helpers = []
    coordinates = []
    for index in range(16):
        start = index * 0.008
        helpers.append(_FakeBone(
            "muscle_%02d" % index, (0.0, 0.0, start),
            (0.0, 0.0, start + 0.0063), parent=parent,
            head_radius=0.1, tail_radius=0.1,
        ))
        coordinates.append((0.002, 0.0, start + 0.00315))
    # Red on the old cap: 0.25 * 0.0063 = 0.0016 < the 0.002 offset, so the
    # span alone keeps the capsule off the skin; only the mesh floor lifts it.
    tight = muscle_skinning._capsule_radius(
        0.1, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0063), 0.0063
    )
    assert tight < 0.002, tight
    assert 0.25 * muscle_skinning._mesh_diagonal(coordinates) > 0.002
    armature = _FakeArmature([parent] + helpers)
    obj = _FakeObject(
        coordinates, groups=("forearm.L",),
        modifiers=[_armature_modifier(armature)],
    )
    for index in range(len(coordinates)):
        obj.set_weights(index, {"forearm.L": 1.0})
    report = muscle_skinning.apply_muscle_skinning(obj)
    counts = {bone.name: 0 for bone in helpers}
    for groups in report["weights"].values():
        for name in counts:
            if groups.get(name, 0.0) > 0.0:
                counts[name] += 1
    assert report["vertices_bound"] == 16, report["vertices_bound"]
    assert report["muscles_bound"] == 16, report["muscles_bound"]
    assert all(count > 0 for count in counts.values()), counts
    # The half-span cap (0.00315) is below the floor, so the mesh floor lifts
    # the radius to a quarter of the 0.12 diagonal (0.03) and the capsules
    # overlap: every helper binds, and the strongest capsule on a vertex is the
    # geometrically nearest one. The capsule weight is 0.5 * falloff**2 on top
    # of the 1.0 forearm influence, normalized over the three kept helpers.
    lifted = muscle_skinning._capsule_radius(
        0.1, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0063), 0.0063,
        muscle_skinning._mesh_diagonal(coordinates),
    )
    assert abs(lifted - 0.25 * muscle_skinning._mesh_diagonal(coordinates)) < 1e-9
    shares = {
        bone.name: 0.5 * muscle_skinning.capsule_weight(
            coordinates[0], bone.head_local, bone.tail_local, lifted
        )
        for bone in helpers
    }
    kept = sorted(
        ((name, weight) for name, weight in shares.items() if weight > 0.0),
        key=lambda item: (-item[1], str(item[0])),
    )[:3]
    total = 1.0 + sum(weight for _, weight in kept)
    written = obj.weights_by_name(0)
    for name, weight in kept:
        assert abs(written[name] - weight / total) < 1e-6, (name, written)
    assert abs(written["forearm.L"] - 1.0 / total) < 1e-6, written
    for index, groups in report["weights"].items():
        nearest = min(
            helpers,
            key=lambda bone: muscle_skinning.segment_distance(
                coordinates[index], bone.head_local, bone.tail_local
            ),
        )
        assert nearest.name in groups, (index, groups)


def test_capsule_radius_honors_explicit_large_radius():
    """Regression: a wide/bulky character needs a capsule wider than the span cap.

    A SpaceDwarf-style body on short helpers capped the capsule at half the
    span (0.06) and bound no skin. A radius the user raised above the default is
    an explicit widening and is returned untouched.
    """
    head, tail = (0.0, 0.0, 0.0), (0.0, 0.0, 0.12)
    radius = muscle_skinning._capsule_radius(0.25, head, tail, 0.12)
    assert radius == 0.25, radius
    assert radius > muscle_skinning.DEFAULT_RADIUS, radius


def _main():
    tests = [
        test_segment_distance_midpoint_and_endpoints,
        test_segment_distance_clamped_and_degenerate,
        test_capsule_weight_falloff,
        test_capsule_weight_invalid_radius,
        test_compute_muscle_weights_basic,
        test_compute_muscle_weights_keeps_existing,
        test_compute_muscle_weights_global_fallback,
        test_compute_muscle_weights_respects_budget,
        test_tiny_helper_radius_capped,
        test_chain_length_is_local_to_each_muscle,
        test_tiny_helper_radius_follows_its_span,
        test_sixteen_helpers_bind_on_a_body_scale_mesh,
        test_compute_muscle_weights_keeps_the_joint_bone,
        test_apply_muscle_skinning_creates_groups,
        test_apply_muscle_skinning_uses_global_fallback_bone,
        test_apply_muscle_skinning_errors,
        test_apply_muscle_skinning_rejects_non_armature,
        test_capsule_weights_drive_muscle_shape,
        test_is_excluded_bone,
        test_compute_muscle_weights_excludes_foot,
        test_exclude_keeps_the_owner_vertices,
        test_body_scale_mesh_lifts_the_span_cap,
        test_capsule_radius_keeps_span_cap_on_human_scale,
        test_capsule_radius_honors_explicit_large_radius,
        test_apply_muscle_skinning_excludes_foot,
        test_side_filter_drops_the_opposite_side,
        test_apply_muscle_skinning_torso_side_filter,
        test_apply_muscle_skinning_with_scaled_rotated_armature,
        test_validate_deformation_integration,
        test_skinning_message,
        test_operator_properties,
        test_operator_execute_cancelled,
        test_operator_execute_finished,
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
