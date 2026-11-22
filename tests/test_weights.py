# Deterministic headless test of the FlexForge weight utilities.
# If bpy is missing the shared stub is installed; the test mesh is fake (same
# minimal interface as Mesh/VertexGroup) and works inside Blender too.

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

from flexforge import weights  # noqa: E402


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

    def __init__(self, weights_per_vertex):
        self.type = "MESH"
        names = []
        for groups in weights_per_vertex.values():
            for name in groups:
                if name not in names:
                    names.append(name)
        self.vertex_groups = [
            _FakeGroup(self, name, index) for index, name in enumerate(names)
        ]
        indices = {
            name: group.index for name, group in
            ((g.name, g) for g in self.vertex_groups)
        }
        self.weights = {}
        for vertex, groups in weights_per_vertex.items():
            self.weights[vertex] = {
                indices[name]: weight
                for name, weight in groups.items()
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


def test_normalize_negative_sum():
    error = None
    try:
        weights.normalize({0: {"a": -1.0, "b": 0.5}})
    except weights.WeightsError as exception:
        error = exception
    assert error is not None, "expected WeightsError with a negative sum"
    assert "Negative" in str(error), str(error)


def test_budget_report_ignores_residuals():
    weights_map = {
        0: {"a": 0.5, "b": 0.5, "c": 1e-9},
        1: {"a": 1.0},
    }
    report = weights.budget_report(weights_map, 2)
    assert report["vertices"] == 2, report
    assert report["over_budget"] == 0, report
    assert report["max_influences"] == 2, report


def test_read_weights():
    obj = _FakeObject(
        {0: {"a": 1.0, "b": 0.25}, 1: {"b": 0.5}, 2: {}}
    )
    read = weights.read_weights(obj)
    assert read[0] == {"a": 1.0, "b": 0.25}, read[0]
    assert read[1] == {"b": 0.5}, read[1]
    assert read[2] == {}, read[2]
    assert set(read) == {0, 1, 2}, sorted(read)


def test_write_weights():
    obj = _FakeObject({0: {"a": 0.5, "b": 0.5}})
    weights.write_weights(obj, {0: {"a": 1.0}})
    assert obj.weights_by_name(0) == {"a": 1.0}, obj.weights_by_name(0)


def test_apply_limit():
    obj = _FakeObject(
        {
            0: {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4, "e": 0.5},
            1: {"a": 1.0},
        }
    )
    report = weights.apply_limit(obj, 4)
    assert report["vertices"] == 2, report
    assert report["over_budget"] == 0, report
    assert report["max_influences"] == 4, report
    written = obj.weights_by_name(0)
    assert len(written) == 4, written
    assert "a" not in written, written
    assert abs(sum(written.values()) - 1.0) < 1e-6, written
    assert abs(obj.weights_by_name(1)["a"] - 1.0) < 1e-6, obj.weights_by_name(1)


def test_message_report():
    message = weights.message_report(
        {"vertices": 3, "over_budget": 1, "max_influences": 5}
    )
    expected = "FlexForge - weights: vertices=3 over_budget=1 max_influences=5"
    assert message == expected, message


def test_normalize():
    weights_map = {
        0: {"a": 2.0, "b": 6.0},
        1: {"a": 0.0, "b": 0.0},
    }
    result = weights.normalize(weights_map)
    assert abs(sum(result[0].values()) - 1.0) < 1e-6, result[0]
    assert abs(result[0]["a"] - 0.25) < 1e-6, result[0]
    assert result[1] == {"a": 0.0, "b": 0.0}, result[1]
    assert weights_map[0]["a"] == 2.0, "the input must not be modified"


def test_limit_influences():
    weights_map = {
        0: {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4, "e": 0.5},
        1: {"a": 1.0},
    }
    result = weights.limit_influences(weights_map, 4)
    assert len(result[0]) == 4, result[0]
    assert "a" not in result[0], "kept the weakest influence: %s" % result[0]
    assert abs(sum(result[0].values()) - 1.0) < 1e-6, result[0]
    assert abs(result[1]["a"] - 1.0) < 1e-6, result[1]
    assert len(weights_map[0]) == 5, "the input must not be modified"


def test_budget_report():
    weights_map = {
        0: {"a": 0.5, "b": 0.3, "c": 0.2},
        1: {"a": 1.0},
        2: {"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.125, "e": 0.125},
    }
    report = weights.budget_report(weights_map, 4)
    assert report["vertices"] == 3, report
    assert report["over_budget"] == 1, report
    assert report["max_influences"] == 5, report


def test_invalid_limit_error():
    error = None
    try:
        weights.limit_influences({0: {"a": 1.0}}, 0)
    except weights.WeightsError as exception:
        error = exception
    assert error is not None, "expected WeightsError with max_influences=0"


def _main():
    tests = [
        test_normalize,
        test_normalize_negative_sum,
        test_limit_influences,
        test_budget_report,
        test_budget_report_ignores_residuals,
        test_invalid_limit_error,
        test_read_weights,
        test_write_weights,
        test_apply_limit,
        test_message_report,
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
