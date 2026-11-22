# Deterministic headless test of the FlexForge weight transfer.
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

    stub_folder = "/home/pierofra/.cache/opencode/tmp"
    if stub_folder not in sys.path:
        sys.path.insert(0, stub_folder)
    from flexforge_stub import installa_stub_bpy as install_bpy_stub

    installed = install_bpy_stub(props_default=True)
    # The shared stub does not expose FloatProperty (needed by max_distance):
    # the test adds it, not the addon code.
    import bpy
    if not hasattr(bpy.props, "FloatProperty"):
        bpy.props.FloatProperty = lambda **kwargs: dict(kwargs)
    return installed


_install_bpy_stub()

import bpy  # noqa: E402

from flexforge import spatial_grid  # noqa: E402
from flexforge import weight_transfer  # noqa: E402


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
    """Fake vertex with coordinates and group read from the fake mesh."""

    def __init__(self, mesh, index, coordinates):
        self._mesh = mesh
        self.index = index
        self.co = tuple(coordinates)

    @property
    def groups(self):
        present = self._mesh.weights.get(self.index, {})
        return [
            _FakeGroupElement(index, weight)
            for index, weight in sorted(present.items())
        ]


class _FakeObject:
    """Fake mesh object with coordinates, indexed vertices and groups."""

    def __init__(self, coordinates, weights_per_vertex=None, groups=()):
        self.type = "MESH"
        weights_per_vertex = weights_per_vertex or {}
        names = list(groups)
        for vertex, weight_groups in weights_per_vertex.items():
            for name in weight_groups:
                if name not in names:
                    names.append(name)
        self.vertex_groups = [
            _FakeGroup(self, name, index) for index, name in enumerate(names)
        ]
        indices = {group.name: group.index for group in self.vertex_groups}
        self.weights = {index: {} for index in range(len(coordinates))}
        for vertex, weight_groups in weights_per_vertex.items():
            self.weights[vertex] = {
                indices[name]: weight
                for name, weight in weight_groups.items()
                if weight != 0.0
            }
        self.data = types.SimpleNamespace(
            vertices=[
                _FakeVertex(self, index, coordinates[index])
                for index in range(len(coordinates))
            ]
        )

    def weights_by_name(self, vertex):
        names = {group.index: group.name for group in self.vertex_groups}
        return {
            names[index]: weight
            for index, weight in self.weights.get(vertex, {}).items()
        }


def test_invert_group_name():
    assert weight_transfer.invert_group_name("arm.L") == "arm.R"
    assert weight_transfer.invert_group_name("arm.R") == "arm.L"
    assert weight_transfer.invert_group_name("hand_L") == "hand_R"
    assert weight_transfer.invert_group_name("hand_R") == "hand_L"
    assert weight_transfer.invert_group_name("spine") == "spine"


def test_map_groups():
    reference = ["arm.L", "arm.R", "shoulder"]
    target = ["arm.R", "arm.L"]
    mapping = weight_transfer.map_groups(reference, target)
    assert mapping == {"arm.L": "arm.L", "arm.R": "arm.R"}, mapping
    assert "shoulder" not in mapping, mapping

    inverted = weight_transfer.map_groups(reference, target, True)
    assert inverted == {"arm.L": "arm.R", "arm.R": "arm.L"}, (
        inverted
    )


def test_nearest_vertex():
    coordinates = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)]
    assert weight_transfer.nearest_vertex((0.9, 0.0, 0.0), coordinates, 0.5) == 1
    assert weight_transfer.nearest_vertex((5.0, 0.0, 0.0), coordinates, 0.05) is None
    # Inclusive threshold: distance exactly equal to the limit.
    assert weight_transfer.nearest_vertex((0.05, 0.0, 0.0), coordinates, 0.05) == 0
    # Zero threshold: exact coincidence only.
    assert weight_transfer.nearest_vertex((0.0, 0.0, 0.0), coordinates, 0.0) == 0
    assert weight_transfer.nearest_vertex((0.1, 0.0, 0.0), coordinates, 0.0) is None

    error = None
    try:
        weight_transfer.nearest_vertex((0.0, 0.0, 0.0), coordinates, -0.1)
    except weight_transfer.TransferError as exception:
        error = exception
    assert error is not None, "expected TransferError with a negative threshold"
    assert "negative" in str(error), str(error)


def test_compute_transfer():
    reference_weights = {
        0: {"arm.L": 0.6, "arm.R": 0.4, "other": 1.0},
        1: {"arm.L": 1.0},
    }
    reference_coordinates = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)]
    target_coordinates = [(0.01, 0.0, 0.0), (9.99, 0.0, 0.0), (20.0, 0.0, 0.0)]
    mapping = {"arm.L": "hand.L", "arm.R": "hand.R"}

    result = weight_transfer.compute_transfer(
        reference_weights,
        reference_coordinates,
        target_coordinates,
        mapping,
        0.5,
    )
    assert result["vertices"] == 3, result
    assert result["vertices_transferred"] == 2, result
    assert result["vertices_out_of_range"] == 1, result
    assert result["ignored_groups"] == ["other"], result["ignored_groups"]
    assert result["weights"][0] == {"hand.L": 0.6, "hand.R": 0.4}, result["weights"]
    assert result["weights"][1] == {"hand.L": 1.0}, result["weights"]
    assert result["weights"][2] == {}, result["weights"]
    assert reference_weights[0]["other"] == 1.0, "the input must not be modified"


