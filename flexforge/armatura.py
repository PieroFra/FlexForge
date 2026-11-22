# FlexForge — shared armature helper (verify and export).
# No bpy logic beyond the attributes read: it works on 4.2 and 5.3.


def armature_of_mesh(obj):
    """Return the Armature modifier armature (or the parent), otherwise None."""
    for modifier in getattr(obj, "modifiers", ()):
        if getattr(modifier, "type", None) != "ARMATURE":
            continue
        armature = getattr(modifier, "object", None)
        if armature is not None and getattr(armature, "type", None) == "ARMATURE":
            return armature
    parent = getattr(obj, "parent", None)
    if parent is not None and getattr(parent, "type", None) == "ARMATURE":
        return parent
    return None
