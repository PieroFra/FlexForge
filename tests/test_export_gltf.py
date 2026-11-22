# Deterministic headless test of the FlexForge glTF export.
# If bpy is missing the shared stub is installed; the real exporter is never
# invoked: `bpy.ops.export_scene.gltf` is replaced by a fake that records the
# parameters, so the test runs outside Blender too.

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

from flexforge import export_gltf  # noqa: E402

_calls = []


_selections_during_export = []


def _fake_gltf(**kwargs):
    """Fake `bpy.ops.export_scene.gltf` that keeps the received parameters."""
    _calls.append(kwargs)
    return {"FINISHED"}


def _fake_gltf_capture(_context_ref):
    def _fake(**kwargs):
        _calls.append(kwargs)
        _selections_during_export.append(
            [
                (obj.name, getattr(obj, "selected", None))
                for obj in _context_ref()
            ]
        )
        return {"FINISHED"}

    return _fake


bpy.ops.export_scene = types.SimpleNamespace(gltf=_fake_gltf)


class _FakeArmature:
    """Fake armature with a real number of bones."""

    def __init__(self, name, bones):
        self.type = "ARMATURE"
        self.name = name
        self.selected = False
        self.parent = None
        self.data = types.SimpleNamespace(
            bones=[types.SimpleNamespace(name="bone_%d" % i) for i in range(bones)]
        )

    def select_set(self, state):
        self.selected = bool(state)


class _FakeMesh:
    """Fake mesh with minimal modifiers, parent, weights and selection."""

    def __init__(self, modifiers=(), parent=None):
        self.type = "MESH"
        self.name = "FakeMesh"
        self.modifiers = list(modifiers)
        self.parent = parent
        self.selected = False
        self.vertex_groups = []
        self.data = types.SimpleNamespace(vertices=[])

    def select_set(self, state):
        self.selected = bool(state)


class _FakeGroup:
    """Fake vertex group that keeps the written weights."""

    def __init__(self, index, name):
        self.index = index
        self.name = name
        self.weights = {}

    def add(self, indices, weight, kind):
        for index in indices:
            self.weights[index] = weight

    def remove(self, indices):
        for index in indices:
            self.weights.pop(index, None)


class _FakeVertex:
    """Fake vertex with groups and weights read by `read_weights`."""

    def __init__(self, index, groups):
        self.index = index
        self.groups = [
            types.SimpleNamespace(group=group.index, weight=weight)
            for group, weight in groups
        ]


def _mesh_with_weights(influences):
    """Fake mesh with one vertex and `influences` groups at equal weight."""
    mesh = _FakeMesh()
    mesh.vertex_groups = [
        _FakeGroup(index, "group_%d" % index) for index in range(influences)
    ]
    mesh.data = types.SimpleNamespace(
        vertices=[
            _FakeVertex(
                0,
                [
                    (group, 1.0 / influences)
                    for group in mesh.vertex_groups
                ],
            )
        ]
    )
    return mesh


def _armature_modifier(armature):
    return types.SimpleNamespace(type="ARMATURE", object=armature)


class _FakeViewLayerObjects:
    """Fake view layer collection: iterable and with an active object."""

    def __init__(self, objects, active):
        self._objects = list(objects)
        self.active = active

    def __iter__(self):
        return iter(self._objects)


def _context(mesh, selected=(), objects=()):
    entries = list(objects) + list(selected)
    if mesh is not None:
        entries.append(mesh)
    return types.SimpleNamespace(
        view_layer=types.SimpleNamespace(
            objects=_FakeViewLayerObjects(entries, mesh)
        ),
        selected_objects=list(selected),
    )


def _export_error(callable_):
    """Run `callable_` and return the ExportError exception or None."""
    try:
        callable_()
    except export_gltf.ExportError as exception:
        return exception
    return None


def test_validate_path_not_glb():
    mesh = _FakeMesh(modifiers=[_armature_modifier(_FakeArmature("Rig", 2))])
    error = _export_error(
        lambda: export_gltf.export_glb(_context(mesh), "/tmp/mesh.gltf")
    )
    assert error is not None, "expected ExportError with a .gltf extension"
    assert "glb" in str(error), str(error)
    assert _calls == [], "the exporter must not be called"


def test_validate_path_empty():
    mesh = _FakeMesh(modifiers=[_armature_modifier(_FakeArmature("Rig", 2))])
    error = _export_error(
        lambda: export_gltf.export_glb(_context(mesh), "   ")
    )
    assert error is not None, "expected ExportError with an empty path"
    assert "Missing" in str(error), str(error)


def test_validate_path_without_name():
    mesh = _FakeMesh(modifiers=[_armature_modifier(_FakeArmature("Rig", 2))])
    error = _export_error(
        lambda: export_gltf.export_glb(_context(mesh), "/tmp/.glb")
    )
    assert error is not None, "expected ExportError without a file name"
    assert "file name" in str(error), str(error)


