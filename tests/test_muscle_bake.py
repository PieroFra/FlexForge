# Deterministic headless test of the FlexForge muscle bake.
# The pure functions run on plain dicts, the Blender pass runs on fake objects
# shaped like Mesh/VertexGroup; one test builds real shape keys inside Blender.

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

    stub_folder = "/home/pierofra/.cache/opencode/tmp"
    if stub_folder not in sys.path:
        sys.path.insert(0, stub_folder)
    from flexforge_stub import installa_stub_bpy as install_bpy_stub

    installed = install_bpy_stub(props_default=True)
    return installed


_install_bpy_stub()

import bpy  # noqa: E402

from flexforge import muscle_bake, muscle_shape  # noqa: E402


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
    """Fake vertex group collection with the real `remove(group)` call."""

    def remove(self, group):
        for index, item in enumerate(self):
            if item is group or item.name == getattr(group, "name", None):
                del self[index]
                return
        raise ValueError("vertex group not found: %r" % (group,))


class _FakeVertex:
    """Fake vertex with coordinates and groups read from the fake mesh."""

    def __init__(self, mesh, index, coordinates):
        self._mesh = mesh
        self.index = index
        self.co = coordinates

    @property
    def groups(self):
        present = self._mesh.weights.get(self.index, {})
        return [
            _FakeGroupElement(index, weight)
            for index, weight in sorted(present.items())
        ]


class _FakeShapeKey:
    """Fake shape key block: one `.data[i].co` per vertex, plus its `value`."""

    def __init__(self, name, coordinates):
        self.name = name
        self.value = 0.0
        self.drivers = []
        self.drivers_removed = []
        self.data = [
            types.SimpleNamespace(co=tuple(coordinates[i]))
            for i in range(len(coordinates))
        ]

    def driver_remove(self, path):
        self.drivers_removed.append(path)
        self.drivers = []

    def driver_add(self, path):
        fcurve = _FakeFCurve(path)
        self.drivers.append(fcurve)
        return fcurve


class _FakeDriverTarget:
    """One target slot of a driver variable."""

    def __init__(self):
        self.id = None
        self.bone_target = ""


class _FakeDriverVariable:
    """Driver variable with the two ROTATION_DIFF target slots."""

    def __init__(self):
        self.name = ""
        self.type = ""
        self.targets = [_FakeDriverTarget(), _FakeDriverTarget()]


class _FakeDriverVariables(list):
    """`driver.variables` with the real `new()` call."""

    def new(self):
        variable = _FakeDriverVariable()
        self.append(variable)
        return variable


class _FakeDriver:
    """Fake driver: type, expression and variables."""

    def __init__(self):
        self.type = ""
        self.expression = ""
        self.variables = _FakeDriverVariables()


class _FakeFCurve:
    """Fake fcurve returned by `key_block.driver_add(path)`."""

    def __init__(self, data_path):
        self.data_path = data_path
        self.driver = _FakeDriver()


class _FakeObject:
    """Fake mesh object with indexed vertices, groups and shape keys."""

    def __init__(self, weights_per_vertex, coordinates=None):
        self.type = "MESH"
        self.modifiers = []
        self.parent = None
        self.shape_keys_created = []
        names = []
        for weight_groups in weights_per_vertex.values():
            for name in weight_groups:
                if name not in names:
                    names.append(name)
        self.vertex_groups = _FakeGroups()
        for index, name in enumerate(names):
            self.vertex_groups.append(_FakeGroup(self, name, index))
        indices = {group.name: group.index for group in self.vertex_groups}
        count = len(weights_per_vertex)
        self.weights = {index: {} for index in range(count)}
        for vertex, weight_groups in weights_per_vertex.items():
            self.weights[vertex] = {
                indices[name]: weight
                for name, weight in weight_groups.items()
                if weight != 0.0
            }
        if coordinates is None:
            coordinates = [(0.0, 0.0, 0.0) for _ in range(count)]
        self.data = types.SimpleNamespace(
            vertices=[
                _FakeVertex(self, index, coordinates[index])
                for index in range(count)
            ]
        )

    def weights_by_name(self, vertex):
        names = {group.index: group.name for group in self.vertex_groups}
        return {
            names[index]: weight
            for index, weight in self.weights.get(vertex, {}).items()
        }

    def shape_key_add(self, name="Key", from_mix=False):
        coordinates = [tuple(vertex.co) for vertex in self.data.vertices]
        key = _FakeShapeKey(name, coordinates)
        self.shape_keys_created.append(key)
        return key


class _FakeQuaternion:
    """Quaternion with the subset used by the rest-angle math."""

    def __init__(self, w=1.0, x=0.0, y=0.0, z=0.0):
        self.w = w
        self.x = x
        self.y = y
        self.z = z

    def _multiply(self, other):
        w1, x1, y1, z1 = self.w, self.x, self.y, self.z
        w2, x2, y2, z2 = other.w, other.x, other.y, other.z
        return _FakeQuaternion(
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        )

    def rotation_difference(self, other):
        conjugate = _FakeQuaternion(self.w, -self.x, -self.y, -self.z)
        return conjugate._multiply(other)

    @property
    def angle(self):
        return 2.0 * math.acos(min(1.0, abs(self.w)))


class _FakeMatrix:
    """Rest matrix fake: only `to_quaternion()` is used by the driver pass."""

    def __init__(self, quaternion=None):
        self._quaternion = quaternion or _FakeQuaternion()

    def to_quaternion(self):
        return self._quaternion


