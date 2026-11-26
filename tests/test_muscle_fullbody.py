# Headless test of the FlexForge Phase 1.6 full-body end-to-end operator.
# Real bpy when available, otherwise the shared stub; real-Blender integration
# and single-undo tests are skipped on the stub, which has no operator stack.
import importlib.util
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


_FAKE = _install_bpy_stub()

from flexforge import fullbody_pipeline, muscle_fullbody, rig_detect  # noqa: E402


FAKE_REPORT = {
    "preset_ids": [],
    "rig_type": "unknown",
    "coverage": 0.0,
    "matched": 0,
    "missing": 0,
    "topology_ok": None,
    "topology_checked": 0,
    "topology_bad": [],
    "matched_bones": {},
}


def _mixamo_data():
    """The Mixamo names/parents of the rig detect suite, reused when possible."""
    path = BASE / "tests" / "test_rig_detect.py"
    try:
        spec = importlib.util.spec_from_file_location("test_rig_detect_suite", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module._MIXAMO_NAMES, module._MIXAMO_PARENTS
    except Exception:
        names = [
            "mixamorig:Hips", "mixamorig:LeftArm", "mixamorig:RightArm",
            "mixamorig:LeftForeArm", "mixamorig:RightForeArm",
            "mixamorig:LeftShoulder", "mixamorig:RightShoulder",
            "mixamorig:LeftUpLeg", "mixamorig:RightUpLeg",
            "mixamorig:LeftLeg", "mixamorig:RightLeg",
            "mixamorig:LeftFoot", "mixamorig:RightFoot",
            "mixamorig:Spine", "mixamorig:Spine1", "mixamorig:Spine2",
        ]
        parents = {
            "mixamorig:Hips": "",
            "mixamorig:Spine": "mixamorig:Hips",
            "mixamorig:Spine1": "mixamorig:Spine",
            "mixamorig:Spine2": "mixamorig:Spine1",
            "mixamorig:LeftShoulder": "mixamorig:Spine1",
            "mixamorig:RightShoulder": "mixamorig:Spine1",
            "mixamorig:LeftArm": "mixamorig:LeftShoulder",
            "mixamorig:RightArm": "mixamorig:RightShoulder",
            "mixamorig:LeftForeArm": "mixamorig:LeftArm",
            "mixamorig:RightForeArm": "mixamorig:RightArm",
            "mixamorig:LeftUpLeg": "mixamorig:Hips",
            "mixamorig:RightUpLeg": "mixamorig:Hips",
            "mixamorig:LeftLeg": "mixamorig:LeftUpLeg",
            "mixamorig:RightLeg": "mixamorig:RightUpLeg",
            "mixamorig:LeftFoot": "mixamorig:LeftLeg",
            "mixamorig:RightFoot": "mixamorig:RightLeg",
        }
        return names, parents


def test_operator_definition():
    cls = muscle_fullbody.FLEXFORGE_OT_apply_full_body
    assert cls.bl_idname == "flexforge.apply_full_body", cls.bl_idname
    assert cls.bl_label == "Create full body", cls.bl_label
    assert "mirror_lr" in cls.__annotations__, cls.__annotations__


def test_operator_properties_complete():
    annotations = muscle_fullbody.FLEXFORGE_OT_apply_full_body.__annotations__
    expected = (
        "mirror_lr",
        "bind_radius",
        "displacement",
        "anatomical_taper",
        "directional_bias",
        "smooth_iterations",
        "drive_by_pose",
        "max_influences",
        "lod",
    )
    for prop in expected:
        assert prop in annotations, "Missing property %s on operator" % prop


def test_apply_full_body_no_presets():
    from flexforge.rig_detect import apply_full_body

    mesh = types.SimpleNamespace(
        type="MESH", modifiers=(), parent=None, data=types.SimpleNamespace()
    )
    report = apply_full_body(mesh, dict(FAKE_REPORT), mirror_lr=True)
    assert report["created"] == [], report
    assert "no presets available" in report["message"], report["message"]

    armature = types.SimpleNamespace(
        type="ARMATURE", data=types.SimpleNamespace(bones=[])
    )
    report = apply_full_body(
        armature, dict(FAKE_REPORT), armature=armature, mirror_lr=False
    )
    assert report["created"] == [], report
    assert "no presets available" in report["message"], report["message"]


def test_detect_rig_mixamo_nine_presets():
    names, parents = _mixamo_data()
    report = rig_detect.detect_rig(names, parents)
    assert report["rig_type"] == "mixamo", report
    assert report["topology_ok"] is True, report
    assert len(report["preset_ids"]) == 9, report
    assert report["preset_ids"] == [
        "biceps", "triceps", "deltoid", "pectoral",
        "latissimus", "quadriceps", "hamstring", "calf", "gluteus",
    ], report["preset_ids"]


def test_full_body_message_counts_created():
    report = {
        "rig_type": "standard",
        "coverage": 1.0,
        "matched": 9,
        "missing": 0,
        "preset_ids": ["biceps", "triceps"],
        "topology_ok": None,
        "topology_checked": 0,
        "topology_bad": [],
        "matched_bones": {},
    }
    message = muscle_fullbody.full_body_message(report, 4, ["biceps", "triceps"])
    assert message.startswith("FlexForge - rig: type=standard"), message
    assert "created 4 bones on 2 presets" in message, message
    empty = muscle_fullbody.full_body_message(report, 0, [])
    assert "created" not in empty, empty


def test_resolve_targets_mesh_and_armature():
    rig = types.SimpleNamespace(type="ARMATURE", name="Rig")
    mod = types.SimpleNamespace(type="ARMATURE", object=rig)
    mesh1 = types.SimpleNamespace(type="MESH", name="Body", modifiers=[mod], parent=None)
    mesh2 = types.SimpleNamespace(type="MESH", name="Other", modifiers=[], parent=None)
    ctx = types.SimpleNamespace(
        view_layer=types.SimpleNamespace(objects=types.SimpleNamespace(active=mesh1)),
        scene=types.SimpleNamespace(objects=[rig, mesh1, mesh2]),
    )
    resolved_rig, resolved_meshes = fullbody_pipeline.resolve_targets(ctx)
    assert resolved_rig is rig and resolved_meshes == [mesh1]

    ctx.view_layer.objects.active = rig
    resolved_rig, resolved_meshes = fullbody_pipeline.resolve_targets(ctx)
    assert resolved_rig is rig and resolved_meshes == [mesh1]

    ctx.scene.objects = [rig, mesh2]
    try:
        fullbody_pipeline.resolve_targets(ctx)
        assert False, "Expected FullBodyError when armature has no bound mesh"
    except fullbody_pipeline.FullBodyError:
        pass

    try:
        fullbody_pipeline.resolve_targets(ctx, active=mesh2)
        assert False, "Expected FullBodyError when mesh has no armature"
    except fullbody_pipeline.FullBodyError:
        pass


def test_pipeline_order_and_rollback():
    calls = []
    fake_bones = [
        types.SimpleNamespace(name=n, parent=None, use_deform=True)
        for n in _mixamo_data()[0]
    ]
    rig = types.SimpleNamespace(
        type="ARMATURE",
        name="Rig",
        mode="OBJECT",
        data=types.SimpleNamespace(bones=fake_bones),
    )
    mesh = types.SimpleNamespace(
        type="MESH",
        name="Body",
        vertex_groups=[],
        data=types.SimpleNamespace(shape_keys=None),
    )

    originals = {
        "_select_only": fullbody_pipeline._select_only,
        "_set_mode_no_undo": fullbody_pipeline._set_mode_no_undo,
        "create_preset_muscles": fullbody_pipeline.create_preset_muscles,
        "setup_preset_constraints": fullbody_pipeline.setup_preset_constraints,
        "apply_muscle_skinning": fullbody_pipeline.apply_muscle_skinning,
        "apply_muscle_bake": fullbody_pipeline.apply_muscle_bake,
        "validate_deformation": fullbody_pipeline.validate_deformation,
        "apply_engine_budget": fullbody_pipeline.apply_engine_budget,
        "_rollback_state": fullbody_pipeline._rollback_state,
    }
    try:
        fullbody_pipeline._select_only = lambda a, s: None
        fullbody_pipeline._set_mode_no_undo = lambda a, m: (setattr(a, "mode", m), None)[1]
        fullbody_pipeline.create_preset_muscles = lambda a, pid, mirror_lr=True: (
            calls.append(("create", pid, a.mode)) or [("spec", ["muscle_%s_01" % pid])]
        )
        fullbody_pipeline.setup_preset_constraints = lambda a, c: (
            calls.append(("constraints", a.mode, len(c))) or len(c)
        )
        fullbody_pipeline.apply_muscle_skinning = lambda m, **kw: (
            calls.append(("skin", m.name)) or {"weights": {0: {"b": 1.0}}}
        )
        fullbody_pipeline.apply_muscle_bake = lambda m, **kw: (
            calls.append(("bake", m.name)) or {"shape_keys": 2, "drivers_added": 2}
        )
        fullbody_pipeline.validate_deformation = lambda w, hb, mi: (
            calls.append(("verify", mi)) or {"valid": False, "reason": "test warn"}
        )
        fullbody_pipeline.apply_engine_budget = lambda m, **kw: (
            calls.append(("budget", kw["lod"])) or {"report": {"within_budget": True}}
        )
        res = fullbody_pipeline.run_full_body_pipeline(rig, [mesh])
        assert res["warnings"] == ["Body: test warn"], res
        assert calls[0][0] == "create" and calls[0][2] == "EDIT", calls
        con_idx = [i for i, c in enumerate(calls) if c[0] == "constraints"][0]
        assert calls[con_idx][1] == "OBJECT", calls[con_idx]
        tail_stages = [c[0] for c in calls[con_idx + 1:]]
        assert tail_stages == ["skin", "bake", "verify", "budget"], tail_stages

        rolled_back = []
        fullbody_pipeline._rollback_state = lambda a, ms, snap: rolled_back.append(True)
        def _fail_bake(*a, **kw):
            raise fullbody_pipeline.BakeError("boom")
        fullbody_pipeline.apply_muscle_bake = _fail_bake
        try:
            fullbody_pipeline.run_full_body_pipeline(rig, [mesh])
            assert False, "Expected BakeError"
        except fullbody_pipeline.BakeError:
            assert rolled_back == [True]
    finally:
        for key, val in originals.items():
            setattr(fullbody_pipeline, key, val)


def test_operator_registered():
    import bpy

    assert hasattr(bpy.ops.flexforge, "apply_full_body"), (
        "operator not exposed in bpy.ops.flexforge"
    )


# Head of every bone of the Mixamo fixture, spread along the body.
_MIXAMO_HEADS = {
    "mixamorig:Hips": (0.0, 0.0, 0.0),
    "mixamorig:Spine": (0.0, 0.0, 1.0),
    "mixamorig:Spine1": (0.0, 0.0, 2.0),
    "mixamorig:Spine2": (0.0, 0.0, 3.0),
    "mixamorig:LeftUpLeg": (0.0, -1.0, 0.0),
    "mixamorig:LeftLeg": (0.0, -1.0, -1.0),
    "mixamorig:LeftFoot": (0.0, -1.0, -2.0),
    "mixamorig:LeftShoulder": (0.2, 0.5, 2.5),
    "mixamorig:LeftArm": (0.2, 0.9, 2.5),
    "mixamorig:LeftForeArm": (0.2, 1.3, 2.4),
    "mixamorig:RightUpLeg": (0.0, 1.0, 0.0),
    "mixamorig:RightLeg": (0.0, 1.0, -1.0),
    "mixamorig:RightFoot": (0.0, 1.0, -2.0),
    "mixamorig:RightShoulder": (-0.2, 0.5, 2.5),
    "mixamorig:RightArm": (-0.2, 0.9, 2.5),
    "mixamorig:RightForeArm": (-0.2, 1.3, 2.4),
}


def _make_mixamo_armature(parents):
    """Create a real Mixamo rig in Object Mode."""
    import bpy

    rig_data = bpy.data.armatures.new("FlexForgeFullBodyRig")
    rig = bpy.data.objects.new("FlexForgeFullBodyRig", rig_data)
    bpy.context.scene.collection.objects.link(rig)
    for other in bpy.context.view_layer.objects:
        other.select_set(False)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="EDIT")
    for name, parent_name in parents.items():
        head = _MIXAMO_HEADS.get(name, (0.0, 0.0, 0.0))
        parent = rig_data.edit_bones.get(parent_name) if parent_name else None
        bone = rig_data.edit_bones.new(name)
        bone.parent = parent
        bone.head = head
        bone.tail = (head[0], head[1], head[2] + 1.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def _make_mixamo_rig_with_mesh(parents):
    """Create a Mixamo rig plus a skinned humanoid mesh bound via Armature."""
    import bpy

    rig = _make_mixamo_armature(parents)
    verts = []
    faces = []
    vert_bones = []
    offsets = (
        (-0.04, -0.04, -0.04), (0.04, -0.04, -0.04),
        (0.04, 0.04, -0.04), (-0.04, 0.04, -0.04),
        (-0.04, -0.04, 0.04), (0.04, -0.04, 0.04),
        (0.04, 0.04, 0.04), (-0.04, 0.04, 0.04),
    )
    box_faces = (
        (0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4),
        (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7),
    )
    for bone in rig.data.bones:
        mid = tuple((bone.head_local[i] + bone.tail_local[i]) * 0.5 for i in range(3))
        for pt in (tuple(bone.head_local), mid, tuple(bone.tail_local)):
            base = len(verts)
            for dx, dy, dz in offsets:
                verts.append((pt[0] + dx, pt[1] + dy, pt[2] + dz))
                vert_bones.append(bone.name)
            for f in box_faces:
                faces.append((base + f[0], base + f[1], base + f[2], base + f[3]))

    mesh_data = bpy.data.meshes.new("FlexForgeFullBodyMesh")
    mesh_data.from_pydata(verts, [], faces)
    mesh_data.update()
    mesh = bpy.data.objects.new("FlexForgeFullBodyMesh", mesh_data)
    bpy.context.scene.collection.objects.link(mesh)
    mod = mesh.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = rig
    for bone in rig.data.bones:
        mesh.vertex_groups.new(name=bone.name)
    for idx, bname in enumerate(vert_bones):
        mesh.vertex_groups[bname].add([idx], 1.0, "REPLACE")
    return rig, mesh


def _cleanup_rig_and_mesh(rig, mesh=None):
    import bpy

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    if mesh is not None:
        mdata = mesh.data
        bpy.data.objects.remove(mesh, do_unlink=True)
        if mdata.users == 0:
            bpy.data.meshes.remove(mdata)
    if rig is not None:
        rdata = rig.data
        bpy.data.objects.remove(rig, do_unlink=True)
        if rdata.users == 0:
            bpy.data.armatures.remove(rdata)


def test_operator_execute_missing_mesh_cancelled():
    import bpy

    if _FAKE:
        return
    parents = _mixamo_data()[1]
    rig = _make_mixamo_armature(parents)
    bpy.utils.register_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
    try:
        try:
            result = bpy.ops.flexforge.apply_full_body(mirror_lr=True)
            assert result == {"CANCELLED"}, result
        except RuntimeError as error:
            assert "No mesh bound to armature" in str(error), str(error)
        assert not [b for b in rig.data.bones if b.name.startswith("muscle_")]
    finally:
        bpy.utils.unregister_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
        _cleanup_rig_and_mesh(rig)


def test_operator_execute_end_to_end_from_armature():
    import bpy

    if _FAKE:
        return
    parents = _mixamo_data()[1]
    rig, mesh = _make_mixamo_rig_with_mesh(parents)
    bpy.context.view_layer.objects.active = rig
    bpy.utils.register_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
    try:
        result = bpy.ops.flexforge.apply_full_body(mirror_lr=True, bind_radius=0.8)
        assert result == {"FINISHED"}, result
        assert rig.mode == "OBJECT", rig.mode
        assert bpy.context.view_layer.objects.active == rig
        assert any(b.name.startswith("muscle_") for b in rig.data.bones)
        sk = mesh.data.shape_keys
        assert sk is not None and "Basis" in sk.key_blocks, sk
        assert any(kb.name.startswith("flexforge_") for kb in sk.key_blocks)
        assert not [g for g in mesh.vertex_groups if g.name.startswith("muscle_")]
        assert all(len(v.groups) <= 4 for v in mesh.data.vertices)
    finally:
        bpy.utils.unregister_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
        _cleanup_rig_and_mesh(rig, mesh)


def test_operator_execute_end_to_end_from_mesh():
    import bpy

    if _FAKE:
        return
    parents = _mixamo_data()[1]
    rig, mesh = _make_mixamo_rig_with_mesh(parents)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)
    bpy.utils.register_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
    try:
        result = bpy.ops.flexforge.apply_full_body(mirror_lr=True, bind_radius=0.8)
        assert result == {"FINISHED"}, result
        assert bpy.context.view_layer.objects.active == mesh
        assert mesh.select_get()
        assert mesh.data.shape_keys is not None
        assert any(kb.name.startswith("flexforge_") for kb in mesh.data.shape_keys.key_blocks)
    finally:
        bpy.utils.unregister_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
        _cleanup_rig_and_mesh(rig, mesh)


