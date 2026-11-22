# Headless UI probe of FlexForge (Phase 4).
# Registers the addon in real Blender and checks that panel and operators are
# exposed in bpy.ops: it is not an interactive GUI Gate (that requires the real
# GUI with a manual check), it is the probe that the panel buttons point to
# existing and registered operators.
import sys
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import bpy  # noqa: E402

from flexforge import ui  # noqa: E402
import flexforge  # noqa: E402

OPERATOR_IDS = [
    "flexforge.create_muscle_preset",
    "flexforge.bind_muscles",
    "flexforge.bake_shape_keys",
    "flexforge.bake_bounce",
    "flexforge.weight_transfer",
    "flexforge.cleanup_weights",
    "flexforge.mirror_weights",
    "flexforge.limit_weights",
    "flexforge.verify",
    "flexforge.export_gltf",
    "flexforge.create_biceps",
]


def _register():
    """Register the addon only once per process."""
    if not getattr(bpy, "_flexforge_prova", False):
        flexforge.register()
        bpy._flexforge_prova = True


def test_panel_registered():
    _register()
    panel = ui.FLEXFORGE_PT_main
    assert panel.bl_idname == "FLEXFORGE_PT_main"
    assert panel.bl_space_type == "VIEW_3D"
    assert panel.bl_region_type == "UI"
    assert panel.bl_category == "FlexForge"


def test_operators_exposed():
    _register()
    for operator_id in OPERATOR_IDS:
        module, name = operator_id.split(".", 1)
        assert hasattr(getattr(bpy.ops, module), name), (
            "operator not exposed in bpy.ops: %s" % operator_id
        )


def test_panel_draws_all_buttons():
    _register()
    drawn = []

    class _FakeLayout:
        def box(self):
            return self

        def row(self):
            return self

        def separator(self):
            pass

        def label(self, text, icon="NONE"):
            drawn.append(("label", text))

        def operator(self, operator_id, text, icon="NONE"):
            drawn.append(("operator", operator_id))

        def prop(self, data, attr, text=None, **kwargs):
            drawn.append(("prop", text))

    import types

    panel = types.SimpleNamespace(layout=_FakeLayout())
    ui.FLEXFORGE_PT_main.draw(panel, None)
    operators = [value for kind, value in drawn if kind == "operator"]
    assert operators == OPERATOR_IDS, operators


def test_context_summary():
    _register()
    import types

    empty = types.SimpleNamespace(active_object=None)
    assert ui.context_summary(empty) == "Active: none"
    assert ui.context_summary(None) == "Active: none"

    rig_data = bpy.data.armatures.new("FFSummaryRig")
    rig = bpy.data.objects.new("FFSummaryRig", rig_data)
    mesh_data = bpy.data.meshes.new("FFSummaryMesh")
    mesh = bpy.data.objects.new("FFSummaryMesh", mesh_data)
    collection = bpy.context.scene.collection
    collection.objects.link(rig)
    collection.objects.link(mesh)
    try:
        for other in bpy.context.view_layer.objects:
            other.select_set(False)
        bpy.context.view_layer.objects.active = rig
        rig.select_set(True)
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.mode_set(mode="EDIT")
        for bone_name in ("spine", "biceps.L", "biceps.R"):
            bone = rig_data.edit_bones.new(bone_name)
            bone.head = (0.0, 0.0, 0.0)
            bone.tail = (0.0, 0.0, 1.0)
        bpy.ops.object.mode_set(mode="OBJECT")

        rig_context = types.SimpleNamespace(active_object=rig)
        assert ui.context_summary(rig_context) == (
            "Active: FFSummaryRig (ARMATURE, 3 bones)"
        ), ui.context_summary(rig_context)

        for group_name in ("biceps.L", "biceps.R"):
            mesh.vertex_groups.new(name=group_name)
        mesh_context = types.SimpleNamespace(active_object=mesh)
        assert ui.context_summary(mesh_context) == (
            "Active: FFSummaryMesh (MESH, 2 groups)"
        ), ui.context_summary(mesh_context)
    finally:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.data.objects.remove(rig, do_unlink=True)
        bpy.data.objects.remove(mesh, do_unlink=True)
        bpy.data.armatures.remove(rig_data)
        bpy.data.meshes.remove(mesh_data)


def test_muscle_status_summary():
    _register()
    import types

    assert ui.muscle_status_summary(None) == "Muscles: select a mesh"
    assert ui.muscle_status_summary(types.SimpleNamespace(
        type="ARMATURE"
    )) == "Muscles: select a mesh"

    mesh_data = bpy.data.meshes.new("FFStatusMesh")
    mesh = bpy.data.objects.new("FFStatusMesh", mesh_data)
    bpy.context.scene.collection.objects.link(mesh)
    try:
        mesh.vertex_groups.new(name="muscle_biceps")
        mesh.vertex_groups.new(name="muscle_triceps")
        mesh.vertex_groups.new(name="biceps")
        assert ui.muscle_status_summary(mesh) == (
            "Muscles: 2 groups | 0 baked keys"
        ), ui.muscle_status_summary(mesh)

        bpy.context.view_layer.objects.active = mesh
        mesh.select_set(True)
        mesh.shape_key_add(name="Basis")
        mesh.shape_key_add(name="flexforge_biceps")
        mesh.shape_key_add(name="other")
        assert ui.muscle_status_summary(mesh) == (
            "Muscles: 2 groups | 1 baked keys"
        ), ui.muscle_status_summary(mesh)
    finally:
        bpy.data.objects.remove(mesh, do_unlink=True)
        bpy.data.meshes.remove(mesh_data)


def _main():
    tests = [
        test_panel_registered,
        test_operators_exposed,
        test_panel_draws_all_buttons,
        test_context_summary,
        test_muscle_status_summary,
    ]
    passed = failed = 0
    for case in tests:
        try:
            case()
        except Exception:
            failed += 1
            traceback.print_exc()
        else:
            passed += 1
    print(
        "VERDICT_UI_OK | passati=%d falliti=%d totale=%d"
        % (passed, failed, passed + failed)
    )
    print("RISULTATO passati=%d falliti=%d totale=%d" % (passed, failed, passed + failed))
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(_main())
