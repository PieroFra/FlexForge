# Deterministic headless test of the FlexForge weight mirror.
# If bpy is missing the shared stub is installed; the test mesh is fake
# (same minimal interface as Mesh/VertexGroup) and works inside Blender too.

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

    return install_bpy_stub(props_default=True)


_install_bpy_stub()

import bpy  # noqa: E402

from flexforge import weights_mirror  # noqa: E402


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


class _FakeVertex:
    """Fake vertex exposing `groups` by reading the mesh weight map."""

    def __init__(self, mesh, index):
        self._mesh = mesh
        self.index = index

    @property
    def groups(self):
        present = self._mesh.weights.get(self.index, {})
        return [
            _FakeGroupElement(index, weight)
            for index, weight in sorted(present.items())
        ]


class _FakeObject:
    """Fake mesh object with vertex groups and indexed vertices."""

    def __init__(self, weights_per_vertex, groups=()):
        self.type = "MESH"
        names = list(groups)
        for weight_groups in weights_per_vertex.values():
            for name in weight_groups:
                if name not in names:
                    names.append(name)
        self.vertex_groups = [
            _FakeGroup(self, name, index) for index, name in enumerate(names)
        ]
        indices = {group.name: group.index for group in self.vertex_groups}
        self.weights = {}
        for vertex, weight_groups in weights_per_vertex.items():
            self.weights[vertex] = {
                indices[name]: weight
                for name, weight in weight_groups.items()
                if weight != 0.0
            }
        self.data = types.SimpleNamespace(
            vertices=[
                _FakeVertex(self, vertex) for vertex in sorted(self.weights)
            ]
        )

    def weights_by_name(self, vertex):
        names = {group.index: group.name for group in self.vertex_groups}
        return {
            names[index]: weight
            for index, weight in self.weights.get(vertex, {}).items()
        }


def test_group_side():
    assert weights_mirror.group_side("arm.L") == "L"
    assert weights_mirror.group_side("arm.R") == "R"
    assert weights_mirror.group_side("hand_L") == "L"
    assert weights_mirror.group_side("hand_R") == "R"
    assert weights_mirror.group_side("spine") is None


def test_mirror_weights():
    weights_map = {
        0: {"arm.L": 1.0},
        1: {"arm.R": 0.5, "arm.L": 0.5},
        2: {"hand_L": 0.3, "shoulder": 0.7},
        3: {"shoulder": 1.0},
        4: {"leg.L": 1.0},
    }
    right = ["arm.R", "hand_R"]
    left = ["arm.L", "hand_L"]

    result = weights_mirror.mirror_weights(weights_map, right, left)
    assert result[0] == {"arm.L": 0.5, "arm.R": 0.5}, result[0]
    assert result[1] == {"arm.R": 0.5, "arm.L": 0.5}, result[1]
    assert abs(sum(result[2].values()) - 1.0) < 1e-6, result[2]
    assert abs(result[2]["hand_R"] - 0.3 / 1.3) < 1e-6, result[2]
    assert result[3] == {"shoulder": 1.0}, result[3]
    # No matching right group: the left side stays unchanged.
    assert result[4] == {"leg.L": 1.0}, result[4]
    assert weights_map[0] == {"arm.L": 1.0}, "the input must not be modified"


def test_mirror_weights_does_not_overwrite_existing_side():
    weights_map = {0: {"arm.R": 0.25, "arm.L": 0.75}}
    result = weights_mirror.mirror_weights(
        weights_map, ["arm.R"], ["arm.L"]
    )
    assert result[0] == {"arm.R": 0.25, "arm.L": 0.75}, result[0]


def test_mirror_weights_spatial():
    weights_map = {0: {"arm.L": 1.0}, 1: {}}
    coordinates = [(1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)]
    result = weights_mirror.mirror_weights_spatial(
        weights_map, coordinates, ["arm.R"], ["arm.L"]
    )
    assert result[0] == {"arm.L": 1.0}, result[0]
    assert result[1] == {"arm.R": 1.0}, result[1]
    assert weights_map[1] == {}, "the input must not be modified"


def test_apply_mirror():
    obj = _FakeObject(
        {0: {"arm.L": 1.0}}, groups=["arm.L", "arm.R"]
    )
    report = weights_mirror.apply_mirror(obj, 4)
    assert report["vertices"] == 1, report
    assert report["mirrored"] == 1, report
    assert report["over_budget"] == 0, report
    assert report["max_influences"] == 2, report
    written = obj.weights_by_name(0)
    assert abs(written["arm.L"] - 0.5) < 1e-6, written
    assert abs(written["arm.R"] - 0.5) < 1e-6, written


def test_mirror_message():
    report = {
        "vertices": 3,
        "mirrored": 2,
        "over_budget": 1,
        "max_influences": 5,
    }
    expected = (
        "FlexForge - mirror: vertices=3 mirrored=2 over_budget=1 "
        "max_influences=5"
    )
    assert weights_mirror.mirror_message(report) == expected, (
        weights_mirror.mirror_message(report)
    )


def test_operator_mirror_weights():
    cls = weights_mirror.FLEXFORGE_OT_mirror_weights
    assert cls.bl_idname == "flexforge.mirror_weights", cls.bl_idname
    assert "REGISTER" in cls.bl_options, cls.bl_options
    assert "UNDO" in cls.bl_options, cls.bl_options
    annotations = getattr(cls, "__annotations__", {})
    assert "max_influences" in annotations, "missing property: max_influences"
    assert hasattr(cls, "bl_label"), "bl_label missing"


def _context(obj):
    return types.SimpleNamespace(
        view_layer=types.SimpleNamespace(
            objects=types.SimpleNamespace(active=obj)
        )
    )


def test_operator_mirror_weights_finished():
    obj = _FakeObject(
        {0: {"arm.L": 1.0}}, groups=["arm.L", "arm.R"]
    )

    class _Operator:
        execute = weights_mirror.FLEXFORGE_OT_mirror_weights.execute

        def __init__(self):
            self.max_influences = 4
            self.reported = []

        def report(self, levels, message):
            self.reported.append((levels, message))

    operator = _Operator()
    outcome = operator.execute(_context(obj))
    assert outcome == {"FINISHED"}, outcome
    assert len(operator.reported) == 1, operator.reported
    levels, message = operator.reported[0]
    assert levels == {"INFO"}, levels
    assert "mirror" in message and "mirrored=1" in message, message


def test_operator_mirror_weights_cancelled():
    class _Operator:
        execute = weights_mirror.FLEXFORGE_OT_mirror_weights.execute

        def __init__(self):
            self.max_influences = 4
            self.reported = []

        def report(self, levels, message):
            self.reported.append((levels, message))

    operator = _Operator()
    outcome = operator.execute(_context(None))
    assert outcome == {"CANCELLED"}, outcome
    assert len(operator.reported) == 1, operator.reported
    assert operator.reported[0][0] == {"ERROR"}, operator.reported
    assert "active mesh" in operator.reported[0][1], (
        operator.reported
    )


def _main():
    tests = [
        test_group_side,
        test_mirror_weights,
        test_mirror_weights_does_not_overwrite_existing_side,
        test_mirror_weights_spatial,
        test_apply_mirror,
        test_mirror_message,
        test_operator_mirror_weights,
        test_operator_mirror_weights_finished,
        test_operator_mirror_weights_cancelled,
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
