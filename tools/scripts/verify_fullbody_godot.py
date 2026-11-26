# Headless Blender -> Godot 4.7.2 E2E verification for Phase 1.6 full-body.
# Builds synthetic Mixamo-like (Xbot) and ARP-like (SpaceDwarf) rigs + meshes,
# runs flexforge.apply_full_body, exports .glb, and runs godot_import_check.gd.
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import flexforge  # noqa: E402
from flexforge.export_gltf import export_glb  # noqa: E402
from flexforge.rig_detect import detect_rig  # noqa: E402

GODOT_SCRIPT = str(ROOT / "tools" / "scripts" / "godot_import_check.gd")
SCRATCH_DIR = Path(
    os.environ.get("FLEXFORGE_SCRATCH_DIR")
    or str(Path(tempfile.gettempdir()) / "flexforge_verify_fullbody_godot")
)


def _resolve_godot_bin():
    env_bin = os.environ.get("GODOT_BIN")
    if env_bin:
        return env_bin
    which_bin = shutil.which("godot")
    if which_bin:
        return which_bin
    home_candidate = Path.home() / "godot" / "Godot_v4.7.2-stable_linux.x86_64"
    if home_candidate.is_file():
        return str(home_candidate)
    raise FileNotFoundError(
        "Godot binary not found: set GODOT_BIN, add 'godot' to PATH, "
        "or place Godot_v4.7.2-stable_linux.x86_64 under Path.home() / 'godot'"
    )

MIXAMO_SPEC = {
    "name": "MixamoXbotLike",
    "parents": {
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
    },
    "heads": {
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
    },
}

ARP_SPEC = {
    "name": "ARPSpaceDwarfLike",
    "parents": {
        "DEF_Pelvis": "",
        "DEF_Spine": "DEF_Pelvis",
        "DEF_Spine.1": "DEF_Spine",
        "DEF_Spine.2": "DEF_Spine.1",
        "DEF_Chest": "DEF_Spine.2",
        "DEF_Shoulder.L": "DEF_Spine.2",
        "DEF_Shoulder.R": "DEF_Spine.2",
        "DEF_UpperArm.L": "DEF_Shoulder.L",
        "DEF_UpperArm.R": "DEF_Shoulder.R",
        "DEF_ForeArm.L": "DEF_UpperArm.L",
        "DEF_ForeArm.R": "DEF_UpperArm.R",
        "DEF_Leg.L": "DEF_Pelvis",
        "DEF_Leg.R": "DEF_Pelvis",
        "DEF_ForeLeg.L": "DEF_Leg.L",
        "DEF_ForeLeg.R": "DEF_Leg.R",
        "DEF_Foot.L": "DEF_ForeLeg.L",
        "DEF_Foot.R": "DEF_ForeLeg.R",
    },
    "heads": {
        "DEF_Pelvis": (0.0, 0.0, 0.0),
        "DEF_Spine": (0.0, 0.0, 1.0),
        "DEF_Spine.1": (0.0, 0.0, 2.0),
        "DEF_Spine.2": (0.0, 0.0, 3.0),
        "DEF_Chest": (0.0, 0.0, 3.5),
        "DEF_Leg.L": (0.0, -1.0, 0.0),
        "DEF_ForeLeg.L": (0.0, -1.0, -1.0),
        "DEF_Foot.L": (0.0, -1.0, -2.0),
        "DEF_Shoulder.L": (0.2, 0.5, 2.5),
        "DEF_UpperArm.L": (0.2, 0.9, 2.5),
        "DEF_ForeArm.L": (0.2, 1.3, 2.4),
        "DEF_Leg.R": (0.0, 1.0, 0.0),
        "DEF_ForeLeg.R": (0.0, 1.0, -1.0),
        "DEF_Foot.R": (0.0, 1.0, -2.0),
        "DEF_Shoulder.R": (-0.2, 0.5, 2.5),
        "DEF_UpperArm.R": (-0.2, 0.9, 2.5),
        "DEF_ForeArm.R": (-0.2, 1.3, 2.4),
    },
}


def _build_rig_and_mesh(spec):
    rig_data = bpy.data.armatures.new(spec["name"] + "Arm")
    rig = bpy.data.objects.new(spec["name"] + "Arm", rig_data)
    bpy.context.scene.collection.objects.link(rig)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, parent_name in spec["parents"].items():
        head = spec["heads"][name]
        eb = rig_data.edit_bones.new(name)
        eb.parent = rig_data.edit_bones.get(parent_name) if parent_name else None
        eb.head = head
        eb.tail = (head[0], head[1], head[2] + 0.8)
    bpy.ops.object.mode_set(mode="OBJECT")

    verts, faces, vert_bones = [], [], []
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

    mdata = bpy.data.meshes.new(spec["name"] + "Mesh")
    mdata.from_pydata(verts, [], faces)
    mdata.update()
    mesh = bpy.data.objects.new(spec["name"] + "Mesh", mdata)
    bpy.context.scene.collection.objects.link(mesh)
    mesh.parent = rig
    mesh.modifiers.new(name="Armature", type="ARMATURE").object = rig
    for bone in rig.data.bones:
        mesh.vertex_groups.new(name=bone.name)
    for idx, bname in enumerate(vert_bones):
        mesh.vertex_groups[bname].add([idx], 1.0, "REPLACE")
    return rig, mesh


def _verify_spec(spec, godot_bin):
    rig, mesh = _build_rig_and_mesh(spec)
    try:
        report = detect_rig([b.name for b in rig.data.bones], spec["parents"])
        assert len(report["preset_ids"]) == 9, report
        assert report["topology_ok"] is True, report

        bpy.context.view_layer.objects.active = rig
        res = bpy.ops.flexforge.apply_full_body(mirror_lr=True, bind_radius=0.8)
        assert res == {"FINISHED"}, res

        sk = mesh.data.shape_keys
        ff_keys = [kb.name for kb in sk.key_blocks if kb.name.startswith("flexforge_") and kb.name != "flexforge_Basis"]
        assert len(ff_keys) >= 9, ff_keys
        assert all(len(v.groups) <= 4 for v in mesh.data.vertices)

        bpy.context.view_layer.objects.active = mesh
        mesh.select_set(True)
        glb_path = str(SCRATCH_DIR / (spec["name"] + ".glb"))
        exp = export_glb(bpy.context, glb_path, max_influences=4)
        assert os.path.isfile(exp["file"]), exp

        proc = subprocess.run(
            [godot_bin, "--headless", "--script", GODOT_SCRIPT, "--", glb_path],
            capture_output=True,
            text=True,
            check=False,
        )
        print(proc.stdout.strip())
        if proc.returncode != 0 or "ENGINE_CHECK_OK | engine=godot |" not in proc.stdout:
            raise RuntimeError(
                "Godot check failed (exit %d): %s\n%s" % (proc.returncode, proc.stdout, proc.stderr)
            )
    finally:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        mdata, rdata = mesh.data, rig.data
        bpy.data.objects.remove(mesh, do_unlink=True)
        bpy.data.objects.remove(rig, do_unlink=True)
        if mdata.users == 0:
            bpy.data.meshes.remove(mdata)
        if rdata.users == 0:
            bpy.data.armatures.remove(rdata)


def main():
    godot_bin = _resolve_godot_bin()
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    flexforge.register()
    try:
        _verify_spec(MIXAMO_SPEC, godot_bin)
        _verify_spec(ARP_SPEC, godot_bin)
    finally:
        flexforge.unregister()
        shutil.rmtree(SCRATCH_DIR, ignore_errors=True)
    print("FULLBODY_GODOT_E2E_OK | rigs=2/2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