def test_active_mesh_missing():
    error = _export_error(
        lambda: export_gltf.export_glb(_context(None), "/tmp/mesh.glb")
    )
    assert error is not None, "expected ExportError without an active mesh"
    assert "active mesh" in str(error), str(error)
    assert _calls == [], "the exporter must not be called"


def test_active_object_not_mesh():
    armature = _FakeArmature("Rig", 2)
    error = _export_error(
        lambda: export_gltf.export_glb(_context(armature), "/tmp/mesh.glb")
    )
    assert error is not None, "expected ExportError with a non-mesh active object"
    assert "active mesh" in str(error), str(error)


def test_armature_missing():
    mesh = _FakeMesh()
    error = _export_error(
        lambda: export_gltf.export_glb(_context(mesh), "/tmp/mesh.glb")
    )
    assert error is not None, "expected ExportError without an armature"
    assert "armature" in str(error), str(error)
    assert _calls == [], "the exporter must not be called"


def test_export_counts_bones_and_meshes():
    armature = _FakeArmature("Rig", 3)
    mesh = _FakeMesh(modifiers=[_armature_modifier(armature)])
    result = export_gltf.export_glb(_context(mesh), "/tmp/mesh.glb")
    assert result == {
        "file": "/tmp/mesh.glb",
        "bones": 3,
        "meshes": 1,
    }, result
    assert len(_calls) == 1, _calls
    parameters = _calls[0]
    assert parameters["filepath"] == "/tmp/mesh.glb", parameters
    assert parameters["export_format"] == "GLB", parameters
    assert parameters["use_selection"] is True, parameters
    assert parameters["export_skins"] is True, parameters
    # During the export mesh+armature are selected; once the export is done
    # the previous selection (empty) is restored.
    assert mesh.selected is False, mesh.selected
    assert armature.selected is False, armature.selected


def test_export_selected_armature():
    armature = _FakeArmature("Rig", 5)
    mesh = _FakeMesh()
    result = export_gltf.export_glb(
        _context(mesh, selected=[armature]), "/tmp/mesh.glb"
    )
    assert result["bones"] == 5, result
    assert result["meshes"] == 1, result


def test_export_armature_from_parent():
    armature = _FakeArmature("RigParent", 4)
    mesh = _FakeMesh(parent=armature)
    result = export_gltf.export_glb(_context(mesh), "/tmp/mesh.glb")
    assert result["bones"] == 4, result
    assert result["meshes"] == 1, result
    # Selection restored after the export: the active object is not selected.
    assert mesh.selected is False, mesh.selected
    assert armature.selected is False, armature.selected


def test_export_selects_only_mesh_armature_and_helpers():
    armature = _FakeArmature("Rig", 2)
    imported = _FakeArmature("ImportedRig", 2)
    mesh = _FakeMesh(modifiers=[_armature_modifier(armature)])
    helper = _FakeMesh(parent=armature)
    unrelated = _FakeMesh(parent=imported)
    result = export_gltf.export_glb(
        _context(mesh, objects=[helper, unrelated]), "/tmp/mesh.glb"
    )
    assert result["meshes"] == 2, result
    # Previous selection restored: everything unselected.
    assert mesh.selected is False, mesh.selected
    assert armature.selected is False, armature.selected
    assert helper.selected is False, helper.selected
    assert unrelated.selected is False, unrelated.selected


def test_export_applies_influence_budget():
    armature = _FakeArmature("Rig", 2)
    mesh = _mesh_with_weights(6)
    mesh.modifiers = [_armature_modifier(armature)]
    export_gltf.export_glb(
        _context(mesh), "/tmp/mesh.glb", max_influences=4
    )
    influences = [
        group for group in mesh.vertex_groups if group.weights.get(0, 0.0) > 0.0
    ]
    assert len(influences) == 4, [group.name for group in influences]
    total = sum(group.weights[0] for group in influences)
    assert abs(total - 1.0) <= 1e-6, total


def test_operator_export_gltf():
    armature = _FakeArmature("Rig", 2)
    mesh = _FakeMesh(modifiers=[_armature_modifier(armature)])

    class _Operator:
        execute = export_gltf.FLEXFORGE_OT_export_gltf.execute

        def __init__(self, path, max_influences):
            self.path = path
            self.max_influences = max_influences
            self.reported = []

        def report(self, levels, message):
            self.reported.append((levels, message))

    operator = _Operator("/tmp/op.glb", 4)
    outcome = operator.execute(_context(mesh))
    assert outcome == {"FINISHED"}, outcome
    assert len(_calls) == 1, _calls
    assert _calls[0]["filepath"] == "/tmp/op.glb", _calls[0]
    assert len(operator.reported) == 1, operator.reported
    assert "meshes=1" in operator.reported[0][1], operator.reported


