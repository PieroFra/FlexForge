# Deterministic headless test of the FlexForge weight cleanup.
# No external dependency: if bpy is missing the shared stub is installed;
# the test mesh is fake (same minimal interface as Mesh/VertexGroup)
# and works identically inside Blender too.

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

from flexforge import weights_cleanup  # noqa: E402


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
    """Fake vertex with groups read from the fake mesh."""

    def __init__(self, mesh, index):
        self._mesh = mesh
        self.index = index
        self.co = (0.0, 0.0, 0.0)

    @property
    def groups(self):
        present = self._mesh.weights.get(self.index, {})
        return [
            _FakeGroupElement(index, weight)
            for index, weight in sorted(present.items())
        ]


class _FakeObject:
    """Fake mesh object with indexed vertices and vertex groups."""

    def __init__(self, weights_per_vertex):
        self.type = "MESH"
        names = []
        for weight_groups in weights_per_vertex.values():
            for name in weight_groups:
                if name not in names:
                    names.append(name)
        self.vertex_groups = [
            _FakeGroup(self, name, index) for index, name in enumerate(names)
        ]
        indices = {group.name: group.index for group in self.vertex_groups}
        self.weights = {index: {} for index in range(len(weights_per_vertex))}
        for vertex, weight_groups in weights_per_vertex.items():
            self.weights[vertex] = {
                indices[name]: weight
                for name, weight in weight_groups.items()
                if weight != 0.0
            }
        self.data = types.SimpleNamespace(
            vertices=[
                _FakeVertex(self, index)
                for index in range(len(weights_per_vertex))
            ]
        )

    def weights_by_name(self, vertex):
        names = {group.index: group.name for group in self.vertex_groups}
        return {
            names[index]: weight
            for index, weight in self.weights.get(vertex, {}).items()
        }


class _FakeContext:
    """Minimal context with the only active mesh used by the operator."""

    def __init__(self, obj):
        self.view_layer = types.SimpleNamespace(
            objects=types.SimpleNamespace(active=obj)
        )


def test_clean_weights_removes_epsilon():
    weights_map = {
        0: {"a": 1e-9, "b": 0.5, "c": 0.5},
        1: {"a": 0.0, "b": 1.0},
    }
    result = weights_cleanup.clean_weights(weights_map)
    assert result["vertices"] == 2, result
    assert result["zero_removed"] == 2, result
    assert result["weights"][0] == {"b": 0.5, "c": 0.5}, result["weights"]
    assert result["weights"][1] == {"b": 1.0}, result["weights"]
    assert weights_map[0]["a"] == 1e-9, "the input must not be modified"
    # Same threshold as weights.py: a weight equal to eps is removed.
    threshold = weights_cleanup.clean_weights({0: {"a": 1e-6}}, 1e-6)
    assert threshold["zero_removed"] == 1, threshold
    assert threshold["weights"][0] == {}, threshold["weights"]
    assert threshold["orphan_groups"] == ["a"], threshold["orphan_groups"]


def test_clean_weights_orphan_groups():
    weights_map = {
        0: {"a": 1e-8, "b": 1.0},
        1: {"b": 0.5, "c": 1e-7},
    }
    result = weights_cleanup.clean_weights(weights_map)
    assert result["orphan_groups"] == ["a", "c"], result["orphan_groups"]
    assert result["zero_removed"] == 2, result
    assert result["weights"][1] == {"b": 1.0}, result["weights"]


def test_clean_weights_influence_limit():
    weights_map = {
        0: {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.35, "e": 0.05},
    }
    result = weights_cleanup.clean_weights(weights_map, 1e-9, 4)
    limited = result["weights"][0]
    assert len(limited) == 4, limited
    assert "e" not in limited, limited
    assert abs(sum(limited.values()) - 1.0) < 1e-6, limited
    assert result["over_budget_removed"] == 1, result
    assert result["orphan_groups"] == ["e"], result["orphan_groups"]


