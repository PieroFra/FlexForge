# Deterministic headless test of the FlexForge bootstrap.
# No external dependency: if bpy is not available a minimal stub is installed
# in sys.modules so the package can be imported outside Blender.
# When run inside Blender the real bpy is used instead.

import sys
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def _install_bpy_stub():
    """Install the shared bpy stub only if the real module is missing."""
    try:
        import bpy  # noqa: F401
        return False
    except ImportError:
        pass

    stub_folder = "/tmp/flexforge_test"
    if stub_folder not in sys.path:
        sys.path.insert(0, stub_folder)
    from flexforge_stub import installa_stub_bpy as install_bpy_stub

    installed = install_bpy_stub()
    # The shared stub does not expose FloatProperty, which the new
    # weight_transfer module needs: the test adds it, not the addon code.
    import bpy
    if not hasattr(bpy.props, "FloatProperty"):
        bpy.props.FloatProperty = lambda **kwargs: dict(kwargs)
    return installed


def _load_manifest():
    """Read the manifest with tomllib, tomli fallback, regex fallback."""
    path = BASE / "flexforge" / "blender_manifest.toml"
    text = path.read_text(encoding="utf-8")

    try:
        import tomllib
        return {"mode": "tomllib", "data": tomllib.loads(text), "text": text}
    except ImportError:
        pass

    try:
        import tomli
        return {"mode": "tomli", "data": tomli.loads(text), "text": text}
    except ImportError:
        pass

    # Fallback: extraction of the expected scalar keys only.
    import re
    data = {}
    for key in ("id", "name", "version", "blender_version_min"):
        match = re.search(r'^%s\s*=\s*"([^"]*)"' % key, text, re.MULTILINE)
        if match:
            data[key] = match.group(1)
    return {"mode": "regex", "data": data, "text": text}


def test_bl_info_present():
    import flexforge
    assert hasattr(flexforge, "bl_info"), "bl_info missing"
    assert isinstance(flexforge.bl_info, dict), "bl_info is not a dict"


def test_bl_info_fields():
    import flexforge
    info = flexforge.bl_info
    assert info["name"] == "FlexForge", info.get("name")
    assert tuple(info["blender"]) == (4, 2, 0), info.get("blender")
    assert tuple(info["version"]) == (1, 6, 0), info.get("version")
    assert info["category"] == "Rigging", info.get("category")


def test_expected_classes():
    import flexforge
    assert isinstance(flexforge._CLASSES, tuple), "_CLASSES is not a tuple"
    assert len(flexforge._CLASSES) == 16, (
        "expected 16 classes (panel + muscle operator + weights operator"
        " + verify operator + glTF export operator"
        " + weight transfer operator + weight cleanup operator"
        " + weight mirror operator + muscle preset operator"
        " + muscle binding operator + shape key bake operator"
        " + skin bounce bake operator + clear muscles operator"
        " + engine budget operator + rig detection operator"
        " + full body operator),"
        " found %d: %s"
        % (len(flexforge._CLASSES), [c.bl_idname for c in flexforge._CLASSES])
    )
    assert flexforge._CLASSES[0].bl_idname == "FLEXFORGE_PT_main"
    assert flexforge._CLASSES[1].bl_idname == "flexforge.create_biceps"
    assert flexforge._CLASSES[2].bl_idname == "flexforge.limit_weights"
    assert flexforge._CLASSES[3].bl_idname == "flexforge.verify"
    assert flexforge._CLASSES[4].bl_idname == "flexforge.export_gltf"
    assert flexforge._CLASSES[5].bl_idname == "flexforge.weight_transfer"
    assert flexforge._CLASSES[6].bl_idname == "flexforge.cleanup_weights"
    assert flexforge._CLASSES[7].bl_idname == "flexforge.mirror_weights"
    assert flexforge._CLASSES[8].bl_idname == "flexforge.create_muscle_preset"
    assert flexforge._CLASSES[9].bl_idname == "flexforge.bind_muscles"
    assert flexforge._CLASSES[10].bl_idname == "flexforge.bake_shape_keys"
    assert flexforge._CLASSES[11].bl_idname == "flexforge.bake_bounce"
    assert flexforge._CLASSES[12].bl_idname == "flexforge.clear_muscles"
    assert flexforge._CLASSES[13].bl_idname == "flexforge.apply_budget"
    assert flexforge._CLASSES[14].bl_idname == "flexforge.detect_rig"
    assert flexforge._CLASSES[15].bl_idname == "flexforge.apply_full_body"