class _FakeBone:
    """Fake rest bone with head/tail, parent and rest matrix."""

    def __init__(self, name, head, tail, parent=None, matrix_local=None):
        self.name = name
        self.head_local = head
        self.tail_local = tail
        self.parent = parent
        self.matrix_local = matrix_local or _FakeMatrix()


class _FakeArmature:
    """Fake armature object with a rest bone list and optional pose bones."""

    def __init__(self, bones, pose_bones=None):
        self.type = "ARMATURE"
        self.data = types.SimpleNamespace(bones=bones)
        self.pose = types.SimpleNamespace(bones=list(pose_bones or []))


class _FakeContext:
    """Minimal context with the only active object used by the operator."""

    def __init__(self, obj):
        self.view_layer = types.SimpleNamespace(
            objects=types.SimpleNamespace(active=obj)
        )


def _muscle_armature():
    parent = _FakeBone("upper_arm.L", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    muscle = _FakeBone(
        "muscle_biceps_01", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), parent
    )
    return _FakeArmature([parent, muscle])


def test_shape_key_name_for_bone():
    assert (
        muscle_bake.shape_key_name_for_bone("muscle_biceps_01")
        == "flexforge_biceps"
    )
    assert (
        muscle_bake.shape_key_name_for_bone("muscle_quad_12")
        == "flexforge_quad"
    )
    # A name without the helper prefix keeps the same deterministic rule.
    assert muscle_bake.shape_key_name_for_bone("biceps") == "flexforge_biceps"
    assert muscle_bake.SHAPE_KEY_PREFIX == "flexforge_"


def test_shape_key_name_errors():
    error = None
    try:
        muscle_bake.shape_key_name_for_bone("muscle_")
    except muscle_bake.BakeError as exception:
        error = exception
    assert error is not None, "expected BakeError with an empty name"
    assert "shape key name" in str(error), str(error)


def test_compute_deltas_radial():
    coordinates = {0: (0.2, 0.5, 0.0), 1: (0.0, -0.5, 0.0)}
    weights = {0: {"muscle_biceps_01": 0.5}, 1: {"muscle_biceps_01": 1.0}}
    segments = {"muscle_biceps_01": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))}
    deltas = muscle_bake.compute_muscle_shape_deltas(
        coordinates, weights, segments, 0.05
    )
    assert list(deltas) == ["muscle_biceps_01"], deltas
    # One segment: 0.05 capped at 0.3 * the default 0.1 bone radius = 0.03, and
    # the bucket peak (0.5) is renormalized to 1.0 so it reaches the cap.
    first = deltas["muscle_biceps_01"][0]
    assert abs(first[0] - 0.03) < 1e-9, first  # 1.0 * 0.03 outward on X
    assert abs(first[1]) < 1e-9 and abs(first[2]) < 1e-9, first
    # The vertex is behind the head: clamped, so the radial points down.
    second = deltas["muscle_biceps_01"][1]
    assert abs(second[1] + 0.03) < 1e-9, second
    assert abs(second[0]) < 1e-9, second

    # Two segments of the same muscle: the displacement is split between them.
    split = {
        "muscle_biceps_01": ((0.0, 0.0, 0.0), (0.0, 0.5, 0.0)),
        "muscle_biceps_02": ((0.0, 0.5, 0.0), (0.0, 1.0, 0.0)),
    }
    pair = muscle_bake.compute_muscle_shape_deltas(
        {0: (0.2, 0.25, 0.0)}, {0: {"muscle_biceps_01": 1.0}}, split, 0.06,
        {"muscle_biceps_01": 1.0, "muscle_biceps_02": 1.0},
    )
    assert abs(pair["muscle_biceps_01"][0][0] - 0.03) < 1e-9, pair
    # The spike guard: the bone radius caps the push at 0.3 * 0.05 = 0.015.
    clamped = muscle_bake.compute_muscle_shape_deltas(
        {0: (0.2, 0.25, 0.0)}, {0: {"muscle_biceps_01": 1.0}},
        {"muscle_biceps_01": ((0.0, 0.0, 0.0), (0.0, 0.5, 0.0))}, 0.06,
        {"muscle_biceps_01": 0.05},
    )
    assert abs(clamped["muscle_biceps_01"][0][0] - 0.015) < 1e-9, clamped


def test_compute_deltas_on_axis_fallback():
    coordinates = {0: (0.0, 0.5, 0.0)}
    weights = {0: {"muscle_biceps_01": 1.0}}
    segments = {"muscle_biceps_01": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))}
    first = muscle_bake.compute_muscle_shape_deltas(
        coordinates, weights, segments, 0.05
    )
    second = muscle_bake.compute_muscle_shape_deltas(
        coordinates, weights, segments, 0.05
    )
    delta = first["muscle_biceps_01"][0]
    assert delta == second["muscle_biceps_01"][0], (delta, second)
    assert abs(delta[0] - 0.03) < 1e-9, delta  # deterministic X fallback
    assert abs(delta[1]) < 1e-9 and abs(delta[2]) < 1e-9, delta


