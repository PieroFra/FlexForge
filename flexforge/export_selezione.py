# FlexForge — selection handling during glTF export.
# Saves the context selection, applies the export one and always restores it
# (even if the exporter fails): no spurious mutation is left behind.

import bpy  # noqa: F401 (imported for consistency with the other modules)


def view_layer_objects(context):
    """Return the list of view layer objects, empty if missing."""
    objects = getattr(getattr(context, "view_layer", None), "objects", None)
    try:
        return list(objects)
    except TypeError:
        return []


def save_selection(context):
    """Copy the current selection of `context.selected_objects`."""
    try:
        return list(getattr(context, "selected_objects", ()))
    except TypeError:
        return []


def restore_selection(context, previous, to_deselect=()):
    """Restore the previous selection without ever propagating errors."""
    try:
        expected = set(id(obj) for obj in previous)
        seen = set()
        for obj in (
            view_layer_objects(context)
            + list(to_deselect)
            + list(previous)
        ):
            if id(obj) in seen:
                continue
            seen.add(id(obj))
            select = getattr(obj, "select_set", None)
            if callable(select):
                select(id(obj) in expected)
        selected = getattr(context, "selected_objects", None)
        if selected is not None:
            try:
                selected.clear()
                selected.extend(previous)
            except (AttributeError, TypeError):
                pass
    except Exception:
        pass


def select_for_export(context, objects):
    """Select only `objects` and deselect everything else in the view layer."""
    expected = set(id(obj) for obj in objects)
    for obj in view_layer_objects(context):
        select = getattr(obj, "select_set", None)
        if callable(select):
            select(id(obj) in expected)
    for obj in objects:
        select = getattr(obj, "select_set", None)
        if callable(select):
            select(True)
    selected = getattr(context, "selected_objects", None)
    if selected is not None:
        try:
            selected.clear()
            selected.extend(objects)
        except (AttributeError, TypeError):
            pass