def test_sidebar_panel():
    import flexforge
    import bpy
    panel = flexforge._CLASSES[0]
    # Inside real Blender bpy: effective subclass of bpy.types.Panel.
    # With the stub (outside Blender) issubclass would always be true, so we
    # also check that the panel exposes the two mandatory attributes.
    assert issubclass(
        panel, bpy.types.Panel
    ), "the panel does not derive from Panel"
    assert hasattr(bpy.types, "Panel"), "bpy.types.Panel missing"
    assert hasattr(panel, "bl_idname"), "the panel is missing bl_idname"
    assert hasattr(panel, "bl_space_type"), "the panel is missing bl_space_type"
    assert panel.bl_space_type == "VIEW_3D", panel.bl_space_type
    assert panel.bl_region_type == "UI", panel.bl_region_type
    assert panel.bl_category == "FlexForge", panel.bl_category
    assert panel.bl_label == "FlexForge", panel.bl_label


def test_register_unregister():
    import flexforge
    import bpy
    uses_stub = hasattr(bpy, "_registrate")
    # Inside real Blender bpy: register() must make the panel appear in
    # bpy.types and unregister() must remove it. With the stub the call
    # counter is used to tell a broken register from a working one.
    flexforge.register()
    if uses_stub:
        assert len(bpy._registrate) == 15, "register() not registered with stub"
    else:
        assert hasattr(bpy.types, "FLEXFORGE_PT_main"), (
            "register() did not register the panel in bpy.types"
        )
    flexforge.unregister()
    if uses_stub:
        assert len(bpy._registrate) == 0, "unregister() did not remove with stub"
    else:
        assert not hasattr(bpy.types, "FLEXFORGE_PT_main"), (
            "unregister() did not remove the panel from bpy.types"
        )
    # Check that register/unregister respond coherently again, to rule out a
    # case where the second pair of calls is a no-op.
    if uses_stub:
        flexforge.register()
        assert len(bpy._registrate) == 15, "register() not registered with stub"
        flexforge.unregister()
        assert len(bpy._registrate) == 0, "unregister() did not remove with stub"


def test_valid_manifest():
    outcome = _load_manifest()
    data = outcome["data"]
    assert data.get("id") == "flexforge", data.get("id")
    assert data.get("name") == "FlexForge", data.get("name")
    assert str(data.get("version")) == "1.6.0", data.get("version")
    assert str(data.get("blender_version_min")) == "4.2.0", data.get(
        "blender_version_min"
    )
    assert data.get("maintainer"), "maintainer missing"
    assert "network" not in (data.get("permissions") or {}), data.get("permissions")

    license_value = data.get("license")
    if outcome["mode"] == "regex":
        assert "SPDX:" in outcome["text"], "SPDX license missing in the manifest"
    else:
        entries = license_value if isinstance(license_value, (list, tuple)) else [license_value]
        assert any(isinstance(v, str) and v.startswith("SPDX:") for v in entries), (
            "SPDX license missing: %r" % (license_value,)
        )


def _main():
    _install_bpy_stub()

    tests = [
        test_bl_info_present,
        test_bl_info_fields,
        test_expected_classes,
        test_sidebar_panel,
        test_register_unregister,
        test_valid_manifest,
    ]

    passed = 0
    failed = 0
    for case in tests:
        try:
            case()
        except Exception:
            failed += 1
            traceback.print_exc()
        else:
            passed += 1

    total = passed + failed
    print("RISULTATO passati=%d falliti=%d totale=%d" % (passed, failed, total))
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(_main())
