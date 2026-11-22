# FlexForge — user interface.
# Panel in the VIEW_3D Sidebar with the operator buttons.
# APIs used are present on both Blender 4.2 and 5.3.

import bpy

from .armatura import armature_of_mesh
from .muscle_bounce import find_flexforge_keys


def context_summary(context):
    """One-line description of the active object for the panel header."""
    obj = getattr(context, "active_object", None) if context is not None else None
    if obj is None:
        return "Active: none"

    name = obj.name
    kind = getattr(obj, "type", "UNKNOWN")
    if kind == "ARMATURE":
        bones = getattr(getattr(obj, "data", None), "bones", None) or []
        return "Active: %s (ARMATURE, %d bones)" % (name, len(bones))
    if kind == "MESH":
        groups = getattr(obj, "vertex_groups", None) or []
        return "Active: %s (MESH, %d groups)" % (name, len(groups))
    return "Active: %s (%s)" % (name, kind)


def muscle_status_summary(obj):
    """One-line muscle/bake status of `obj` for the panel header."""
    if obj is None or getattr(obj, "type", None) != "MESH":
        return "Muscles: select a mesh"
    groups = [
        group
        for group in getattr(obj, "vertex_groups", None) or []
        if str(getattr(group, "name", "")).startswith("muscle_")
    ]
    return "Muscles: %d groups | %d baked keys" % (
        len(groups), len(find_flexforge_keys(obj))
    )


class FLEXFORGE_PT_main(bpy.types.Panel):
    """FlexForge main panel: buttons for the registered operators."""

    bl_idname = "FLEXFORGE_PT_main"
    bl_label = "FlexForge"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "FlexForge"

    def draw(self, context):
        layout = self.layout
        obj = getattr(context, "active_object", None) if context is not None else None
        kind = getattr(obj, "type", None)
        armature = obj if kind == "ARMATURE" else None
        if armature is None and kind == "MESH":
            armature = armature_of_mesh(obj)
        settings = getattr(getattr(context, "scene", None), "flexforge_settings", None)
        layout.label(text="FlexForge - muscles and weights")

        header = layout.box()
        header.label(text=context_summary(context), icon="OBJECT_DATA")
        header.label(text=muscle_status_summary(obj), icon="BONE_DATA")

        box = layout.box()
        box.label(text="Muscle Workflow", icon="ARMATURE_DATA")
        custom = False
        if settings is not None:
            box.prop(settings, "preset")
            box.prop(settings, "mirror_lr")
            custom = getattr(settings, "preset", None) == "custom"
            if custom:
                box.prop(settings, "custom_name")
                rig_data = getattr(armature, "data", None)
                if rig_data is not None:
                    box.prop_search(settings, "origin_bone", rig_data, "bones")
                    box.prop_search(settings, "insertion_bone", rig_data, "bones")
                else:
                    box.prop(settings, "origin_bone")
                    box.prop(settings, "insertion_bone")
                box.prop(settings, "segments")
        op = box.operator(
            "flexforge.create_muscle_preset", text="Create muscle preset", icon="ADD"
        )
        if settings is not None:
            op.preset = settings.preset
            op.mirror_lr = settings.mirror_lr
            if custom:
                op.custom_name = settings.custom_name
                op.origin_bone = settings.origin_bone
                op.insertion_bone = settings.insertion_bone
                op.segments = settings.segments
        if settings is not None:
            box.prop(settings, "bind_radius")
        op_bind = box.operator(
            "flexforge.bind_muscles", text="Bind muscles", icon="MOD_SKIN"
        )
        if settings is not None:
            op_bind.radius = settings.bind_radius
        if settings is not None:
            box.prop(settings, "displacement")
            box.prop(settings, "anatomical_taper")
            box.prop(settings, "directional_bias")
            box.prop(settings, "smooth_iterations")
            box.prop(settings, "drive_by_pose")
        op_bake = box.operator(
            "flexforge.bake_shape_keys", text="Bake shape keys", icon="SHAPEKEY_DATA"
        )
        if settings is not None:
            op_bake.displacement = settings.displacement
            op_bake.anatomical_taper = settings.anatomical_taper
            op_bake.directional_bias = settings.directional_bias
            op_bake.smooth_iterations = settings.smooth_iterations
            op_bake.drive_by_pose = settings.drive_by_pose
        box.operator(
            "flexforge.bake_bounce", text="Bake skin bounce", icon="PHYSICS"
        )

        box = layout.box()
        box.label(text="Muscle Bulge Controls", icon="PREFERENCES")
        keys = []
        if obj is not None and getattr(obj, "type", None) == "MESH":
            keys = find_flexforge_keys(obj)
        if keys:
            for kb in keys:
                box.prop(kb, "value", text=kb.name[len("flexforge_"):])
        else:
            box.label(text="No baked muscles on active mesh")

        box = layout.box()
        box.label(text="Weight Paint Toolkit", icon="WPAINT_HLT")
        box.operator(
            "flexforge.weight_transfer", text="Transfer weights", icon="MOD_DATA_TRANSFER"
        )
        box.operator(
            "flexforge.cleanup_weights", text="Clean weights", icon="BRUSH_DATA"
        )
        box.operator("flexforge.mirror_weights", text="Mirror weights", icon="MOD_MIRROR")
        box.operator(
            "flexforge.limit_weights", text="Limit weights", icon="LINENUMBERS_ON"
        )

        box = layout.box()
        box.label(text="Validation & Export", icon="CHECKMARK")
        box.operator("flexforge.verify", text="Verify deformation", icon="CHECKMARK")
        box.operator("flexforge.export_gltf", text="Export glTF", icon="EXPORT")

        box = layout.box()
        box.label(text="Quick Single Muscle", icon="BONE_DATA")
        box.operator("flexforge.create_biceps", text="Create biceps (quick)", icon="PLUS")