def test_clean_weights_errors():
    error = None
    try:
        weights_cleanup.clean_weights({}, 1e-6, 0)
    except weights_cleanup.WeightsError as exception:
        error = exception
    assert error is not None, "expected WeightsError with max_influences=0"

    error = None
    try:
        weights_cleanup.clean_weights({}, -0.1)
    except weights_cleanup.WeightsError as exception:
        error = exception
    assert error is not None, "expected WeightsError with a negative eps"
    assert "eps" in str(error), str(error)


def test_cleanup_message():
    report = {
        "vertices": 5,
        "zero_removed": 3,
        "orphan_groups": ["a", "b"],
        "over_budget_removed": 1,
    }
    expected = (
        "FlexForge - cleanup: vertices=5 zero_removed=3 orphan_groups=2 "
        "over_budget_removed=1"
    )
    assert weights_cleanup.cleanup_message(report) == expected, (
        weights_cleanup.cleanup_message(report)
    )


def test_apply_cleanup():
    obj = _FakeObject(
        {
            0: {"a": 1e-4, "b": 0.75},
            1: {"a": 0.5, "c": 0.5},
        }
    )
    report = weights_cleanup.apply_cleanup(obj, 1e-3, 4)
    assert report["vertices"] == 2, report
    assert report["zero_removed"] == 1, report
    assert report["orphan_groups"] == [], report["orphan_groups"]
    assert report["over_budget_removed"] == 0, report
    assert obj.weights_by_name(0) == {"b": 1.0}, obj.weights_by_name(0)
    assert obj.weights_by_name(1) == {"a": 0.5, "c": 0.5}, (
        obj.weights_by_name(1)
    )


def test_operator_cleanup_weights():
    cls = weights_cleanup.FLEXFORGE_OT_cleanup_weights
    assert cls.bl_idname == "flexforge.cleanup_weights", cls.bl_idname
    assert "REGISTER" in cls.bl_options, cls.bl_options
    assert "UNDO" in cls.bl_options, cls.bl_options
    annotations = getattr(cls, "__annotations__", {})
    assert "max_influences" in annotations, "missing property: max_influences"
    assert hasattr(cls, "bl_label"), "bl_label missing"


def _fake_operator(max_influences=4):
    """Fake operator with the real execute, like the other tests."""

    class _Operator:
        execute = weights_cleanup.FLEXFORGE_OT_cleanup_weights.execute

        def __init__(self, max_influences):
            self.max_influences = max_influences
            self.reported = []

        def report(self, levels, message):
            self.reported.append((levels, message))

    return _Operator(max_influences)


def test_operator_execute_cancelled():
    operator = _fake_operator()
    assert operator.execute(_FakeContext(None)) == {"CANCELLED"}
    assert operator.reported[0][0] == {"ERROR"}, operator.reported
    assert "active mesh" in operator.reported[0][1], operator.reported

    non_mesh = types.SimpleNamespace(type="EMPTY")
    operator = _fake_operator()
    assert operator.execute(_FakeContext(non_mesh)) == {"CANCELLED"}
    assert "active mesh" in operator.reported[0][1], operator.reported


def test_operator_execute_finished():
    obj = _FakeObject(
        {0: {"a": 1e-9, "b": 0.2, "c": 0.3, "d": 0.3, "e": 0.2}}
    )
    operator = _fake_operator(max_influences=1)
    outcome = operator.execute(_FakeContext(obj))
    assert outcome == {"FINISHED"}, outcome
    assert operator.reported[0][0] == {"INFO"}, operator.reported
    assert "FlexForge - cleanup" in operator.reported[0][1], operator.reported
    assert len(obj.weights_by_name(0)) == 1, obj.weights_by_name(0)


def _main():
    tests = [
        test_clean_weights_removes_epsilon,
        test_clean_weights_orphan_groups,
        test_clean_weights_influence_limit,
        test_clean_weights_errors,
        test_cleanup_message,
        test_apply_cleanup,
        test_operator_cleanup_weights,
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
