# Deterministic headless test of the FlexForge capsule skinning across unit
# scales. A GLB/FBX import in centimetres (object scale 0.01) holds local
# coordinates 100x the metre scale of a Blender rig: the default capsule radius
# is authored in metres and must be converted to the mesh-local unit before it
# is compared with the vertex coordinates, otherwise it binds no vertex.
# The rigs are real bpy objects, so `matrix_world` is exercised for real.

import sys
import traceback
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

from flexforge import muscle_skinning  # noqa: E402

# Helper span in metres (0.5), skin offset in metres (0.05), one far vertex.
_NEAR_OFFSET = 0.05
_FAR_OFFSET = 0.2
_NEAR_Z = (0.05, 0.15, 0.25, 0.35, 0.45)


def _build_rigged_scene(unit):
    """Mesh + one-helper armature whose local coordinates are scaled by `unit`.

    `unit == 1.0` is a metre rig; `unit == 100.0` is the same rig imported in
    centimetres: every local coordinate is 100x and both objects carry
    scale=0.01, so the world geometry is identical and the number of bound
    vertices must not depend on the local unit. The helper has no rest
    envelope, so it exercises the metre-based default radius.
    """
    scale = 1.0 / unit
    arm_data = bpy.data.armatures.new("ff_scale_arm")
    armature = bpy.data.objects.new("ff_scale_arm", arm_data)
    bpy.context.scene.collection.objects.link(armature)
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    parent = arm_data.edit_bones.new("upper_arm.L")
    parent.head = (0.0, 0.0, 0.0)
    parent.tail = (0.0, 0.0, 1.0 * unit)
    helper = arm_data.edit_bones.new("muscle_biceps_01")
    helper.head = (0.0, 0.0, 0.0)
    helper.tail = (0.0, 0.0, 0.5 * unit)
    helper.parent = parent
    helper.use_deform = True
    for bone in (parent, helper):
        bone.head_radius = 0.0
        bone.tail_radius = 0.0
    bpy.ops.object.mode_set(mode="OBJECT")
    armature.scale = (scale, scale, scale)

    coordinates = [(_NEAR_OFFSET * unit, 0.0, z * unit) for z in _NEAR_Z]
    coordinates.append((_FAR_OFFSET * unit, 0.0, 0.25 * unit))
    mesh = bpy.data.meshes.new("ff_scale_mesh")
    mesh.from_pydata(coordinates, [], [])
    obj = bpy.data.objects.new("ff_scale_mesh", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.scale = (scale, scale, scale)
    group = obj.vertex_groups.new(name="upper_arm.L")
    group.add(list(range(len(coordinates))), 1.0, "REPLACE")
    modifier = obj.modifiers.new(name="Armature", type="ARMATURE")
    modifier.object = armature
    bpy.context.view_layer.update()
    return obj, armature, mesh, arm_data


def _remove(obj, armature, mesh, arm_data):
    for datablock, collection in ((obj, bpy.data.objects),
                                  (armature, bpy.data.objects),
                                  (mesh, bpy.data.meshes),
                                  (arm_data, bpy.data.armatures)):
        if datablock is not None:
            collection.remove(datablock, do_unlink=True)


def _bound_names(obj):
    by_index = {group.index: group.name for group in obj.vertex_groups}
    return [
        vertex.index for vertex in obj.data.vertices
        if any(by_index.get(element.group) == "muscle_biceps_01"
               for element in vertex.groups)
    ]


def test_metre_rig_binds_the_skin():
    """Reference: the metre rig binds the near vertices and not the far one."""
    obj, armature, mesh, arm_data = _build_rigged_scene(1.0)
    try:
        report = muscle_skinning.apply_muscle_skinning(obj)
        assert report["vertices"] == len(_NEAR_Z) + 1, report
        assert report["vertices_bound"] == len(_NEAR_Z), report
        assert len(_bound_names(obj)) == len(_NEAR_Z), _bound_names(obj)
        assert report["muscles_bound"] == 1, report
    finally:
        _remove(obj, armature, mesh, arm_data)


def test_centimetre_rig_binds_vertices():
    """RED: a centimetre rig (scale 0.01) must bind, not report 0 vertices."""
    obj, armature, mesh, arm_data = _build_rigged_scene(100.0)
    try:
        report = muscle_skinning.apply_muscle_skinning(obj)
        assert report["vertices_bound"] > 0, report
        assert report["vertices_bound"] == len(_NEAR_Z), report
        assert report["muscles_bound"] == 1, report
    finally:
        _remove(obj, armature, mesh, arm_data)


def test_binding_is_scale_invariant():
    """The same world geometry binds the same vertices in metres and cm."""
    obj_m, arm_m, mesh_m, data_m = _build_rigged_scene(1.0)
    obj_c, arm_c, mesh_c, data_c = _build_rigged_scene(100.0)
    try:
        metre = muscle_skinning.apply_muscle_skinning(obj_m)
        centimetre = muscle_skinning.apply_muscle_skinning(obj_c)
        assert metre["vertices_bound"] > 0, metre
        assert centimetre["vertices_bound"] == metre["vertices_bound"], (
            centimetre, metre)
        assert centimetre["muscles_bound"] == metre["muscles_bound"], (
            centimetre, metre)
    finally:
        _remove(obj_m, arm_m, mesh_m, data_m)
        _remove(obj_c, arm_c, mesh_c, data_c)


def _main():
    tests = [
        test_metre_rig_binds_the_skin,
        test_centimetre_rig_binds_vertices,
        test_binding_is_scale_invariant,
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