def test_operator_execute_restores_pose_mode():
    import bpy

    if _FAKE:
        return
    parents = _mixamo_data()[1]
    rig, mesh = _make_mixamo_rig_with_mesh(parents)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")
    assert rig.mode == "POSE", rig.mode
    bpy.utils.register_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
    try:
        result = bpy.ops.flexforge.apply_full_body(mirror_lr=True, bind_radius=0.8)
        assert result == {"FINISHED"}, result
        assert rig.mode == "POSE", rig.mode
    finally:
        bpy.utils.unregister_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
        _cleanup_rig_and_mesh(rig, mesh)


def test_single_undo_step():
    import bpy

    if _FAKE:
        return
    parents = _mixamo_data()[1]
    rig, mesh = _make_mixamo_rig_with_mesh(parents)
    bpy.context.view_layer.objects.active = rig
    bpy.utils.register_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
    try:
        bpy.ops.ed.undo_push(message="Before Full Body")
        result = bpy.ops.flexforge.apply_full_body(
            "EXEC_DEFAULT", True, mirror_lr=True, bind_radius=0.8
        )
        assert result == {"FINISHED"}, result
        assert any(b.name.startswith("muscle_") for b in rig.data.bones)
        assert mesh.data.shape_keys is not None
        assert bpy.ops.ed.undo.poll(), "Undo should be available after operator"

        undo_res = bpy.ops.ed.undo()
        assert undo_res == {"FINISHED"}, undo_res
        rig = bpy.data.objects.get("FlexForgeFullBodyRig")
        mesh = bpy.data.objects.get("FlexForgeFullBodyMesh")
        assert rig is not None and mesh is not None, "Undo removed base rig/mesh"
        assert not [b for b in rig.data.bones if b.name.startswith("muscle_")], (
            "Single undo left muscle_* bones behind"
        )
        assert not [g for g in mesh.vertex_groups if g.name.startswith("muscle_")], (
            "Single undo left muscle_* groups behind"
        )
        sk = mesh.data.shape_keys
        leftover_keys = [
            kb.name for kb in (sk.key_blocks if sk else ())
            if kb.name.startswith("flexforge_") or kb.name == "Basis"
        ]
        assert not leftover_keys, "Single undo left shape keys: %s" % leftover_keys

        assert bpy.ops.ed.redo.poll(), "Redo should be available after single undo"
        redo_res = bpy.ops.ed.redo()
        assert redo_res == {"FINISHED"}, redo_res
        rig = bpy.data.objects.get("FlexForgeFullBodyRig")
        mesh = bpy.data.objects.get("FlexForgeFullBodyMesh")
        assert any(b.name.startswith("muscle_") for b in rig.data.bones), "Redo did not restore muscle_* bones"
        assert mesh.data.shape_keys is not None and any(
            kb.name.startswith("flexforge_") for kb in mesh.data.shape_keys.key_blocks
        ), "Redo did not restore flexforge_* shape keys"
    finally:
        bpy.utils.unregister_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
        _cleanup_rig_and_mesh(
            bpy.data.objects.get("FlexForgeFullBodyRig"),
            bpy.data.objects.get("FlexForgeFullBodyMesh"),
        )


