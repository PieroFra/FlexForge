# FlexForge

**Status: Alpha (`v1.0.2-alpha`)** — Early testing release. Pose-driven muscle workflows are under active testing and refinement; behavior may change between builds.

![CI](https://github.com/PieroFra/FlexForge/actions/workflows/ci.yml/badge.svg)

FlexForge is a Blender add-on that builds anatomical muscle systems on existing character rigs: it creates deformable muscle meshes, drives them from pose (bone stretch), manages their weight painting, bakes bounce, and exports engine-ready glTF/FBX for Godot and Unity.

## Demo & 3-Step Workflow

1. **Create & Bind** — open the FlexForge panel in the Sidebar (N-panel), pick a target rig and muscle preset, then *Create Muscle* and *Bind Muscles*. FlexForge generates the muscle mesh, helper bones and skinning automatically.
2. **Pose & Adjust** — pose the rig: muscles contract and bulge driven by the armature (`drive_by_pose`). Tweak the *Muscle Bulge Controls* (bulge scale, directional bias, smoothing) until the flex looks right.
3. **Bounce & Export** — run *Bake Skin Bounce* to bake the secondary motion onto the timeline, then *Export glTF/FBX* with the weight budget applied (max 4 influences) for Godot or Unity.

## Current Limitations (Alpha)

- **Bounce is baked to the timeline**, not live: secondary motion only appears after baking, not while dragging a pose in real time.
- **Linked meshes** (library overrides / linked data) require *Make Local* before baking shape keys.
- **Blender Extensions** listing is pending: the package validates with `blender --command extension validate`, but it is not published on extensions.blender.org yet.

## Status: Alpha vs Local Tests vs Blender Extensions

| Channel | Status |
| --- | --- |
| Release (Alpha) | `v1.0.2-alpha` — usable, APIs and UI may still change |
| Local tests & CI | 204/204 checks pass on Blender 4.2 and 5.2, Windows + Linux, plus Godot/Unity engine smoke tests |
| Blender Extensions | Not yet published; package passes `extension validate` |

## Features & Weight Toolkit

- Pose-driven muscle contraction with bulge controls (scale, taper, directional bias).
- Muscle presets (biceps and more), custom bone picker, preset from active mesh.
- Weight toolkit: **limit influences** (max 4), **weight transfer** (nearest-vertex with L/R mapping), **cleanup weights**, **mirror weights** (spatial X-axis mirroring), multi-rig bone aliases (`Bip01`, L/R).
- Deformation verification, shape-key baking, skin bounce baking, one-click muscle cleanup.
- glTF/FBX export with explicit mesh+armature selection and weight budget enforced before export.
- Interface in English; minimum supported Blender version: 4.2.

## Running Tests

Each suite runs headless inside Blender (`-b --factory-startup`):

```bash
blender -b --factory-startup --python tests/test_bootstrap.py
```

Run every `tests/test_*.py` file; the CI matrix (`.github/workflows/ci.yml`) runs them all on Blender 4.2.3 and 5.2.0, on Ubuntu and Windows, and additionally builds and validates the extension zip.

Install from a build: edit the `dist/flexforge-1.0.2.zip` in Blender via *Edit > Preferences > Add-ons > Install* (or drop `flexforge/` into your add-ons folder).