def test_compute_deltas_errors():
    segments = {"muscle_biceps_01": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))}
    for bad in (0.0, -0.1):
        error = None
        try:
            muscle_bake.compute_muscle_shape_deltas(
                {0: (0.1, 0.5, 0.0)}, {0: {}}, segments, bad
            )
        except muscle_bake.BakeError as exception:
            error = exception
        assert error is not None, "expected BakeError with displacement=%r" % bad
        assert "displacement" in str(error), str(error)

    error = None
    try:
        muscle_bake.compute_muscle_shape_deltas({}, {}, {})
    except muscle_bake.BakeError as exception:
        error = exception
    assert error is not None, "expected BakeError with empty segments"

    error = None
    degenerate = {"muscle_biceps_01": ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))}
    try:
        muscle_bake.compute_muscle_shape_deltas({0: (0.1, 0.0, 0.0)}, {0: {}}, degenerate)
    except muscle_bake.BakeError as exception:
        error = exception
    assert error is not None, "expected BakeError with a degenerate segment"
    assert "Degenerate" in str(error), str(error)


def test_muscle_shape_bone_radius_from_envelope():
    bone = types.SimpleNamespace(head_radius=0.04, tail_radius=0.09)
    assert abs(muscle_shape.bone_radius(bone) - 0.09) < 1e-9
    # Only positive numbers count: zeros and junk fall back to the default.
    empty = types.SimpleNamespace()
    assert muscle_shape.DEFAULT_BONE_RADIUS == 0.1, muscle_shape.DEFAULT_BONE_RADIUS
    assert muscle_shape.bone_radius(empty) == muscle_shape.DEFAULT_BONE_RADIUS
    zeroed = types.SimpleNamespace(head_radius=0.0, tail_radius=-0.5)
    assert muscle_shape.bone_radius(zeroed) == muscle_shape.DEFAULT_BONE_RADIUS
    junk = types.SimpleNamespace(head_radius="0.2", tail_radius=None)
    assert muscle_shape.bone_radius(junk) == muscle_shape.DEFAULT_BONE_RADIUS
    # An explicit fallback is used only when the envelope has no usable radius.
    assert abs(muscle_shape.bone_radius(empty, 0.25) - 0.25) < 1e-9
    assert abs(muscle_shape.bone_radius(bone, 0.25) - 0.09) < 1e-9


def test_muscle_shape_weights_are_one_hot():
    segments = {"muscle_biceps_01": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))}
    coordinates = {index: (0.5, 0.5, 0.0) for index in range(4)}
    weights = {
        0: {"muscle_biceps_01": 0.0},
        1: {"muscle_biceps_01": 1e-9},
        2: {"muscle_biceps_01": 1.0},
        3: {"upper_arm.L": 1.0},
    }
    deltas = muscle_shape.compute_muscle_shape_deltas(
        coordinates, weights, segments, 0.05
    )
    # Only the vertex that really carries the weight moves: zero, sub-EPS and
    # other-bone vertices are dropped, not kept as zero-length entries.
    assert sorted(deltas["muscle_biceps_01"]) == [2], deltas
    assert abs(deltas["muscle_biceps_01"][2][0] - 0.03) < 1e-9, deltas
    # No vertex on the helper at all: the bone never appears in the result.
    empty = muscle_shape.compute_muscle_shape_deltas(
        coordinates, {3: {"upper_arm.L": 1.0}}, segments, 0.05
    )
    assert empty == {}, empty


def test_muscle_shape_projection_clamp():
    segments = {"muscle_biceps_01": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))}
    points = {0: (0.3, 4.0, 0.0), 1: (0.3, -4.0, 0.0), 2: (0.3, 0.5, 0.0)}
    weights = {index: {"muscle_biceps_01": 1.0} for index in points}
    deltas = muscle_shape.compute_muscle_shape_deltas(
        points, weights, segments, 0.05
    )["muscle_biceps_01"]

    def radial(point, closest, amplitude=0.03):
        offset = [point[i] - closest[i] for i in range(3)]
        length = math.sqrt(sum(component ** 2 for component in offset))
        return [amplitude * component / length for component in offset]

    # Beyond the tail the projection clamps to the tail itself, so the radial
    # direction leans back instead of growing along the axis.
    tail = radial((0.3, 4.0, 0.0), (0.0, 1.0, 0.0))
    for axis in range(3):
        assert abs(deltas[0][axis] - tail[axis]) < 1e-9, (deltas[0], tail)
    assert 0.0 < tail[0] < 0.03 and tail[1] < 0.03, tail
    # Before the head the projection clamps to the head.
    head = radial((0.3, -4.0, 0.0), (0.0, 0.0, 0.0))
    for axis in range(3):
        assert abs(deltas[1][axis] - head[axis]) < 1e-9, (deltas[1], head)
    assert head[1] < 0.0, head
    # Inside the segment nothing clamps: the radial is exactly perpendicular.
    assert abs(deltas[2][0] - 0.03) < 1e-9, deltas[2]
    assert abs(deltas[2][1]) < 1e-9 and abs(deltas[2][2]) < 1e-9, deltas[2]


def test_muscle_shape_split_over_segments():
    names = ["muscle_pec_01", "muscle_pec_02", "muscle_pec_03"]
    segments = [(name, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)) for name in names]
    coordinates = {0: (0.5, 0.5, 0.0)}
    weights = {0: {name: 1.0 for name in names}}
    deltas = muscle_shape.compute_muscle_shape_deltas(
        coordinates, weights, segments, 0.06
    )
    assert sorted(deltas) == names, deltas
    total = 0.0
    for name in names:
        delta = deltas[name][0]
        assert abs(delta[0]) < 1e-9 and abs(delta[2]) < 1e-9, delta
        # 0.06 split over three segments: 0.02 each, under the 0.03 spike cap.
        assert abs(delta[1] - 0.02) < 1e-9, delta
        total += delta[1]
    assert abs(total - 0.06) < 1e-9, total
    # The tuple form is the same input: one segment, no split, cap on 0.03.
    listed = muscle_shape.compute_muscle_shape_deltas(
        coordinates, weights, [("muscle_pec_01", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))],
        0.06,
    )
    assert sorted(listed) == ["muscle_pec_01"], listed
    assert abs(listed["muscle_pec_01"][0][1] - 0.03) < 1e-9, listed