def _call_expect_cancelled(bpy, expected_substr):
    try:
        res = bpy.ops.flexforge.apply_full_body()
        assert res == {"CANCELLED"}, res
    except RuntimeError as error:
        assert expected_substr in str(error), str(error)


def test_operator_execute_negative_targets_cancelled():
    import bpy

    if _FAKE:
        return
    bpy.utils.register_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
    empty = None
    rig = None
    mesh = None
    try:
        # 1. active = None
        bpy.context.view_layer.objects.active = None
        _call_expect_cancelled(bpy, "Select an armature or a rigged mesh first")

        # 2. active = EMPTY
        empty = bpy.data.objects.new("NotARig", None)
        bpy.context.scene.collection.objects.link(empty)
        bpy.context.view_layer.objects.active = empty
        _call_expect_cancelled(bpy, "Select an armature or a rigged mesh first")

        # 3. armature with 0 matching presets
        rig, mesh = _make_mixamo_rig_with_mesh({"BoneA": "", "BoneB": "BoneA"})
        bpy.context.view_layer.objects.active = rig
        _call_expect_cancelled(bpy, "no presets available")
    finally:
        bpy.utils.unregister_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
        if empty is not None:
            bpy.data.objects.remove(empty, do_unlink=True)
        _cleanup_rig_and_mesh(rig, mesh)