def test_compute_influence_limit():
    reference_weights = {
        0: {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.35, "e": 0.05},
    }
    mapping = {name: name for name in ("a", "b", "c", "d", "e")}
    result = weight_transfer.compute_transfer(
        reference_weights,
        [(0.0, 0.0, 0.0)],
        [(0.0, 0.0, 0.0)],
        mapping,
        0.01,
        4,
    )
    weights = result["weights"][0]
    assert len(weights) == 4, weights
    assert "e" not in weights, weights
    assert abs(sum(weights.values()) - 1.0) < 1e-6, weights


def test_max_influences_error():
    error = None
    try:
        weight_transfer.compute_transfer(
            {0: {"a": 1.0}}, [(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)], {"a": "a"}, 0.1, 0
        )
    except weight_transfer.WeightsError as exception:
        error = exception
    assert error is not None, "expected WeightsError with max_influences=0"


def test_apply_transfer():
    reference = _FakeObject(
        [(0.0, 0.0, 0.0)], {0: {"arm.L": 1.0}}
    )
    target = _FakeObject(
        [(0.001, 0.0, 0.0), (1.0, 0.0, 0.0)], groups=["arm.L"]
    )
    report = weight_transfer.apply_transfer(
        reference, target, False, 0.01
    )
    assert report["vertices"] == 2, report
    assert report["vertices_transferred"] == 1, report
    assert report["vertices_out_of_range"] == 1, report
    assert report["ignored_groups"] == [], report
    assert target.weights_by_name(0) == {"arm.L": 1.0}, (
        target.weights_by_name(0)
    )
    assert target.weights_by_name(1) == {}, target.weights_by_name(1)


def test_apply_transfer_inversion():
    reference = _FakeObject(
        [(0.0, 0.0, 0.0)], {0: {"arm.L": 0.25, "arm.R": 0.75}}
    )
    target = _FakeObject(
        [(0.0, 0.0, 0.0)], groups=["arm.R", "arm.L"]
    )
    report = weight_transfer.apply_transfer(
        reference, target, True, 0.01
    )
    assert report["vertices_transferred"] == 1, report
    assert target.weights_by_name(0) == {
        "arm.R": 0.25,
        "arm.L": 0.75,
    }, target.weights_by_name(0)


def test_transfer_message():
    report = {
        "vertices": 3,
        "vertices_transferred": 2,
        "vertices_out_of_range": 1,
        "ignored_groups": ["a", "b"],
    }
    expected = (
        "FlexForge - transfer: vertices=3 transferred=2 out_of_range=1 "
        "ignored_groups=2"
    )
    assert weight_transfer.transfer_message(report) == expected, (
        weight_transfer.transfer_message(report)
    )


def test_operator_weight_transfer():
    cls = weight_transfer.FLEXFORGE_OT_weight_transfer
    assert cls.bl_idname == "flexforge.weight_transfer", cls.bl_idname
    assert "REGISTER" in cls.bl_options, cls.bl_options
    assert "UNDO" in cls.bl_options, cls.bl_options
    annotations = getattr(cls, "__annotations__", {})
    for name in ("max_distance", "invert_lr", "max_influences"):
        assert name in annotations, "missing property: %s" % name
    assert hasattr(cls, "bl_label"), "bl_label missing"


def test_build_spatial_grid_rejects_zero_cell_size():
    coordinates = [(0.0, 0.0, 0.0), (1.5, -0.5, 0.0), None]
    for bad in (0.0, -0.25):
        error = None
        try:
            spatial_grid.build_spatial_grid(coordinates, bad)
        except ValueError as exception:
            error = exception
        assert error is not None, "expected ValueError with cell_size=%r" % bad
        assert str(error) == "cell_size must be positive.", str(error)
    # A positive cell size still buckets the vertices and skips the None ones.
    grid = spatial_grid.build_spatial_grid(coordinates, 1.0)
    assert grid[(0, 0, 0)] == [0], grid
    assert grid[(1, -1, 0)] == [1], grid
    assert spatial_grid.build_spatial_grid([], 1.0) == {}


def _main():
    tests = [
        test_invert_group_name,
        test_map_groups,
        test_nearest_vertex,
        test_compute_transfer,
        test_compute_influence_limit,
        test_max_influences_error,
        test_apply_transfer,
        test_apply_transfer_inversion,
        test_transfer_message,
        test_operator_weight_transfer,
        test_build_spatial_grid_rejects_zero_cell_size,
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
