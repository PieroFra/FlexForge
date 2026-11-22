# FlexForge — vertex group names and shared L/R mapping.
# Used by weight_transfer and weights_mirror: no bpy logic here.

# Side suffix pairs recognized by the mapping with inversion.
LATERAL_SUFFIXES = ((".L", ".R"), ("_L", "_R"), (".l", ".r"), ("_l", "_r"))

# Infix side tokens (Rigify, Mixamo, Unity, VRM) recognized by inversion.
LATERAL_INFIXES = (("Left", "Right"), ("left", "right"),
                   ("_L_", "_R_"), ("_l_", "_r_"), (" L ", " R "))


def invert_group_name(name):
    """Invert the side of a vertex group name (`arm.L` -> `arm.R`).

    Both lateral suffixes and infix tokens are recognized; names without a
    known lateral token are returned unchanged.
    """
    for left, right in LATERAL_SUFFIXES:
        if name.endswith(left):
            return name[: -len(left)] + right
        if name.endswith(right):
            return name[: -len(right)] + left
    for left, right in LATERAL_INFIXES:
        if left in name:
            return name.replace(left, right, 1)
        if right in name:
            return name.replace(right, left, 1)
    return name


# Aliases of the standard bones, as authored by common rig conventions.
_ALIASES_L = {
    "upper_arm.L": ("DEF-upper_arm.L", "arm_stretch.l", "mixamorig:LeftArm",
                    "upperarm_l", "LeftUpperArm", "J_Bip_L_UpperArm",
                    "Bip01 L UpperArm"),
    "forearm.L": ("DEF-forearm.L", "forearm_stretch.l",
                  "mixamorig:LeftForeArm", "lowerarm_l", "LeftLowerArm",
                  "J_Bip_L_LowerArm", "Bip01 L Forearm"),
    "shoulder.L": ("DEF-shoulder.L", "mixamorig:LeftShoulder", "clavicle_l",
                   "LeftShoulder", "J_Bip_L_Shoulder", "Bip01 L Clavicle"),
    "thigh.L": ("DEF-thigh.L", "DEF_Leg.B.L", "DEF_Leg.L", "DEF_Hip.L",
                "mixamorig:LeftUpLeg", "thigh_l", "LeftUpLeg",
                "J_Bip_L_UpperLeg", "Bip01 L Thigh"),
    "shin.L": ("DEF-shin.L", "DEF_ForeLeg.B.L", "DEF_Leg.L", "mixamorig:LeftLeg",
               "calf_l", "LeftLeg", "J_Bip_L_LowerLeg", "Bip01 L Calf"),
    "foot.L": ("DEF-foot.L", "DEF_Foot.L", "mixamorig:LeftFoot", "foot_l",
               "LeftFoot", "J_Bip_L_Foot", "Bip01 L Foot"),
    "spine": ("DEF_Spine.01", "DEF_Pelvis", "mixamorig:Spine", "spine_01",
              "J_Bip_C_Spine", "root", "Bip01 Spine", "Bip01 Pelvis"),
    "spine.001": ("DEF_Spine.02", "mixamorig:Spine1", "spine_02",
                  "J_Bip_C_Chest", "Bip01 Spine1"),
    "spine.002": ("DEF_Spine.03", "mixamorig:Spine2", "spine_03",
                  "J_Bip_C_UpperChest", "Bip01 Spine2"),
}

# Canonical names plus their R counterparts, each with its own alias list.
BONE_ALIASES = {}
for _canonical, _aliases in _ALIASES_L.items():
    BONE_ALIASES[_canonical] = tuple(_aliases)
    _mirrored = invert_group_name(_canonical)
    if _mirrored != _canonical:
        BONE_ALIASES[_mirrored] = tuple(invert_group_name(a) for a in _aliases)


def strip_namespace(name):
    """Drop a `namespace:` prefix (`mixamorig:LeftArm` -> `LeftArm`)."""
    name = str(name)
    return name.rsplit(":", 1)[-1]


def resolve_bone_name(bone_name, available):
    """Return the bone of `available` that stands for `bone_name`.

    A name already present is returned unchanged; otherwise the first alias
    of the canonical bone found in `available` is used, else the original.
    Aliases are also matched without their `namespace:` prefix, so unprefixed
    names (Quaternius `LeftArm`) and any prefixed form (`mixamorig1:LeftArm`)
    both resolve.
    """
    name = str(bone_name)
    names = {str(n) for n in available}
    if name in names:
        return name
    by_bare = {}
    for candidate in sorted(names):
        by_bare.setdefault(strip_namespace(candidate), candidate)
    for alias in BONE_ALIASES.get(name, ()):
        alias = str(alias)
        if alias in names:
            return alias
        bare = strip_namespace(alias)
        if bare in by_bare:
            return by_bare[bare]
    return name


def map_groups(reference_names, target_names, invert_lr=False):
    """Map groups by name keeping only the existing targets.

    Return {reference_name: target_name}; with `invert_lr` the target name is
    the reference name with the side inverted. Groups without a match on the
    target mesh stay out of the map.
    """
    available = {str(name) for name in target_names}
    mapping = {}
    for name in reference_names:
        name = str(name)
        target = invert_group_name(name) if invert_lr else name
        if target in available:
            mapping[name] = target
    return mapping