def test_operator_execute_asymmetric_left_only_mirror_lr():
    import bpy

    if _FAKE:
        return
    left_parents = {
        k: v for k, v in _mixamo_data()[1].items()
        if "Right" not in k
    }
    rig, mesh = _make_mixamo_rig_with_mesh(left_parents)
    bpy.context.view_layer.objects.active = rig
    bpy.utils.register_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
    try:
        result = bpy.ops.flexforge.apply_full_body(mirror_lr=True, bind_radius=0.8)
        assert result == {"FINISHED"}, result
        muscle_bones = [b.name for b in rig.data.bones if b.name.startswith("muscle_")]
        assert muscle_bones, "Expected .L muscle bones on asymmetric rig"
        assert not any(n.endswith("_R") or "_R_" in n for n in muscle_bones), (
            "Asymmetric rig should not create _R bones: %s" % muscle_bones
        )
    finally:
        bpy.utils.unregister_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
        _cleanup_rig_and_mesh(rig, mesh)


def test_operator_execute_partial_upper_body_presets():
    import bpy

    if _FAKE:
        return
    upper_parents = {
        "mixamorig:Hips": "",
        "mixamorig:Spine": "mixamorig:Hips",
        "mixamorig:Spine1": "mixamorig:Spine",
        "mixamorig:LeftShoulder": "mixamorig:Spine1",
        "mixamorig:LeftArm": "mixamorig:LeftShoulder",
        "mixamorig:LeftForeArm": "mixamorig:LeftArm",
        "mixamorig:RightShoulder": "mixamorig:Spine1",
        "mixamorig:RightArm": "mixamorig:RightShoulder",
        "mixamorig:RightForeArm": "mixamorig:RightArm",
    }
    rig, mesh = _make_mixamo_rig_with_mesh(upper_parents)
    try:
        res = fullbody_pipeline.run_full_body_pipeline(rig, [mesh], mirror_lr=True, bind_radius=0.8)
        assert res["created"] == ["biceps", "triceps", "deltoid", "latissimus"], res["created"]
        assert res["shape_keys"] == 8, res["shape_keys"]
    finally:
        _cleanup_rig_and_mesh(rig, mesh)


