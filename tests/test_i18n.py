# Headless test of the Italian translation catalogue in flexforge/i18n.py.
import re
import sys
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def _install_stub():
    try:
        import bpy  # noqa: F401
        return False
    except ImportError:
        pass
    folder = "/home/pierofra/.cache/opencode/tmp"
    if folder not in sys.path:
        sys.path.insert(0, folder)
    from flexforge_stub import installa_stub_bpy as install_bpy_stub

    return install_bpy_stub(props_default=True, con_ops=True)


_install_stub()

from flexforge import i18n  # noqa: E402

# Strings built inside ui.py functions, not passed through text="".
_UI_SUMMARY_STRINGS = (
    "Muscles: select a mesh",
    "Muscles: %d groups | %d baked keys",
)


def test_translations_dict_has_it_IT_entries():
    assert "it_IT" in i18n.TRANSLATIONS
    entries = i18n.TRANSLATIONS["it_IT"]
    assert isinstance(entries, dict)
    assert len(entries) >= 30
    for key, value in entries.items():
        assert isinstance(key, tuple) and len(key) == 2
        assert key[0] in ("*", "Operator")
        assert isinstance(key[1], str) and key[1]
        assert isinstance(value, str) and value
    assert ("*", "Muscle Workflow") in entries
    assert ("Operator", "Bind muscles") in entries
    assert ("*", "Max influences") in entries


def test_ui_labels_are_translated():
    source = (BASE / "flexforge" / "ui.py").read_text(encoding="utf-8")
    entries = i18n.TRANSLATIONS["it_IT"]
    labels = set(re.findall(r'text="([^"]+)"', source))
    labels.update(_UI_SUMMARY_STRINGS)
    assert len(labels) >= 18
    missing = sorted(text for text in labels if ("*", text) not in entries)
    assert missing == []


def test_register_and_unregister_translations_in_blender():
    import bpy

    entries = i18n.TRANSLATIONS["it_IT"]
    view = bpy.context.preferences.view
    previous = view.language
    view.language = "it_IT"
    try:
        i18n.register_translations()
        i18n.register_translations()
        assert (
            bpy.app.translations.pgettext_iface("Muscle Workflow")
            == entries[("*", "Muscle Workflow")]
        )
        assert (
            bpy.app.translations.pgettext("Bind muscles", "Operator")
            == entries[("Operator", "Bind muscles")]
        )
        assert (
            bpy.app.translations.pgettext_iface("Max influences")
            == entries[("*", "Max influences")]
        )
        i18n.unregister_translations()
        i18n.unregister_translations()
        assert bpy.app.translations.pgettext_iface("Muscle Workflow") == "Muscle Workflow"
    finally:
        view.language = previous
        i18n.unregister_translations()


def _main():
    tests = [
        test_translations_dict_has_it_IT_entries,
        test_ui_labels_are_translated,
        test_register_and_unregister_translations_in_blender,
    ]
    passed = failed = 0
    for case in tests:
        try:
            case()
        except Exception:
            failed += 1
            traceback.print_exc()
        else:
            passed += 1
    print("RISULTATO passati=%d falliti=%d totale=%d" % (passed, failed, passed + failed))
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(_main())