def test_muscle_shape_displacement_cap():
    segments = {"muscle_biceps_01": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))}
    coordinates = {0: (0.5, 0.5, 0.0)}
    weights = {0: {"muscle_biceps_01": 0.5}}
    wide = muscle_shape.compute_muscle_shape_deltas(
        coordinates, weights, segments, 1.0, {"muscle_biceps_01": 0.2}
    )
    # The peak segment of the vertex is renormalized to the cap: 0.3 * 0.2.
    assert abs(wide["muscle_biceps_01"][0][0] - 0.06) < 1e-9, wide
    tight = muscle_shape.compute_muscle_shape_deltas(
        coordinates, weights, segments, 1.0, {"muscle_biceps_01": 0.04}
    )
    assert abs(tight["muscle_biceps_01"][0][0] - 0.012) < 1e-9, tight
    # A junk radius falls back to the default 0.1 instead of dropping the cap.
    junk = muscle_shape.compute_muscle_shape_deltas(
        coordinates, weights, segments, 1.0, {"muscle_biceps_01": -1.0}
    )
    assert abs(junk["muscle_biceps_01"][0][0] - 0.03) < 1e-9, junk


def test_compute_deltas_peak_normalization():
    segments = {"muscle_biceps_01": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))}
    coordinates = {0: (0.5, 0.5, 0.0), 1: (0.5, 0.5, 0.0)}
    weights = {
        0: {"muscle_biceps_01": 0.361},
        1: {"muscle_biceps_01": 0.12},
    }
    # Under the cap (0.02 < 0.03): the heaviest vertex of the bucket is
    # renormalized to the full amplitude, the lighter one to the same value.
    deltas = muscle_shape.compute_muscle_shape_deltas(
        coordinates, weights, segments, 0.02
    )["muscle_biceps_01"]
    assert abs(deltas[0][0] - 0.02) < 1e-9, deltas
    assert abs(deltas[1][0] - 0.02) < 1e-9, deltas
    assert abs(deltas[0][1]) < 1e-9 and abs(deltas[1][1]) < 1e-9, deltas
    # Inside one vertex the scale follows the peak segment, not the sum: the
    # secondary segment gets exactly a third of the dominant delta vector.
    split = {
        "muscle_biceps_01": ((0.0, 0.0, 0.0), (0.0, 0.5, 0.0)),
        "muscle_biceps_02": ((0.0, 0.5, 0.0), (0.0, 1.0, 0.0)),
    }
    mixed = muscle_shape.compute_muscle_shape_deltas(
        {0: (0.5, 0.25, 0.0)},
        {0: {"muscle_biceps_01": 0.3, "muscle_biceps_02": 0.1}},
        split, 0.04,
    )
    dominant = mixed["muscle_biceps_01"][0]
    secondary = mixed["muscle_biceps_02"][0]
    length = math.sqrt(sum(value ** 2 for value in dominant))
    assert abs(length - 0.02) < 1e-9, dominant
    for axis in range(3):
        assert abs(secondary[axis] - dominant[axis] / 3.0) < 1e-9, mixed


def test_compute_deltas_max_displacement_ratio():
    segments = {"muscle_biceps_01": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0))}
    coordinates = {0: (0.5, 0.5, 0.0)}
    weights = {0: {"muscle_biceps_01": 1.0}}
    default = muscle_shape.compute_muscle_shape_deltas(
        coordinates, weights, segments, 1.0, {"muscle_biceps_01": 0.1}
    )
    assert abs(default["muscle_biceps_01"][0][0] - 0.03) < 1e-9, default
    wider = muscle_shape.compute_muscle_shape_deltas(
        coordinates, weights, segments, 1.0, {"muscle_biceps_01": 0.1},
        max_displacement_ratio=0.5,
    )
    assert abs(wider["muscle_biceps_01"][0][0] - 0.05) < 1e-9, wider
    for bad in (0.0, -0.2):
        error = None
        try:
            muscle_shape.compute_muscle_shape_deltas(
                coordinates, weights, segments, 1.0, None, bad
            )
        except muscle_shape.BakeError as exception:
            error = exception
        assert error is not None, "expected BakeError with ratio=%r" % bad
        assert "max displacement ratio" in str(error), str(error)


def test_muscle_shape_blends_adjacent_segments():
    # Two segments of the same muscle meeting at (0, 1, 0) at a right angle.
    segments = {
        "muscle_pec_01": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        "muscle_pec_02": ((0.0, 1.0, 0.0), (1.0, 1.0, 0.0)),
    }
    coordinates = {0: (0.5, 1.0, 0.0)}
    weights = {0: {"muscle_pec_01": 0.5, "muscle_pec_02": 0.5}}
    deltas = muscle_shape.compute_muscle_shape_deltas(
        coordinates, weights, segments, 0.06,
        {"muscle_pec_01": 0.1, "muscle_pec_02": 0.1},
    )
    first = deltas["muscle_pec_01"][0]
    second = deltas["muscle_pec_02"][0]
    # Equal weights and equal envelopes: the seam sees no step at all.
    for axis in range(3):
        assert abs(first[axis] - second[axis]) < 1e-9, (first, second)
    length = math.sqrt(sum(value ** 2 for value in first))
    assert abs(length - 0.03) < 1e-9, length
    # The direction is the normalized blend of both radials (+X and -Y), not
    # the direction of either segment alone.
    assert abs(first[0] - 0.03 / math.sqrt(2.0)) < 1e-9, first
    assert abs(first[1] + 0.03 / math.sqrt(2.0)) < 1e-9, first
    assert abs(first[2]) < 1e-9, first