def test_pipeline_multi_mesh_and_budget_warning():
    import bpy

    if _FAKE:
        return
    parents = _mixamo_data()[1]
    rig, mesh1 = _make_mixamo_rig_with_mesh(parents)
    mesh2_data = mesh1.data.copy()
    mesh2 = bpy.data.objects.new("FlexForgeSecondMesh", mesh2_data)
    bpy.context.scene.collection.objects.link(mesh2)
    mod2 = mesh2.modifiers.new(name="Armature", type="ARMATURE")
    mod2.object = rig
    try:
        res = fullbody_pipeline.run_full_body_pipeline(
            rig, [mesh1, mesh2], mirror_lr=True, bind_radius=0.8, lod=1, max_shape_keys=4
        )
        assert res["meshes"] == 2, res
        assert set(res["budgets"].keys()) == {"FlexForgeFullBodyMesh", "FlexForgeSecondMesh"}, res["budgets"]
        for m in (mesh1, mesh2):
            sk = m.data.shape_keys
            assert sk is not None and any(kb.name.startswith("flexforge_") for kb in sk.key_blocks)
            assert not [g for g in m.vertex_groups if g.name.startswith("muscle_")]
        assert res["has_warnings"] is True, res
        assert any("over budget" in w for w in res["warnings"]), res["warnings"]
        assert "warnings=" in res["message"], res["message"]
    finally:
        _cleanup_rig_and_mesh(None, mesh2)
        _cleanup_rig_and_mesh(rig, mesh1)


