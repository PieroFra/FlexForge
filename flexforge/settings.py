# FlexForge — addon settings exposed in the Sidebar.
# The PropertyGroup holds the values shared by the operators: preset choice,
# custom origin/insertion bones and the bake/anatomy options.

import bpy

PRESET_ITEMS = (
    ("all_available", "All available", ""),
    ("biceps", "Biceps", ""),
    ("triceps", "Triceps", ""),
    ("deltoid", "Deltoid", ""),
    ("pectoral", "Pectoral", ""),
    ("latissimus", "Latissimus", ""),
    ("quadriceps", "Quadriceps", ""),
    ("hamstring", "Hamstring", ""),
    ("calf", "Calf", ""),
    ("gluteus", "Gluteus", ""),
    ("custom", "Custom", ""),
)


class FlexForgeSettings(bpy.types.PropertyGroup):
    """Shared addon settings, attached to the Scene as `flexforge_settings`."""

    preset: bpy.props.EnumProperty(
        name="Preset", description="Muscle preset used by the operators",
        items=PRESET_ITEMS, default="all_available")
    mirror_lr: bpy.props.BoolProperty(
        name="Mirror L/R", description="Create the mirrored counterpart", default=True)
    custom_name: bpy.props.StringProperty(
        name="Custom name", description="Name used by the custom preset", default="custom")
    origin_bone: bpy.props.StringProperty(
        name="Origin bone", description="Origin bone for the custom muscle", default="")
    insertion_bone: bpy.props.StringProperty(
        name="Insertion bone", description="Insertion bone for the custom muscle", default="")
    segments: bpy.props.IntProperty(
        name="Segments", description="Number of muscle segments", default=2, min=1, max=8)
    displacement: bpy.props.FloatProperty(
        name="Displacement", description="Muscle displacement along the bone axis",
        default=0.05, min=0.001, max=1.0)
    anatomical_taper: bpy.props.BoolProperty(
        name="Anatomical taper", description="Taper the muscle at both ends", default=True)
    directional_bias: bpy.props.BoolProperty(
        name="Directional bias", description="Bias the bulge on the front or back side",
        default=True)
    smooth_iterations: bpy.props.IntProperty(
        name="Smooth", description="Laplacian smoothing iterations", default=2, min=0, max=5)
    drive_by_pose: bpy.props.BoolProperty(
        name="Drive by pose", description="Drive contraction from the pose", default=False)
    bind_radius: bpy.props.FloatProperty(
        name="Bind radius", description="Capsule radius for Bind muscles",
        default=0.15, min=0.01, max=1.0)


def register_settings():
    """Register the PropertyGroup and attach it to the Scene."""
    bpy.utils.register_class(FlexForgeSettings)
    bpy.types.Scene.flexforge_settings = bpy.props.PointerProperty(type=FlexForgeSettings)


def unregister_settings():
    """Detach the Scene property and unregister the PropertyGroup."""
    del bpy.types.Scene.flexforge_settings
    bpy.utils.unregister_class(FlexForgeSettings)