def test_muscle_shape_blends_adjacent_envelope():
    names = ["muscle_pec_01", "muscle_pec_02"]
    segments = [(name, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)) for name in names]
    coordinates = {0: (0.5, 0.5, 0.0)}
    weights = {0: {name: 0.5 for name in names}}
    deltas = muscle_shape.compute_muscle_shape_deltas(
        coordinates, weights, segments, 1.0,
        {"muscle_pec_01": 0.1, "muscle_pec_02": 0.4},
    )
    # The envelope is blended (0.25) before the 0.3 cap and the peak segment is
    # renormalized to 1.0, so both segments push 0.3 * 0.25.
    for name in names:
        delta = deltas[name][0]
        assert abs(delta[1] - 0.3 * 0.25) < 1e-9, (name, delta)
        assert abs(delta[0]) < 1e-9 and abs(delta[2]) < 1e-9, delta


def test_muscle_shape_single_segment_keeps_own_direction():
    segments = {
        "muscle_pec_01": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        "muscle_pec_02": ((0.0, 1.0, 0.0), (1.0, 1.0, 0.0)),
    }
    coordinates = {0: (0.5, 1.0, 0.0)}
    weights = {0: {"muscle_pec_01": 1.0}}
    deltas = muscle_shape.compute_muscle_shape_deltas(
        coordinates, weights, segments, 0.06,
        {"muscle_pec_01": 0.1, "muscle_pec_02": 0.1},
    )
    # A vertex weighted on one segment only keeps that segment's own radial:
    # the blend never drags in a bone it is not weighted on.
    assert list(deltas) == ["muscle_pec_01"], deltas
    delta = deltas["muscle_pec_01"][0]
    assert abs(delta[0] - 0.03) < 1e-9, delta
    assert abs(delta[1]) < 1e-9 and abs(delta[2]) < 1e-9, delta


def test_collapse_weights_to_parent():
    bone_parents = {
        "muscle_biceps_01": "muscle_biceps_00",
        "muscle_biceps_00": "upper_arm.L",
        "upper_arm.L": "root",
    }
    weights = {0: {"muscle_biceps_01": 0.6, "muscle_biceps_00": 0.4}}
    collapsed = muscle_bake.collapse_muscle_weights_to_parent(
        weights, bone_parents
    )
    assert collapsed[0] == {"upper_arm.L": 1.0}, collapsed
    assert weights[0]["muscle_biceps_01"] == 0.6, "the input must not change"
    # Helper bones without a non-muscle ancestor are dropped, not invented.
    orphan = muscle_bake.collapse_muscle_weights_to_parent(
        {0: {"muscle_orphan_01": 1.0}}, bone_parents
    )
    assert orphan[0] == {}, orphan


def test_collapse_weights_influence_limit():
    bone_parents = {"muscle_biceps_01": "upper_arm.L"}
    weights = {
        0: {
            "muscle_biceps_01": 0.1,
            "a": 0.2,
            "b": 0.25,
            "c": 0.25,
            "d": 0.2,
        }
    }
    collapsed = muscle_bake.collapse_muscle_weights_to_parent(
        weights, bone_parents, 4
    )
    limited = collapsed[0]
    assert len(limited) == 4, limited
    assert "upper_arm.L" not in limited, limited
    assert abs(sum(limited.values()) - 1.0) < 1e-6, limited


def test_bake_message():
    report = {
        "shape_keys": 2,
        "vertices_displaced": 7,
        "stripped_muscles": 3,
    }
    expected = (
        "FlexForge - bake: shape_keys=2 vertices_displaced=7 "
        "stripped_muscles=3"
    )
    assert muscle_bake.bake_message(report) == expected, (
        muscle_bake.bake_message(report)
    )


def test_bake_uses_span_floor_when_bone_radius_is_tiny():
    parent = _FakeBone("upper_arm.L", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    muscle = _FakeBone(
        "muscle_biceps_01", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), parent
    )
    # Real FBX rig scaled to millimetres: the envelope alone would cap the push
    # at 0.3 * 0.001 = 0.0003 and the bulge would vanish.
    muscle.head_radius = 0.001
    muscle.tail_radius = 0.001
    armature = _FakeArmature([parent, muscle])
    obj = _FakeObject(
        {0: {"muscle_biceps_01": 1.0}}, coordinates=[(0.1, 0.5, 0.0)]
    )
    report = muscle_bake.apply_muscle_bake(obj, armature)
    assert report["vertices_displaced"] == 1, report
    key = obj.shape_keys_created[1]
    delta = key.data[0].co[0] - 0.1
    # A quarter of the 1.0 segment (0.25) allows the full 0.05 displacement.
    assert delta >= 0.05 - 1e-9, delta
    assert delta > 0.0003 + 1e-6, "the bulge was squashed to the tiny cap"


