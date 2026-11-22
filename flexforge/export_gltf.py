# FlexForge — binary glTF (.glb) export of the active skinned mesh.
# Context validation (active mesh, armature, path) plus the call to the stock
# Blender 4.2+ exporter (`bpy.ops.export_scene.gltf`) with stock parameters:
# no FBX export, no invented constraint. The deforming helper bones live in the
# armature and stay exported with it.
# Engine budget: maximum 4 influences per vertex (reused from weights.py).

import os

import bpy

from .armatura import armature_of_mesh
from .export_selezione import (
    restore_selection,
    save_selection,
    select_for_export,
    view_layer_objects,
)
from .weights import MAX_INFLUENCES_DEFAULT, MAX_INFLUENCES_MIN, apply_limit

GLTF_EXTENSION = ".glb"


class ExportError(Exception):
    """glTF export domain error, with an English message."""


def _validate_path(path):
    """Check that `path` is an unambiguous `.glb` file name."""
    if not isinstance(path, str) or not path.strip():
        raise ExportError("Missing export path: specify a .glb file.")
    if not path.lower().endswith(GLTF_EXTENSION):
        raise ExportError(
            "Invalid path: a file with the '%s' extension is required."
            % GLTF_EXTENSION
        )
    root, extension = os.path.splitext(os.path.basename(path))
    if extension.lower() != GLTF_EXTENSION or not root.strip():
        raise ExportError(
            "Invalid path: missing file name before '%s'."
            % GLTF_EXTENSION
        )
    return path


def _active_mesh(context):
    """Return the active mesh or raise `ExportError`."""
    view_layer = getattr(context, "view_layer", None)
    objects = getattr(view_layer, "objects", None)
    active = getattr(objects, "active", None)
    if active is None or getattr(active, "type", None) != "MESH":
        raise ExportError(
            "An active mesh is required: select the object and try again."
        )
    return active


# Legacy alias: delegates to the shared helper in armatura.py.
def _armature_of_mesh(obj):
    return armature_of_mesh(obj)


def _selected_armature(context):
    """Return the first selected armature, otherwise None."""
    for obj in getattr(context, "selected_objects", ()):
        if getattr(obj, "type", None) == "ARMATURE":
            return obj
    return None


def _export_armature(context, mesh):
    """Armature of the mesh (modifier/parent) or the selected armature."""
    armature = _armature_of_mesh(mesh) or _selected_armature(context)
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        raise ExportError(
            "An armature is required: add an Armature modifier to the mesh."
        )
    if not getattr(getattr(armature, "data", None), "bones", None):
        raise ExportError(
            "The armature '%s' has no bones to export." % armature.name
        )
    return armature


def _objects_to_export(context, mesh, armature):
    """Mesh, armature and helper objects deformed by the same armature."""
    to_export = [mesh, armature]
    for obj in view_layer_objects(context):
        if obj is mesh or obj is armature:
            continue
        if getattr(obj, "parent", None) is armature:
            to_export.append(obj)
            continue
        for modifier in getattr(obj, "modifiers", ()):
            if (
                getattr(modifier, "type", None) == "ARMATURE"
                and getattr(modifier, "object", None) is armature
            ):
                to_export.append(obj)
                break
    return to_export


def _valid_max_influences(max_influences):
    """Return a valid influence budget, otherwise the default."""
    if not isinstance(max_influences, int) or isinstance(max_influences, bool):
        return MAX_INFLUENCES_DEFAULT
    if max_influences < MAX_INFLUENCES_MIN:
        return MAX_INFLUENCES_DEFAULT
    return max_influences


def export_glb(context, path, max_influences=MAX_INFLUENCES_DEFAULT):
    """Export the active mesh with its armature to `.glb`.

    Checks: active mesh, armature (from modifier/parent or selected) and `.glb`
    path. Applies the `max_influences` budget to the mesh, selects mesh,
    armature and deforming helpers before the export, then returns
    {file, bones, meshes} counting the real bones and the exported meshes.
    Raise `ExportError` on the checks.
    """
    path = _validate_path(path)
    mesh = _active_mesh(context)
    armature = _export_armature(context, mesh)
    max_influences = _valid_max_influences(max_influences)

    apply_limit(mesh, max_influences)
    to_export = _objects_to_export(context, mesh, armature)
    exporter = getattr(getattr(bpy.ops, "export_scene", None), "gltf", None)
    if not callable(exporter):
        raise ExportError(
            "glTF exporter not available in this Blender build."
        )
    previous = save_selection(context)
    try:
        select_for_export(context, to_export)
        try:
            exporter(
                filepath=path,
                export_format="GLB",
                use_selection=True,
                export_skins=True,
            )
        except ExportError:
            raise
        except Exception as error:
            raise ExportError(
                "glTF export failed: %s" % error
            ) from error
    finally:
        restore_selection(context, previous, to_export)

    return {
        "file": path,
        "bones": len(armature.data.bones),
        "meshes": sum(
            1
            for obj in to_export
            if getattr(obj, "type", None) == "MESH"
        ),
    }


def export_message(result, max_influences=MAX_INFLUENCES_DEFAULT):
    """glTF export summary line, in English and unambiguous."""
    return (
        "FlexForge - glTF: file=%s bones=%d meshes=%d max_influences=%d"
        % (
            result["file"],
            result["bones"],
            result["meshes"],
            max_influences,
        )
    )


class FLEXFORGE_OT_export_gltf(bpy.types.Operator):
    """Export the active skinned mesh to binary glTF (.glb)."""

    bl_idname = "flexforge.export_gltf"
    bl_label = "Export glTF"
    bl_description = (
        "Export the active mesh to .glb with its armature and deforming helper "
        "bones, using Blender's stock exporter"
    )
    bl_options = {"REGISTER", "UNDO"}

    path: bpy.props.StringProperty(
        name="Path",
        subtype="FILE_PATH",
        default="//flexforge_export.glb",
    )
    max_influences: bpy.props.IntProperty(
        name="Max influences",
        default=MAX_INFLUENCES_DEFAULT,
        min=MAX_INFLUENCES_MIN,
        max=8,
    )

    def execute(self, context):
        max_influences = _valid_max_influences(getattr(self, "max_influences", None))

        try:
            result = export_glb(
                context, getattr(self, "path", ""), max_influences
            )
        except ExportError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        message = export_message(result, max_influences)
        print(message)
        self.report({"INFO"}, message)
        return {"FINISHED"}