def test_rollback_preserves_preexisting_state():
    import bpy

    if _FAKE:
        return
    parents = _mixamo_data()[1]
    rig, mesh = _make_mixamo_rig_with_mesh(parents)
    try:
        # Pre-existing muscle_* bone, muscle_* vertex group, and flexforge_* shape key
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode="EDIT")
        pre_bone = rig.data.edit_bones.new("muscle_preexisting")
        pre_bone.head = (0.0, 0.0, 0.0)
        pre_bone.tail = (0.0, 0.0, 0.5)
        bpy.ops.object.mode_set(mode="OBJECT")
        mesh.vertex_groups.new(name="muscle_preexisting")
        mesh.shape_key_add(name="Basis", from_mix=False)
        mesh.shape_key_add(name="flexforge_preexisting", from_mix=False)

        orig_bake = fullbody_pipeline.apply_muscle_bake
        def _fail_bake(m, **kw):
            m.shape_key_add(name="flexforge_new", from_mix=False)
            raise fullbody_pipeline.BakeError("forced rollback")
        fullbody_pipeline.apply_muscle_bake = _fail_bake
        try:
            try:
                fullbody_pipeline.run_full_body_pipeline(rig, [mesh], mirror_lr=True, bind_radius=0.8)
                assert False, "Expected BakeError"
            except fullbody_pipeline.BakeError:
                pass
        finally:
            fullbody_pipeline.apply_muscle_bake = orig_bake

        bone_names = {b.name for b in rig.data.bones}
        assert bone_names == set(parents.keys()) | {"muscle_preexisting"}, bone_names
        group_names = {g.name for g in mesh.vertex_groups}
        assert group_names == set(parents.keys()) | {"muscle_preexisting"}, group_names
        key_names = {kb.name for kb in mesh.data.shape_keys.key_blocks}
        assert key_names == {"Basis", "flexforge_preexisting"}, key_names
    finally:
        _cleanup_rig_and_mesh(rig, mesh)