def test_apply_fake_mesh():
    parent = _FakeBone("upper_arm.L", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    first_segment = _FakeBone(
        "muscle_biceps_01", (0.0, 0.0, 0.0), (0.0, 0.5, 0.0), parent
    )
    second_segment = _FakeBone(
        "muscle_biceps_02", (0.0, 0.5, 0.0), (0.0, 1.0, 0.0), first_segment
    )
    triceps = _FakeBone(
        "muscle_triceps_01", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), parent
    )
    armature = _FakeArmature(
        [parent, first_segment, second_segment, triceps]
    )
    obj = _FakeObject(
        {
            0: {
                "upper_arm.L": 0.5,
                "muscle_biceps_01": 0.25,
                "muscle_biceps_02": 0.25,
            },
            1: {"muscle_triceps_01": 1.0},
        },
        coordinates=[(0.1, 0.5, 0.0), (0.0, 0.25, 0.0)],
    )
    report = muscle_bake.apply_muscle_bake(obj, armature)
    assert report == {
        "shape_keys": 2,
        "vertices_displaced": 2,
        "stripped_muscles": 3,
        "drivers_added": 0,
    }, report
    # One key per muscle, never per segment, and exactly one key is active.
    names = [key.name for key in obj.shape_keys_created]
    assert names == ["Basis", "flexforge_biceps", "flexforge_triceps"], names
    biceps = obj.shape_keys_created[1]
    triceps_key = obj.shape_keys_created[2]
    assert biceps.value == 0.0, biceps.value
    assert triceps_key.value == 1.0, triceps_key.value
    # 0.05 split over two segments, peak weight 0.25 renormalized to 1.0 each:
    # +0.025 per segment, +0.05 on X in total.
    assert abs(biceps.data[0].co[0] - 0.15) < 1e-9, biceps.data[0].co
    assert tuple(biceps.data[1].co) == (0.0, 0.25, 0.0), biceps.data[1].co
    assert tuple(triceps_key.data[0].co) == (0.1, 0.5, 0.0), triceps_key
    assert abs(triceps_key.data[1].co[0] - 0.03) < 1e-9, triceps_key.data[1].co
    assert [group.name for group in obj.vertex_groups] == ["upper_arm.L"]
    assert obj.weights_by_name(0) == {"upper_arm.L": 1.0}, obj.weights_by_name(0)
    assert obj.weights_by_name(1) == {"upper_arm.L": 1.0}, obj.weights_by_name(1)


def test_apply_requires_armature():
    obj = _FakeObject({0: {"muscle_biceps_01": 1.0}})
    error = None
    try:
        muscle_bake.apply_muscle_bake(obj)
    except muscle_bake.BakeError as exception:
        error = exception
    assert error is not None, "expected BakeError without an armature"
    assert "armature" in str(error), str(error)

    non_mesh = types.SimpleNamespace(type="EMPTY")
    error = None
    try:
        muscle_bake.apply_muscle_bake(non_mesh, _muscle_armature())
    except muscle_bake.BakeError as exception:
        error = exception
    assert error is not None, "expected BakeError on a non-mesh object"
    assert "mesh" in str(error), str(error)


def test_operator_bake_shape_keys():
    cls = muscle_bake.FLEXFORGE_OT_bake_shape_keys
    assert cls.bl_idname == "flexforge.bake_shape_keys", cls.bl_idname
    assert cls.bl_label == "Bake shape keys", cls.bl_label
    assert "REGISTER" in cls.bl_options, cls.bl_options
    assert "UNDO" in cls.bl_options, cls.bl_options
    annotations = getattr(cls, "__annotations__", {})
    for name in ("displacement", "strip_muscle_weights", "max_influences",
                 "max_displacement_ratio"):
        assert name in annotations, "missing property: %s" % name


def _fake_operator(displacement=0.05, strip=True, max_influences=4):
    """Fake operator with the real execute, like the other tests."""

    class _Operator:
        execute = muscle_bake.FLEXFORGE_OT_bake_shape_keys.execute

        def __init__(self):
            self.displacement = displacement
            self.strip_muscle_weights = strip
            self.max_influences = max_influences
            self.reported = []

        def report(self, levels, message):
            self.reported.append((levels, message))

    return _Operator()


def test_operator_execute_cancelled():
    operator = _fake_operator()
    assert operator.execute(_FakeContext(None)) == {"CANCELLED"}
    assert operator.reported[0][0] == {"ERROR"}, operator.reported
    assert "active mesh" in operator.reported[0][1], operator.reported

    operator = _fake_operator()
    non_mesh = types.SimpleNamespace(type="EMPTY")
    assert operator.execute(_FakeContext(non_mesh)) == {"CANCELLED"}
    assert "active mesh" in operator.reported[0][1], operator.reported

    operator = _fake_operator()
    obj = _FakeObject({0: {"muscle_biceps_01": 1.0}})
    assert operator.execute(_FakeContext(obj)) == {"CANCELLED"}
    assert operator.reported[0][0] == {"ERROR"}, operator.reported
    assert "armature" in operator.reported[0][1], operator.reported


def test_operator_execute_finished():
    obj = _FakeObject(
        {
            0: {"upper_arm.L": 0.5, "muscle_biceps_01": 0.5},
            1: {"muscle_biceps_01": 1.0},
        },
        coordinates=[(0.1, 0.5, 0.0), (0.0, 0.25, 0.0)],
    )
    obj.parent = _muscle_armature()
    operator = _fake_operator()
    outcome = operator.execute(_FakeContext(obj))
    assert outcome == {"FINISHED"}, outcome
    assert operator.reported[0][0] == {"INFO"}, operator.reported
    assert "FlexForge - bake" in operator.reported[0][1], operator.reported
    assert [key.name for key in obj.shape_keys_created] == [
        "Basis",
        "flexforge_biceps",
    ], obj.shape_keys_created
    key = obj.shape_keys_created[1]
    assert key.value == 1.0, key.value
    assert abs(key.data[0].co[0] - 0.13) < 1e-9, key.data[0].co  # 0.1 + 1.0 * 0.03
    assert abs(key.data[1].co[0] - 0.03) < 1e-9, key.data[1].co  # on-axis fallback


