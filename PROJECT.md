# Project: FlexForge (1.5 -> 2.0 Update & Global Dynamic Roles/Skills)

## Architecture
- Blender addon (`flexforge/`) targeting Blender 4.2+ (tested on 4.2.3 and 5.2.0), using only the common API subset (no `bpy.app.version` branches).
- One operator per module, registered via `_CLASSES` in `flexforge/__init__.py` (currently 16 classes at 1.5.0).
- Pure helper modules (no operators) for shared logic: `armatura.py`, `weight_nomi.py`, `spatial_grid.py`, `export_selezione.py`, `muscle_shape.py`, `muscle_capsule.py`, `muscle_anatomy.py`, `muscle_drivers.py`, `muscle_side.py`, `i18n.py`, `settings.py`, `rig_detect.py` (also has `detect_rig` operator).
- Target game engines: Godot (4.7.2) + Unity (6000.6.6f1; blocked on Linux without interactive license). Unreal is out of scope.
- Global reusable dynamic roles & skills stored in `~/.gemini/skills/` + `~/.gemini/roles/` (and `.agents/skills/` + `.agents/roles/` for workspace discovery).

## Code Layout
- `flexforge/` — Addon package (`__init__.py`, `blender_manifest.toml`, operators, helpers)
- `tests/` — Headless Blender test suites (`test_*.py`, 22 files, 256 tests at 1.5.0)
- `tools/scripts/` — Gate, version check, zip audit, isolated install, and test runners (`.ps1` + `.py`)
- `docs/` — Documentation (`PUBLICATION_PLAN.md`, etc.)
- `dist/` — Built extension zip packages (gitignored/untracked)

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Global dynamic skills & roles | 5 Blender/engine skills + 4 dynamic role definitions | M0 | ORIGINAL_REQUEST |
| 2 | Linux gate environment | Blender 4.2.3, Blender 5.2.0, Godot 4.7.2, pwsh | M0 | env survey |
| 3 | Align AGENTS.md & 1.5.x package | Sync AGENTS.md to 1.5.0 (16 classes, 256 tests, 28 modules), build/validate `dist/flexforge-1.5.0.zip` | M1 (1.5.x) | piano_update_1.5_2.0 |
| 4 | Create full body end-to-end | Single-undo pipeline: helper -> bind_muscles -> bake_shape_keys -> verify -> engine_budget | M2 (1.6) | piano_update_1.5_2.0 |
| 5 | Bip01 + rig hardening + UI coverage | Real Bip01 verification/regression, UI coverage report (missing presets + why), manual bone picker fallback | M3 (1.7) | piano_update_1.5_2.0 |
| 6 | X-Muscle migration (Milestone B) | Scene-data-only reader (flexor/extensor) -> bone-driven shape keys -> export | M4 (1.8) | piano_update_1.5_2.0 |
| 7 | Smart shape key reduction (Milestone C) | `engine_budget.py`: usage/deformation-contribution + Godot VRAM budget reduction | M5 (1.9) | piano_update_1.5_2.0 |
| 8 | 2.0 RC + release + showcase | RC period, fixes, Extensions release, showcase (Milestone D) | M6 (2.0) | piano_update_1.5_2.0 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M0 | Phase 0: Roles/Skills & Env | Global dynamic roles & skills + Blender 4.2.3/5.2.0, Godot 4.7.2, pwsh | none | DONE |
| M1 | Phase 1.5.x: Align & Package 1.5.0 | AGENTS.md sync + `dist/flexforge-1.5.0.zip` + full gates | M0 | DONE |
| M2 | Phase 1.6: Full Body End-to-End | Single-undo full body pipeline + SpaceDwarf/Xbot/Godot gates | M1 | IN_PROGRESS |
| M3 | Phase 1.7: Bip01 & Rig Hardening | Bip01 + UI coverage report + manual bone picker fallback | M2 | PLANNED |
| M4 | Phase 1.8: X-Muscle Import (B) | Scene-data-only X-Muscle migration + export | M3 | PLANNED |
| M5 | Phase 1.9: Shape Key Reduction (C) | Smart shape key reduction in `engine_budget.py` | M4 | PLANNED |
| M6 | Phase 2.0: RC & Release | 2.0 RC, release, showcase | M5 | PLANNED |

## Interface Contracts
- Addon registration: `flexforge/__init__.py` `_CLASSES` list, `register()` / `unregister()`.
- Pure pipeline functions (no internal `bpy.ops` undo pushes when called from an operator):
  - `muscle_skinning.apply_muscle_skinning(obj, armature=None, radius=...)`
  - `muscle_bake.apply_muscle_bake(obj, armature=None, displacement=..., ...)`
  - `verify.validate_deformation(weights, helper_bones, max_influences)`
  - `engine_budget.apply_engine_budget(obj, ..., lod=1, armature=None)`
  - `export_gltf.export_glb(context, path, ...)`