def test_operator_execute_restores_mesh_weight_paint_mode():
    import bpy

    if _FAKE:
        return
    parents = _mixamo_data()[1]
    rig, mesh = _make_mixamo_rig_with_mesh(parents)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)
    bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
    assert mesh.mode == "WEIGHT_PAINT", mesh.mode
    bpy.utils.register_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
    try:
        result = bpy.ops.flexforge.apply_full_body(mirror_lr=True, bind_radius=0.8)
        assert result == {"FINISHED"}, result
        assert bpy.context.view_layer.objects.active == mesh
        assert mesh.mode == "WEIGHT_PAINT", mesh.mode
    finally:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.utils.unregister_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
        _cleanup_rig_and_mesh(rig, mesh)


def test_operator_execute_restores_mesh_edit_mode():
    import bpy

    if _FAKE:
        return
    parents = _mixamo_data()[1]
    rig, mesh = _make_mixamo_rig_with_mesh(parents)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    assert mesh.mode == "EDIT", mesh.mode
    bpy.utils.register_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
    try:
        result = bpy.ops.flexforge.apply_full_body(
            "EXEC_DEFAULT", True, mirror_lr=True, bind_radius=0.8
        )
        assert result == {"FINISHED"}, result
        assert bpy.context.view_layer.objects.active == mesh
        assert mesh.mode == "EDIT", mesh.mode
        assert any(b.name.startswith("muscle_") for b in rig.data.bones)
    finally:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.utils.unregister_class(muscle_fullbody.FLEXFORGE_OT_apply_full_body)
        _cleanup_rig_and_mesh(rig, mesh)