def test_apply_real_blender():
    armature_data = bpy.data.armatures.new("flexforge_bake_arm")
    armature = bpy.data.objects.new("flexforge_bake_arm", armature_data)
    bpy.context.scene.collection.objects.link(armature)
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    parent_bone = armature_data.edit_bones.new("upper_arm.L")
    parent_bone.head = (0.0, 0.0, 0.0)
    parent_bone.tail = (0.0, 1.0, 0.0)
    muscle_bone = armature_data.edit_bones.new("muscle_biceps_01")
    muscle_bone.head = (0.0, 0.0, 0.0)
    muscle_bone.tail = (0.0, 1.0, 0.0)
    muscle_bone.parent = parent_bone
    # Explicit envelope radius: the spike guard caps the push at 0.3 * 0.1.
    for bone in (parent_bone, muscle_bone):
        bone.head_radius = 0.1
        bone.tail_radius = 0.1
    bpy.ops.object.mode_set(mode="OBJECT")

    mesh = bpy.data.meshes.new("flexforge_bake_mesh")
    mesh.from_pydata([(0.1, 0.5, 0.0), (0.0, 0.25, 0.0)], [], [(0, 1)])
    obj = bpy.data.objects.new("flexforge_bake_mesh", mesh)
    bpy.context.scene.collection.objects.link(obj)
    parent_group = obj.vertex_groups.new(name="upper_arm.L")
    muscle_group = obj.vertex_groups.new(name="muscle_biceps_01")
    parent_group.add([0], 0.5, "REPLACE")
    muscle_group.add([0], 0.5, "REPLACE")
    muscle_group.add([1], 1.0, "REPLACE")
    modifier = obj.modifiers.new(name="Armature", type="ARMATURE")
    modifier.object = armature

    try:
        report = muscle_bake.apply_muscle_bake(obj)
        assert report == {
            "shape_keys": 1,
            "vertices_displaced": 2,
            "stripped_muscles": 1,
            "drivers_added": 0,
        }, report
        keys = obj.data.shape_keys.key_blocks
        assert keys[0].name == "Basis", keys[0].name
        assert keys[1].name == "flexforge_biceps", keys[1].name
        assert abs(keys[1].value - 1.0) < 1e-6, keys[1].value
        first = keys[1].data[0].co
        assert abs(first[0] - 0.13) < 1e-5, tuple(first)  # 0.1 + 1.0 * 0.03
        second = keys[1].data[1].co
        assert abs(second[0] - 0.03) < 1e-5, tuple(second)  # on-axis fallback
        assert [group.name for group in obj.vertex_groups] == ["upper_arm.L"], (
            [group.name for group in obj.vertex_groups]
        )
        names = {group.index: group.name for group in obj.vertex_groups}
        for vertex in obj.data.vertices:
            total = 0.0
            for element in vertex.groups:
                if names[element.group] == "upper_arm.L":
                    total += element.weight
            assert abs(total - 1.0) < 1e-5, (vertex.index, total)
    finally:
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.objects.remove(armature, do_unlink=True)
        bpy.data.meshes.remove(mesh)
        bpy.data.armatures.remove(armature_data)


def _rotate_z_quaternion():
    """Quaternion of a 90 degree turn about Z: its angle is pi / 2."""
    half = math.sqrt(0.5)
    return _FakeQuaternion(half, 0.0, 0.0, half)


def test_attach_pose_drivers_creates_rotation_diff():
    origin = _FakeBone("upper_arm.L", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    insertion = _FakeBone(
        "forearm.L", (0.0, 1.0, 0.0), (0.0, 2.0, 0.0),
        matrix_local=_FakeMatrix(_rotate_z_quaternion()),
    )
    muscle = _FakeBone(
        "muscle_biceps_01", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), origin
    )
    constraint = types.SimpleNamespace(type="STRETCH_TO", subtarget="forearm.L")
    armature = _FakeArmature(
        [origin, insertion, muscle],
        pose_bones=[
            types.SimpleNamespace(
                name="muscle_biceps_01", constraints=[constraint]
            )
        ],
    )
    obj = _FakeObject({0: {"muscle_biceps_01": 1.0}})
    obj.shape_key_add(name="Basis")
    key = obj.shape_key_add(name="flexforge_biceps")
    obj.data.shape_keys = types.SimpleNamespace(key_blocks=obj.shape_keys_created)

    assert muscle_bake.attach_pose_drivers(obj, armature) == 1
    assert key.drivers_removed == ["value"], key.drivers_removed
    assert len(key.drivers) == 1, key.drivers
    assert key.drivers[0].data_path == "value", key.drivers[0].data_path
    driver = key.drivers[0].driver
    assert driver.type == "SCRIPTED", driver.type
    variable = driver.variables[0]
    assert variable.name == "ang", variable.name
    assert variable.type == "ROTATION_DIFF", variable.type
    assert variable.targets[0].id is armature
    assert variable.targets[0].bone_target == "upper_arm.L"
    assert variable.targets[1].id is armature
    assert variable.targets[1].bone_target == "forearm.L"
    # Rest angle pi / 2 and the 1.5708 rad default, both with 6 decimals.
    assert driver.expression == (
        "min(1.0, max(0.0, abs(ang - 1.570796) / 1.570800))"
    ), driver.expression

    # A second call replaces the driver instead of stacking another one.
    assert muscle_bake.attach_pose_drivers(obj, armature, max_angle_rad=1.0) == 1
    assert key.drivers_removed == ["value", "value"], key.drivers_removed
    assert len(key.drivers) == 1, key.drivers
    assert key.drivers[0].driver.expression == (
        "min(1.0, max(0.0, abs(ang - 1.570796) / 1.000000))"
    ), key.drivers[0].driver.expression
    assert "drive_by_pose" in getattr(
        muscle_bake.FLEXFORGE_OT_bake_shape_keys, "__annotations__", {}
    )