def test_operator_export_gltf_error():
    armature = _FakeArmature("Rig", 2)
    mesh = _FakeMesh(modifiers=[_armature_modifier(armature)])

    class _Operator:
        execute = export_gltf.FLEXFORGE_OT_export_gltf.execute

        def __init__(self):
            self.path = "/tmp/op.gltf"
            self.max_influences = 4
            self.reported = []

        def report(self, levels, message):
            self.reported.append((levels, message))

    operator = _Operator()
    outcome = operator.execute(_context(mesh))
    assert outcome == {"CANCELLED"}, outcome
    assert _calls == [], "the exporter must not be called"
    assert operator.reported[0][0] == {"ERROR"}, operator.reported


def test_export_message():
    message = export_gltf.export_message(
        {"file": "/tmp/mesh.glb", "bones": 3, "meshes": 1}, 4
    )
    expected = "FlexForge - glTF: file=/tmp/mesh.glb bones=3 meshes=1 max_influences=4"
    assert message == expected, message


def test_exporter_missing():
    armature = _FakeArmature("Rig", 2)
    mesh = _FakeMesh(modifiers=[_armature_modifier(armature)])
    original = bpy.ops.export_scene
    bpy.ops.export_scene = types.SimpleNamespace()
    try:
        error = _export_error(
            lambda: export_gltf.export_glb(_context(mesh), "/tmp/mesh.glb")
        )
    finally:
        bpy.ops.export_scene = original
    assert error is not None, "expected ExportError without an exporter"
    assert "not available" in str(error), str(error)


def test_exporter_fails():
    armature = _FakeArmature("Rig", 2)
    mesh = _FakeMesh(modifiers=[_armature_modifier(armature)])

    def _gltf_error(**kwargs):
        raise RuntimeError("fake exporter error")

    original = bpy.ops.export_scene
    bpy.ops.export_scene = types.SimpleNamespace(gltf=_gltf_error)
    try:
        error = _export_error(
            lambda: export_gltf.export_glb(_context(mesh), "/tmp/mesh.glb")
        )
    finally:
        bpy.ops.export_scene = original
    assert error is not None, "expected ExportError with a failing exporter"
    assert "failed" in str(error), str(error)
    assert mesh.selected is False, "selection restored after the error"


def test_selection_restored_after_export():
    armature = _FakeArmature("Rig", 2)
    mesh = _FakeMesh(modifiers=[_armature_modifier(armature)])
    unrelated = _FakeMesh()
    unrelated.selected = True
    context = _context(mesh, selected=[unrelated], objects=[unrelated])
    original = bpy.ops.export_scene
    bpy.ops.export_scene = types.SimpleNamespace(gltf=_fake_gltf)
    try:
        export_gltf.export_glb(context, "/tmp/mesh.glb")
    finally:
        bpy.ops.export_scene = original
    assert unrelated.selected is True, unrelated.selected
    assert mesh.selected is False, mesh.selected
    assert armature.selected is False, armature.selected
    assert context.selected_objects == [unrelated], context.selected_objects


def test_selection_during_export():
    armature = _FakeArmature("Rig", 2)
    mesh = _FakeMesh(modifiers=[_armature_modifier(armature)])
    helper = _FakeMesh(parent=armature)
    context = _context(mesh, objects=[armature, helper])
    del _selections_during_export[:]
    original = bpy.ops.export_scene
    bpy.ops.export_scene = types.SimpleNamespace(
        gltf=_fake_gltf_capture(lambda: _objects(context))
    )
    try:
        export_gltf.export_glb(context, "/tmp/mesh.glb")
    finally:
        bpy.ops.export_scene = original
    assert len(_selections_during_export) == 1, _selections_during_export
    during = dict(_selections_during_export[0])
    assert during[mesh.name] is True, during
    assert during[armature.name] is True, during
    assert during[helper.name] is True, during


def _objects(context):
    return list(context.view_layer.objects)


def _main():
    tests = [
        test_validate_path_not_glb,
        test_validate_path_empty,
        test_validate_path_without_name,
        test_active_mesh_missing,
        test_active_object_not_mesh,
        test_armature_missing,
        test_export_counts_bones_and_meshes,
        test_export_selected_armature,
        test_export_armature_from_parent,
        test_export_selects_only_mesh_armature_and_helpers,
        test_export_applies_influence_budget,
        test_operator_export_gltf,
        test_operator_export_gltf_error,
        test_export_message,
        test_exporter_missing,
        test_exporter_fails,
        test_selection_restored_after_export,
        test_selection_during_export,
    ]

    passed = 0
    failed = 0
    for case in tests:
        del _calls[:]
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