def test_rollback_mid_edit_mode_no_leaked_bones():
    import bpy

    if _FAKE:
        return
    parents = _mixamo_data()[1]
    rig, mesh = _make_mixamo_rig_with_mesh(parents)
    orig_create = fullbody_pipeline.create_preset_muscles
    calls = [0]

    def _fail_second(arm, pid, mirror_lr=True):
        calls[0] += 1
        if calls[0] >= 2:
            raise fullbody_pipeline.MuscleError("forced mid-EDIT rollback")
        return orig_create(arm, pid, mirror_lr=mirror_lr)

    fullbody_pipeline.create_preset_muscles = _fail_second
    try:
        try:
            fullbody_pipeline.run_full_body_pipeline(
                rig, [mesh], mirror_lr=True, bind_radius=0.8
            )
            assert False, "Expected MuscleError"
        except fullbody_pipeline.MuscleError:
            pass
        assert rig.mode == "OBJECT", rig.mode
        leaked = [b.name for b in rig.data.bones if b.name.startswith("muscle_")]
        assert leaked == [], "Leaked muscle bones after mid-EDIT rollback: %s" % leaked
    finally:
        fullbody_pipeline.create_preset_muscles = orig_create
        _cleanup_rig_and_mesh(rig, mesh)


def _main():
    tests = [
        test_operator_definition,
        test_operator_properties_complete,
        test_apply_full_body_no_presets,
        test_detect_rig_mixamo_nine_presets,
        test_full_body_message_counts_created,
        test_resolve_targets_mesh_and_armature,
        test_pipeline_order_and_rollback,
        test_operator_registered,
        test_operator_execute_missing_mesh_cancelled,
        test_operator_execute_end_to_end_from_armature,
        test_operator_execute_end_to_end_from_mesh,
        test_operator_execute_restores_pose_mode,
        test_single_undo_step,
        test_operator_execute_negative_targets_cancelled,
        test_operator_execute_asymmetric_left_only_mirror_lr,
        test_operator_execute_partial_upper_body_presets,
        test_pipeline_multi_mesh_and_budget_warning,
        test_rollback_preserves_preexisting_state,
        test_operator_execute_restores_mesh_weight_paint_mode,
        test_operator_execute_restores_mesh_edit_mode,
        test_rollback_mid_edit_mode_no_leaked_bones,
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
    print("RISULTATO passati=%d falliti=%d totale=%d" % (passed, failed, passed + failed))
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(_main())