def test_attach_pose_drivers_ignores_missing_targets():
    origin = _FakeBone("upper_arm.L", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    # No STRETCH_TO constraint, no parent at all, and a constraint that points
    # back at the origin bone: none of them may get a driver.
    no_constraint = _FakeBone(
        "muscle_biceps_01", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), origin
    )
    no_parent = _FakeBone("muscle_triceps_01", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    self_target = _FakeBone(
        "muscle_quad_01", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), origin
    )
    armature = _FakeArmature(
        [origin, no_constraint, no_parent, self_target],
        pose_bones=[
            types.SimpleNamespace(
                name="muscle_quad_01",
                constraints=[
                    types.SimpleNamespace(
                        type="STRETCH_TO", subtarget="upper_arm.L"
                    )
                ],
            ),
            types.SimpleNamespace(
                name="muscle_triceps_01",
                constraints=[
                    types.SimpleNamespace(type="STRETCH_TO", subtarget="forearm.L")
                ],
            ),
        ],
    )
    obj = _FakeObject({0: {"muscle_biceps_01": 1.0}})
    for name in ("flexforge_biceps", "flexforge_triceps", "flexforge_quad",
                 "Custom"):
        obj.shape_key_add(name=name)
    obj.data.shape_keys = types.SimpleNamespace(key_blocks=obj.shape_keys_created)

    assert muscle_bake.attach_pose_drivers(obj, armature) == 0
    for key in obj.shape_keys_created:
        assert key.drivers == [], (key.name, key.drivers)
        assert key.drivers_removed == [], (key.name, key.drivers_removed)


def test_attach_pose_drivers_rejects_non_positive_max_angle():
    obj = _FakeObject({0: {"muscle_biceps_01": 1.0}})
    obj.shape_key_add(name="Basis")
    key = obj.shape_key_add(name="flexforge_biceps")
    obj.data.shape_keys = types.SimpleNamespace(key_blocks=obj.shape_keys_created)
    armature = _FakeArmature([])

    for bad in (0.0, -1.5708, -0.25):
        error = None
        try:
            muscle_bake.attach_pose_drivers(obj, armature, max_angle_rad=bad)
        except muscle_bake.BakeError as exception:
            error = exception
        assert error is not None, "expected BakeError with max_angle_rad=%r" % bad
        assert str(error) == "max_angle_rad must be positive.", str(error)
    # The invalid angle stops the call before anything is touched.
    assert key.drivers == [], key.drivers
    assert key.drivers_removed == [], key.drivers_removed

    # The default and a positive angle still go through.
    origin = _FakeBone("upper_arm.L", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    insertion = _FakeBone("forearm.L", (0.0, 1.0, 0.0), (0.0, 2.0, 0.0))
    muscle = _FakeBone(
        "muscle_biceps_01", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), origin
    )
    constraint = types.SimpleNamespace(type="STRETCH_TO", subtarget="forearm.L")
    good = _FakeArmature(
        [origin, insertion, muscle],
        pose_bones=[
            types.SimpleNamespace(
                name="muscle_biceps_01", constraints=[constraint]
            )
        ],
    )
    assert muscle_bake.attach_pose_drivers(obj, good, max_angle_rad=0.5) == 1


def _main():
    tests = [
        test_shape_key_name_for_bone,
        test_shape_key_name_errors,
        test_compute_deltas_radial,
        test_compute_deltas_on_axis_fallback,
        test_compute_deltas_errors,
        test_muscle_shape_bone_radius_from_envelope,
        test_muscle_shape_weights_are_one_hot,
        test_muscle_shape_projection_clamp,
        test_muscle_shape_split_over_segments,
        test_muscle_shape_displacement_cap,
        test_compute_deltas_peak_normalization,
        test_compute_deltas_max_displacement_ratio,
        test_muscle_shape_blends_adjacent_segments,
        test_muscle_shape_blends_adjacent_envelope,
        test_muscle_shape_single_segment_keeps_own_direction,
        test_collapse_weights_to_parent,
        test_collapse_weights_influence_limit,
        test_bake_message,
        test_bake_uses_span_floor_when_bone_radius_is_tiny,
        test_apply_fake_mesh,
        test_apply_requires_armature,
        test_operator_bake_shape_keys,
        test_operator_execute_cancelled,
        test_operator_execute_finished,
        test_apply_real_blender,
        test_attach_pose_drivers_creates_rotation_diff,
        test_attach_pose_drivers_ignores_missing_targets,
        test_attach_pose_drivers_rejects_non_positive_max_angle,
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
