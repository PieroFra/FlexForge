# FlexForge - damped spring secondary motion baked into the `flexforge_*`
# shape keys. The spring math is pure Python, so it runs without Blender; the
# bake pass samples each key over the scene range and re-inserts keyframes.
# APIs used are present on Blender 4.2 and 5.2.

import bpy

DEFAULT_STIFFNESS = 0.35
DEFAULT_DAMPING = 0.28
DEFAULT_OVERSHOOT = 1.35
SHAPE_KEY_PREFIX = "flexforge_"
SUBSTEPS = 2

def compute_spring_curve(values, stiffness=DEFAULT_STIFFNESS,
                         damping=DEFAULT_DAMPING, substeps=SUBSTEPS,
                         clamp_min=0.0, clamp_max=DEFAULT_OVERSHOOT):
    """Integrate a damped spring that follows `values` frame by frame.

    Each frame is `substeps` Euler steps of `acc = stiffness * (target - pos)
    - damping * vel`; the position starts on `values[0]` with zero velocity and
    is clamped in `[clamp_min, clamp_max]` after every frame. Return a list of
    floats with the same length as `values`.
    """
    samples = [float(value) for value in values]
    if not samples:
        return []
    steps = max(1, int(substeps))
    dt = 1.0 / steps
    pos = samples[0]
    vel = 0.0
    curve = []
    for target in samples:
        for _ in range(steps):
            acc = stiffness * (target - pos) - damping * vel
            vel += acc * dt
            pos += vel * dt
        pos = min(max(pos, clamp_min), clamp_max)
        curve.append(pos)
    return curve

def find_flexforge_keys(obj, prefix=SHAPE_KEY_PREFIX):
    """Return the shape keys whose name starts with `prefix`, or []."""
    shape_keys = getattr(getattr(obj, "data", None), "shape_keys", None)
    if shape_keys is None:
        return []
    return [key for key in getattr(shape_keys, "key_blocks", [])
            if str(getattr(key, "name", "")).startswith(prefix)]

def apply_muscle_bounce(obj, scene, stiffness=DEFAULT_STIFFNESS,
                        damping=DEFAULT_DAMPING,
                        overshoot_limit=DEFAULT_OVERSHOOT):
    """Bake the spring curve of every `flexforge_*` key over the scene range.

    The current value of each key is sampled on every frame from
    `scene.frame_start` to `scene.frame_end`, the spring curve replaces it with
    `keyframe_insert("value", frame=f)`, and the initial frame is always
    restored. An existing driver on the key is removed first, otherwise it
    would override the baked keyframes.
    Return {"keys": n_keys, "frames": n_frames, "drivers_removed": n_drivers}.
    """
    keys = find_flexforge_keys(obj)
    start = int(scene.frame_start)
    end = int(scene.frame_end)
    frames = list(range(start, end + 1))
    report = {"keys": len(keys), "frames": len(frames), "drivers_removed": 0}
    if not keys or not frames:
        return report
    initial = scene.frame_current
    try:
        for key in keys:
            if hasattr(key, "slider_max") and key.slider_max < overshoot_limit:
                key.slider_max = overshoot_limit
            try:
                if key.driver_remove("value"):
                    report["drivers_removed"] += 1
            except Exception:
                pass
            samples = []
            for frame in frames:
                scene.frame_set(frame)
                samples.append(float(key.value))
            curve = compute_spring_curve(samples, stiffness, damping, SUBSTEPS,
                                         0.0, overshoot_limit)
            for frame, value in zip(frames, curve):
                scene.frame_set(frame)
                key.value = value
                key.keyframe_insert("value", frame=frame)
    finally:
        scene.frame_set(initial)
    return report

def bounce_message(report):
    """Bounce summary line, in English and unambiguous."""
    return "FlexForge - bounce: keys=%d frames=%d" % (report["keys"],
                                                      report["frames"])

class FLEXFORGE_OT_bake_bounce(bpy.types.Operator):
    """Bake damped spring secondary motion into the flexforge_* shape keys."""

    bl_idname = "flexforge.bake_bounce"
    bl_label = "Bake skin bounce"
    bl_description = ("Sample the flexforge_* shape keys over the scene range and re-bake them as a damped spring curve")
    bl_options = {"REGISTER", "UNDO"}

    stiffness: bpy.props.FloatProperty(name="Stiffness", default=DEFAULT_STIFFNESS, min=0.0, max=10.0)
    damping: bpy.props.FloatProperty(name="Damping", default=DEFAULT_DAMPING, min=0.0, max=10.0)
    overshoot_limit: bpy.props.FloatProperty(name="Overshoot limit", default=DEFAULT_OVERSHOOT, min=1.0, max=5.0)

    def execute(self, context):
        obj = context.view_layer.objects.active
        if obj is None or obj.type != "MESH":
            self.report({"ERROR"}, "An active mesh is required: select the object and try again.")
            return {"CANCELLED"}
        stiffness = getattr(self, "stiffness", DEFAULT_STIFFNESS)
        if not isinstance(stiffness, (int, float)) or stiffness < 0.0:
            stiffness = DEFAULT_STIFFNESS
        damping = getattr(self, "damping", DEFAULT_DAMPING)
        if not isinstance(damping, (int, float)) or damping < 0.0:
            damping = DEFAULT_DAMPING
        overshoot = getattr(self, "overshoot_limit", DEFAULT_OVERSHOOT)
        if (not isinstance(overshoot, (int, float))
                or overshoot <= 0.0):
            overshoot = DEFAULT_OVERSHOOT
        report = apply_muscle_bounce(obj, context.scene, stiffness, damping,
                                     overshoot)
        if report["keys"] == 0:
            self.report({"WARNING"}, "No flexforge_* shape keys found on the active mesh.")
            return {"CANCELLED"}
        message = bounce_message(report)
        print(message)
        self.report({"INFO"}, message)
        return {"FINISHED"}
