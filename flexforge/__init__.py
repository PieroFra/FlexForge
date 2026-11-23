# FlexForge — installable bootstrap.
# The package exposes `bl_info` for legacy installation (Blender 4.2+) and
# stays installable as an Extension thanks to the `blender_manifest.toml` manifest.

bl_info = {
    "name": "FlexForge",
    "author": "FlexForge",
    "version": (1, 2, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > FlexForge",
    "description": "Muscles with helper bones, weights toolkit (transfer, cleanup, mirror) and glTF export for Godot and Unity.",
    "category": "Rigging",
}

# Relative imports: ui defines the panel, muscle the muscle operator,
# weights the utilities and the influence limit operator, verify the
# deformation verification operator, export_gltf the .glb export operator,
# weight_transfer the weight transfer operator between meshes,
# weights_cleanup the weight cleanup operator, weights_mirror the weight
# mirror operator between sides, muscle_presets the muscle preset operator,
# muscle_skinning the muscle binding operator, muscle_bake the shape key
# bake operator, muscle_bounce the skin bounce bake operator and muscle_clear
# the cleanup operator of the muscle data, engine_budget the engine budget
# operator.
# settings holds the Scene PropertyGroup with the addon options,
# i18n holds the it_IT translation catalogue (no class registered).
from . import (
    engine_budget,
    export_gltf,
    i18n,
    muscle,
    muscle_bake,
    muscle_bounce,
    muscle_clear,
    muscle_presets,
    muscle_skinning,
    settings,
    ui,
    verify,
    weight_transfer,
    weights,
    weights_cleanup,
    weights_mirror,
)

# Single source of truth for the addon class list.
_CLASSES = (
    ui.FLEXFORGE_PT_main,
    muscle.FLEXFORGE_OT_create_biceps,
    weights.FLEXFORGE_OT_limit_weights,
    verify.FLEXFORGE_OT_verify,
    export_gltf.FLEXFORGE_OT_export_gltf,
    weight_transfer.FLEXFORGE_OT_weight_transfer,
    weights_cleanup.FLEXFORGE_OT_cleanup_weights,
    weights_mirror.FLEXFORGE_OT_mirror_weights,
    muscle_presets.FLEXFORGE_OT_create_muscle_preset,
    muscle_skinning.FLEXFORGE_OT_bind_muscles,
    muscle_bake.FLEXFORGE_OT_bake_shape_keys,
    muscle_bounce.FLEXFORGE_OT_bake_bounce,
    muscle_clear.FLEXFORGE_OT_clear_muscles,
    engine_budget.FLEXFORGE_OT_apply_budget,
)


def register():
    """Register all addon classes, in the declared order."""
    import bpy
    settings.register_settings()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    i18n.register_translations()


def unregister():
    """Unregister in reverse order."""
    import bpy
    i18n.unregister_translations()
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
    settings.unregister_settings()
