# FlexForge

**Status: Alpha (`v1.6.1`)** — Early testing release. Pose-driven muscle workflows are under active testing and refinement; behavior may change between builds.

![CI](https://github.com/PieroFra/FlexForge/actions/workflows/ci.yml/badge.svg)

FlexForge is a Blender add-on that builds anatomical muscle systems on existing character rigs: it detects the rig convention, creates the full set of helper bones with one click, skins the mesh you already have, drives the muscles from pose (bone stretch), manages their weight painting, bakes bounce, and exports engine-ready glTF (.glb) for Godot and Unity.

## Demo & 5-Step Workflow

0. **Detect & Full Body (Single Undo)** — run *Detect rig* on the selected armature to see the convention and which presets match, then run *Create full body*: FlexForge runs the complete end-to-end pipeline in **one undo step** — helper bone creation, capsule skinning, shape-key + driver baking, deformation verification, and LOD-aware engine budget checks (with rollback on error and budget warnings when limits are exceeded).
1. **Create & Bind** — open the FlexForge panel in the Sidebar (N-panel), pick a target rig and muscle preset, then *Create Muscle* and *Bind Muscles*. FlexForge creates the helper bones and binds them: it adds the missing `muscle_*` vertex groups and writes the weights onto the mesh you already have (no muscle mesh is generated).
2. **Pose & Adjust** — pose the rig: muscles contract and bulge driven by the armature (`drive_by_pose`). Tweak the *Muscle Bulge Controls* (bulge scale, directional bias, smoothing) until the flex looks right.
3. **Apply Engine Budget** — run *Apply engine budget* to fit the character to the game budget for the chosen LOD: influences per vertex (max 4), baked shape keys and deform bones, with a readable report (`shape_keys=2/10 bones=5/60 within_budget=yes`).
4. **Bounce & Export** — run *Bake Skin Bounce* to bake the secondary motion onto the timeline, then *Export glTF (.glb)* with the weight budget applied (max 4 influences) for Godot or Unity.

## Current Limitations (Alpha)

- **Bounce is baked to the timeline**, not live: secondary motion only appears after baking, not while dragging a pose in real time.
- **Linked meshes** (library overrides / linked data) require *Make Local* before baking shape keys.
- **No muscle mesh is generated**: FlexForge builds helper bones and skins the mesh you already have.
- **Blender Extensions** status: **1.6.0** is published and **Approved** on [extensions.blender.org](https://extensions.blender.org/add-ons/flexforge/versions/) (Min Blender 4.2.0, sha256 `da7dacc40e2e0ed2d241fea4778299bb7be4a34029fc24c9df23ee864108d043`); **1.6.1** is validated locally and pending upload.

## Status: Alpha vs Local Tests vs Blender Extensions

| Channel | Status |
| --- | --- |
| Release (Alpha) | `v1.6.1` — current build (single-undo full-body pipeline), 100% free GPL-3.0-or-later |
| Local tests & CI | 271/271 checks pass on Blender 4.2.3 LTS and 5.2.0 LTS (`ALL_GATES_OK 4/4`), plus Godot 4.7.2 E2E (`FULLBODY_GODOT_E2E_OK`) |
| Blender Extensions | `1.6.0` published & Approved on [extensions.blender.org](https://extensions.blender.org/add-ons/flexforge/versions/) (Min Blender 4.2.0, sha256 `da7dacc40e2e0ed2d241fea4778299bb7be4a34029fc24c9df23ee864108d043`); `1.6.1` validated locally, pending upload |
## Features & Weight Toolkit

- **One-click full body (single undo)**: detect the rig convention (standard, Mixamo, Bip01, Auto-Rig Pro aliases) and run helper creation, capsule skinning, shape-key baking, verification, and engine budget in a single undoable operator.
- Pose-driven muscle contraction with bulge controls (scale, taper, directional bias).
- Muscle presets (biceps and more), custom bone picker, preset from active mesh.
- Weight toolkit: **limit influences** (max 4), **weight transfer** (nearest-vertex with L/R mapping), **cleanup weights**, **mirror weights** (spatial X-axis mirroring), multi-rig bone aliases (`Bip01`, L/R).
- **Engine budget first**: one button fits a character to the game budget per LOD (influences, shape keys, bones) with a readable report — no competitor does this as a primary feature.
- Deformation verification, shape-key baking, skin bounce baking, one-click muscle cleanup.
- glTF (.glb) export with explicit mesh+armature selection and weight budget enforced before export.
- Interface in English; minimum supported Blender version: 4.2.

## Running Tests

Each suite runs headless inside Blender (`-b --factory-startup`):

```bash
blender -b --factory-startup --python tests/test_bootstrap.py
```

Run every `tests/test_*.py` file; the CI matrix (`.github/workflows/ci.yml`) runs them all on Blender 4.2.3 and 5.2.0, on Ubuntu and Windows, and additionally builds and validates the extension zip.

Install from a build: edit the `dist/flexforge-1.6.1.zip` in Blender via *Edit > Preferences > Add-ons > Install* (or drop `flexforge/` into your add-ons folder).