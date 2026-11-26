# AGENTS.md Ã¢â‚¬â€ FlexForge

## Stato del progetto

**Fasi 0, 1, 2, 3 e Milestone A chiuse con gate (Godot + Unity come engine; Unreal fuori perimetro per decisione).** L'addon registra **sedici classi** (`_CLASSES` in `flexforge/__init__.py`) nell'ordine: `FLEXFORGE_PT_main` (`flexforge/ui.py`, pannello), `FLEXFORGE_OT_create_biceps` (`flexforge/muscle.py`, 2a), `FLEXFORGE_OT_limit_weights` (`flexforge/weights.py`, 3a), `FLEXFORGE_OT_verify` (`flexforge/verify.py`, 4a), `FLEXFORGE_OT_export_gltf` (`flexforge/export_gltf.py`, 5a), `FLEXFORGE_OT_weight_transfer` (`flexforge/weight_transfer.py`, 6a), `FLEXFORGE_OT_cleanup_weights` (`flexforge/weights_cleanup.py`, 7a), `FLEXFORGE_OT_mirror_weights` (`flexforge/weights_mirror.py`, 8a), `FLEXFORGE_OT_create_muscle_preset` (`flexforge/muscle_presets.py`, 9a), `FLEXFORGE_OT_bind_muscles` (`flexforge/muscle_skinning.py`, 10a), `FLEXFORGE_OT_bake_shape_keys` (`flexforge/muscle_bake.py`, 11a), `FLEXFORGE_OT_bake_bounce` (`flexforge/muscle_bounce.py`, 12a), `FLEXFORGE_OT_clear_muscles` (`flexforge/muscle_clear.py`, 13a), `FLEXFORGE_OT_apply_budget` (`flexforge/engine_budget.py`, 14a), `FLEXFORGE_OT_detect_rig` (`flexforge/rig_detect.py`, 15a) e `FLEXFORGE_OT_apply_full_body` (`flexforge/muscle_fullbody.py`, 16a). **Build 1.6.0 (allineata su Linux, 2026-11-25):** 29 moduli `.py` in `flexforge/` + `blender_manifest.toml` (30 file); `VERSION_CHECK_OK version 1.6.0`; 22 suite in `tests/test_*.py` (`passati=258 falliti=0 totale=258`) + `tools/tests/test_benchmark.py` (`passati=13 falliti=0 totale=13`) = **271/271** su Blender 4.2.3 LTS e Blender 5.2.0 LTS (`RISULTATO passati=271 falliti=0 totale=271`); pacchetto `dist/flexforge-1.6.0.zip` costruito con Python di Blender 5.2.0 (`python3.13`): **30 file, 68590 byte, sha256 `d32666669657a4ca3964526fad2d770634dc77cf750fe7c2f051521bb1d37807`**, `ZIP_AUDIT_OK | sha256=d32666669657a4ca3964526fad2d770634dc77cf750fe7c2f051521bb1d37807 | files=30`, `blender --command extension validate` exit 0 (`Success parsing TOML in "dist/flexforge-1.6.0.zip"`), `ALL_GATES_OK | gates=4/4 | zip=flexforge-1.6.0.zip` su entrambi i Blender (`v1.6.0-iter2-520` e `v1.6.0-iter2-423`), E2E Godot 4.7.2 `FULLBODY_GODOT_E2E_OK | rigs=2/2` (`MixamoXbotLike.glb` bones=60 shape_keys=18, `ARPSpaceDwarfLike.glb` bones=61 shape_keys=18). (Stato Extensions: 1.1 già pubblica/approvata, 1.5.0 in coda per upload utente; piano 1.5/1.6→2.0 in `docs/UPDATE_PLAN_1.5_TO_2.0.md`; guida sync Windows in `docs/BLENDER_ADDONS_SYNC.md`; nota: `docs/PROMO.md` citato sotto non è presente su `main`.)

## Sorgente di veritÃ  e specchio

- **Sorgente di veritÃƒÂ  (si lavora qui):** `<project_root>/`
- **Specchio di backup (Google Drive):** `<backup_mirror>/`
- **Regola:** dopo ogni avanzamento si risincronizza il Drive con `rsync -av` **senza `--delete`**; il Drive non ÃƒÂ¨ mai la destinazione di lavoro.

## Verifica milestone A — rig reale (fatto)

`detect_rig` valida i 9 ancoraggi muscolari, non solo i loro nomi: con la mappa `parents` (osso -> genitore) verifica i link canonici (`upper_arm.L` sotto `shoulder.L`, `spine.001` sotto `spine`, `forearm.L` sotto `upper_arm.L` ...) e mette in `topology_bad` gli ancoraggi che contraddicono l'aspettativa; i preset con ancoraggio invalido restano fuori da `preset_ids`. Senza `parents`, `topology_ok` resta `None` e la detezione resta quella di prima.

Verifica su rig esterno reale (non committata: Mixamo non è redistribuibile):

- `Xbot.glb` — three.js examples, 2.930.032 byte, sha256 `002f8d269de68e5dce3d25195caf390d1aa359bbfaae3fcf4c8dc78ec36c3ba5`, in `%TEMP%\flexforge_rigtest\`
- Blender 5.2.0 LTS headless, import glTF: `detect_rig` -> `rig_type=mixamo`, `matched 9`, `missing 0`, `coverage 1.00`, 9/9 preset disponibili
- `coverage 1.00` è 9/9 **ossa canoniche**, non 9/67 ossa del rig
- `pectoral`, `latissimus`, `gluteus` hanno `origin_r == origin` (ossa centrali, specchio inerte): corretto, non un difetto
- test offline: `tests\test_rig_detect.py` 10/10, con `_MIXAMO_NAMES` e `_MIXAMO_PARENTS`
- gate: `ALL_GATES_OK | gates=4/4`, suite `RISULTATO passati=250 falliti=0 totale=250` (249 + 1 nuovo)

Verifica su rig reale Auto-Rig Pro (2026-11-25): `SpaceDwarf_Rigging_BYPEFFO2_NEW.blend` (tuo, 16.913.986 byte), copiato in `%TEMP%\flexforge_rigtest\SpaceDwarf.blend` — l'originale non è stato toccato e il file resta fuori dal repo. Blender 5.2.0 LTS headless: `detect_rig` -> `rig_type=standard`, `matched 9`, `missing 0`, `coverage 1.00`, `topology_ok=true` (6 link), 9/9 preset disponibili.

Due difetti trovati dal rig e corretti in `weight_nomi.py`:
- `shin.L` puntava a `DEF_Leg.L`, lo stesso osso di `thigh.L`: quadriceps e hamstring venivano creati con `origin == insertion`. Ora usa `DEF_ForeLeg.L`.
- mancavano le grafie di questo rig (`DEF_UpperArm.L`, `DEF_ForeArm.L`, `DEF_Shoulder.L`, `DEF_Spine.1`, `DEF_Spine.2`), una variante diversa da `DEF-upper_arm.L` che avevo previsto.

Il test di regressione `test_arp_leg_aliases_no_collision` fissa il caso.

Ancora aperto: Bip01 su rig reali.

## Struttura codice

Struttura reale attuale (**1.6.0** — 29 moduli `.py` + `blender_manifest.toml` = 30 file, 16 classi registrate in `_CLASSES`, 22 suite in `tests/` + `tools/tests/test_benchmark.py` = 269 test):

- `flexforge/__init__.py` — entry point dell'addon: `bl_info` versione **1.6.0**, compatibilità minima Blender **4.2** (85 righe); registra esattamente **sedici classi** via `_CLASSES`: `FLEXFORGE_PT_main`, `FLEXFORGE_OT_create_biceps`, `FLEXFORGE_OT_limit_weights`, `FLEXFORGE_OT_verify`, `FLEXFORGE_OT_export_gltf`, `FLEXFORGE_OT_weight_transfer`, `FLEXFORGE_OT_cleanup_weights`, `FLEXFORGE_OT_mirror_weights`, `FLEXFORGE_OT_create_muscle_preset`, `FLEXFORGE_OT_bind_muscles`, `FLEXFORGE_OT_bake_shape_keys`, `FLEXFORGE_OT_bake_bounce`, `FLEXFORGE_OT_clear_muscles`, `FLEXFORGE_OT_apply_budget`, `FLEXFORGE_OT_detect_rig`, `FLEXFORGE_OT_apply_full_body`;
- `flexforge/ui.py` — pannello Sidebar `FLEXFORGE_PT_main` (1a classe);
- `flexforge/muscle.py` — operatore `FLEXFORGE_OT_create_biceps` (2a classe);
- `flexforge/weights.py` — utility pesi e operatore `FLEXFORGE_OT_limit_weights` (3a classe);
- `flexforge/verify.py` — verifica deformazione (`validate_deformation`) e operatore `FLEXFORGE_OT_verify` (4a classe);
- `flexforge/export_gltf.py` — export glTF: operatore `FLEXFORGE_OT_export_gltf` (5a classe);
- `flexforge/export_selezione.py` — helper di selezione per l'export (nessun operatore);
- `flexforge/weight_transfer.py` — weight transfer: operatore `FLEXFORGE_OT_weight_transfer` (6a classe);
- `flexforge/weights_cleanup.py` — pulizia pesi: operatore `FLEXFORGE_OT_cleanup_weights` (7a classe);
- `flexforge/weights_mirror.py` — mirror pesi L/R: operatore `FLEXFORGE_OT_mirror_weights` (8a classe);
- `flexforge/muscle_presets.py` — preset muscolari: operatore `FLEXFORGE_OT_create_muscle_preset` (9a classe);
- `flexforge/muscle_skinning.py` — skinning dei muscoli: operatore `FLEXFORGE_OT_bind_muscles` (10a classe);
- `flexforge/muscle_bake.py` — bake delle shape keys: operatore `FLEXFORGE_OT_bake_shape_keys` (11a classe);
- `flexforge/muscle_bounce.py` — bounce del muscolo: operatore `FLEXFORGE_OT_bake_bounce` (12a classe);
- `flexforge/muscle_clear.py` — cleanup dati muscolo: operatore `FLEXFORGE_OT_clear_muscles` (13a classe);
- `flexforge/engine_budget.py` — engine budget LOD-aware (`apply_engine_budget`): operatore `FLEXFORGE_OT_apply_budget` (14a classe);
- `flexforge/rig_detect.py` — rilevamento convenzione rig + validazione topologica (`detect_rig`): operatore `FLEXFORGE_OT_detect_rig` (15a classe);
- `flexforge/muscle_fullbody.py` — preset full body one-click (`FLEXFORGE_OT_apply_full_body`, 16a classe, delega a `fullbody_pipeline.py`);
- `flexforge/fullbody_pipeline.py` — orchestratore end-to-end single-undo (`run_full_body_pipeline`, rollback su errore, warning budget, nessun operatore);
- `flexforge/muscle_capsule.py` — capsule dei muscoli (nessun operatore);
- `flexforge/muscle_anatomy.py` — anatomia dei muscoli (nessun operatore);
- `flexforge/muscle_drivers.py` — driver dei muscoli (nessun operatore);
- `flexforge/muscle_shape.py` — helper forma/taper/bias/smoothing muscolare (nessun operatore);
- `flexforge/muscle_side.py` — helper lato muscolo (nessun operatore);
- `flexforge/i18n.py` — traduzione interfaccia `it_IT` (nessun operatore);
- `flexforge/settings.py` — `PropertyGroup` impostazioni Sidebar (`register_settings` / `unregister_settings`, nessun operatore);
- `flexforge/weight_nomi.py` — nomi dei vertex group, mapping L/R e alias multi-rig (standard, Mixamo, Bip01, Auto-Rig Pro; nessun operatore);
- `flexforge/armatura.py` — helper armatura condiviso (nessun operatore);
- `flexforge/spatial_grid.py` — griglia spaziale 3D O(N) (nessun operatore);
- `flexforge/blender_manifest.toml` — manifest Extensions Blender 4.2+ (`version = "1.6.0"`);
- `tests/` — 22 suite headless (`test_armatura.py` 3, `test_bootstrap.py` 6, `test_engine_budget.py` 7, `test_export_gltf.py` 18, `test_i18n.py` 3, `test_muscle.py` 11, `test_muscle_anatomy.py` 6, `test_muscle_bake.py` 36, `test_muscle_bounce.py` 8, `test_muscle_clear.py` 4, `test_muscle_fullbody.py` 21, `test_muscle_presets.py` 16, `test_muscle_shape.py` 15, `test_muscle_skinning.py` 34, `test_rig_detect.py` 11, `test_ui_probe.py` 7, `test_verify.py` 8, `test_weight_nomi.py` 5, `test_weight_transfer.py` 11, `test_weights.py` 10, `test_weights_cleanup.py` 9, `test_weights_mirror.py` 9 -> 258 test) + `tools/tests/test_benchmark.py` (13 test) = **271 test totali**;
- `dist/flexforge-1.6.0.zip` — pacchetto Extensions **1.6.0** (**30 file, 68590 byte**, costruito con Python di Blender 5.2.0 `python3.13`, sha256 `d32666669657a4ca3964526fad2d770634dc77cf750fe7c2f051521bb1d37807`, `ZIP_AUDIT_OK`, `extension validate` exit 0, `ALL_GATES_OK | gates=4/4` su Blender 4.2.3 e 5.2.0, `FULLBODY_GODOT_E2E_OK | rigs=2/2`).

**Ancora fuori perimetro:** brush/auto-weights avanzati (esclusi in Fase 3), pubblicazione.
**Fissato:** compatibilitÃƒÂ  Blender **4.2+**, con l'intera suite di test (10 file) eseguita su **4.2 e 5.3 il 2026-11-21** (esiti verbatim nella Tabella Verifica, exit 0 su entrambi). Il 5.3 ÃƒÂ¨ giÃƒÂ  disponibile al path `<blender_path>/`; l'host di sistema resta 5.2.2 LTS invariato.
**Strategia versioni (decisa):** nessun controllo sparso su `bpy.app.version`: l'addon usa solo il sottoinsieme comune di API presente sia su 4.2 sia su 5.3 (Panel/Operator, props, modifiers, vertex_groups, exporter stock); le differenze di versione si verificano eseguendo la suite su entrambi i Blender, non con rami condizionali nel codice.

**Fissato:** target engine Ã¢â‚¬â€ Godot + Unity (per decisione, Unreal fuori); smoke test Godot 4.7.2 e Unity 6000.6.6f1 entrambi PASS. **Release 1.0.0 (2026-11-22):** suite 15 file, 170/170 su Blender 5.2 Windows (12 classi, 11 operatori); **aggiornata (2026-11-22): 15 suite, 175/175** - fix in `flexforge/muscle_bake.py` (suite 174/174 dopo lo split di `muscle_skinning.py` con nuovo modulo `flexforge/muscle_capsule.py`, 231 righe); GUI a 5 box con icone, sezione `Muscle Bulge Controls`, contrazione `drive_by_pose`, alias `Bip01` multi-rig; pacchetto `dist/flexforge-1.0.0.zip` ricostruito con Python di Blender 5.2: 21 file, 42634 byte, sha256 `4cbe6a857195333c652760e610523744011522faae7acb6e55d5ba088b231674`. **Aggiornata (2026-11-22, task m33-test): 15 suite, 175/175** Ã¢â‚¬â€ `VERIFY_OK | passed=175 | failed=0 | diff=0` dopo il fix in `flexforge/muscle_capsule.py`; pacchetto ricostruito con Python di Blender 5.2: 21 file, 42723 byte, sha256 `8fd1d1fad4f2964ded1b8458ac1dfe8fdb0936309ba33660a229cceb53ac4413`. **Aggiornata (2026-11-22, i18n): 16 suite, 179/179** â€” nuovo modulo `flexforge/i18n.py` (84 righe, traduzione `it_IT`) con suite `test_i18n.py`; pacchetto ricostruito con Python di Blender 5.2: 22 file, 44314 byte, sha256 `9936f343fdce90f174759157cab460129d29d34433e3860d4d337db33b05e3b3`, `extension validate` exit 0.

## Tabella Verifica

| Verifica | Comando | Stato |
| --- | --- | --- |
| Smoke test GUI (Blender) | Ã¢â‚¬â€ | **NOT CONFIGURED** (serve la GUI reale) |
| Gate interattivo GUI (MCP+GUI live) | socket Blender MCP `127.0.0.1:9876` (Blender 5.2.2 live dell'utente) + `addon-mcp-gui-gate` | **Configurato** (eseguito 2026-11-21: `VERDICT_MCPGUI_REGISTER_OK classi=8`, `VERDICT_MCPGUI_OPS_OK` 5/5 `FINISHED`, `VERDICT_MCPGUI_OK \| operatori=5`, `.glb` 2,8K ossa=3; pulizia scena `VERDICT_MCPGUI_CLEAN_OK`). Gate GUI Xvfb eseguito post-traduzione (2026-11-21): `VERDICT_GUI_OK | operatori=5 render=ok`, render viewport 80K con cubo di prova (script tmp `flexforge_gui_gate_en.py`) |
| Probe UI headless (pannello + 7 operatori) | `flatpak-spawn --host <blender_path>/blender -b --factory-startup --python ".../tests/test_ui_probe.py"`; identico con blender-5.3 | **Configurato** (eseguito 2026-11-21 su entrambi, exit 0: `VERDICT_UI_OK | passati=3 falliti=0 totale=3`); **rieseguita su Blender 5.2 Windows: `passati=4 falliti=0 totale=4` con `context_summary`** |
| Packaging Extensions 1.0.0 | zip `dist/flexforge-1.0.0.zip` + install_check in Blender 5.3 headless | **Configurato** (eseguito 2026-11-21: `PKG_OK classi=8`, `PKG_OPERATORS_OK`; sha256 `37b7b5b437d3de605c98d3075d4ea47dda1de4567983f1aa2c3967eb9b48a50d`; **pacchetto inglese ricostruito 2026-11-21: 18722 byte, sha256 `576d579d4e570c9f2013fd46f2d0e92cd0801157838eb5bdbe8de73f7694ff92`, `PKG_OK classi=8`**; **ricostituito 2026-11-21 su Windows con Python di Blender 5.2 (13 file): 20291 byte, sha256 `5ccaf5197496cae1b404a968789c754a2fbde92c03b987f5f43f0ab6fba53a4c`**; **ricostituito 2026-11-21 su Windows con Python di Blender 5.2 (16 file, 29295 byte): sha256 `89b4a39db80cf1635ee69d425fd20154f675f51f5e69b44bb5588695b7317415`**; **ricostituito 2026-11-21 su Windows con Python di Blender 5.2 (17 file): 31656 byte, sha256 `f47fbd54855d6fe861634f6fd044d910b114539531e37a3e406bedef71c51091`**; **ricostruito 2026-11-21 su Windows con Python di Blender 5.2 (18 file, con `flexforge/muscle_shape.py`): 34228 byte, sha256 `a8e2dd253f3f8a8840fe3702b1c29a29ac5cf9d253dc5bc8da18acfc56929a54`**; **ricostruito 2026-11-22 su Windows con Python di Blender 5.2 (20 file, con `flexforge/muscle_bounce.py` e `flexforge/muscle_side.py`): 40329 byte, sha256 `2322e46ae01c6b245018992879844000f3297739ca3db182d2023189f911ba1d`**; **release 1.0.0 ricostruita 2026-11-22 su Windows con Python di Blender 5.2 (20 file): 41415 byte, sha256 `c53c4be6a0a3c037c175ffc05f5b06bcba4169c4da0745d6092bfe4f0e681495`, nessun duplicato di percorso, `flexforge/__init__.py` e `flexforge/blender_manifest.toml` presenti con versione 1.0.0** |
| Test headless runner (16 file: bootstrap, muscle, weights, verify, export_gltf, weight_transfer, weights_cleanup, weights_mirror, weight_nomi, armatura, ui_probe, muscle_presets, muscle_skinning, muscle_bake, muscle_bounce, i18n) | `flatpak-spawn --host <blender_path>/blender -b --factory-startup --python "<project_root>/tests/test_bootstrap.py"` Ã¢â‚¬â€ ripetuto su gli altri 10 file di `tests/`; identico con `<blender_path>/blender` | **Configurato** (eseguito 2026-11-21 su entrambi i Blender, exit 0 su tutti i 20 run: bootstrap 6/6, muscle 8/8, weights 10/10, verify 8/8, export 18/18, weight transfer 10/10, cleanup 9/9, mirror 8/8, nomi 2/2, armatura 3/3; **rieseguito post-traduzione inglese: 85/85 su 4.2.23 e 5.3.0, exit 0**; **rieseguito su Blender 5.2 Windows: 11 suite, 88/88 (muscle 9/9 con STRETCH_TO/bulge, weights_mirror 9/9 con `mirror_weights_spatial` asse X, ui_probe 4/4 con `context_summary`, altri invariati)**; **esteso su Blender 5.2 Windows (2026-11-21): 14 suite, 133/133 Ã¢â‚¬â€ muscle_presets 15/15, muscle_skinning 16/16, muscle_bake 14/14, bootstrap 6/6 su 11 classi, ui_probe 4/4 su 11 operatori, altri conteggi invariati**); **aggiornata 2026-11-21 su Blender 5.2 Windows: 14 suite, 134/134 - `weight_nomi` `RISULTATO passati=3 falliti=0 totale=3` (alias multi-rig + infissi L/R), nuovo modulo `flexforge/spatial_grid.py` 62 righe griglia spaziale 3D O(N)**)); **aggiornata 2026-11-22 su Blender 5.2 Windows: 15 suite, 170/170 Ã¢â‚¬â€ nuova suite `muscle_bounce` su `flexforge/muscle_bounce.py` (operatore `FLEXFORGE_OT_bake_bounce`), dodici classi**; **aggiornata 2026-11-22: 15 suite, 174/174 Ã¢â‚¬â€ split di `flexforge/muscle_skinning.py` (175 righe) con nuovo modulo `flexforge/muscle_capsule.py` (231 righe)**; **aggiornata 2026-11-22: 15 suite, 175/175 Ã¢â‚¬â€ fix in `flexforge/muscle_bake.py`, pacchetto ricostruito**; **aggiornata 2026-11-22 (m33-test): 15 suite, 175/175 Ã¢â‚¬â€ fix in `flexforge/muscle_capsule.py`, `VERIFY_OK | passed=175 | failed=0`, pacchetto ricostruito (21 file, 42723 byte, sha256 `8fd1d1fad4f2964ded1b8458ac1dfe8fdb0936309ba33660a229cceb53ac4413`)**; **aggiornata 2026-11-22 (i18n): 16 suite, 179/179 â€” nuovo modulo `flexforge/i18n.py` (84 righe, traduzione `it_IT`) con suite `test_i18n.py`, pacchetto ricostruito (22 file, 44314 byte, sha256 `9936f343fdce90f174759157cab460129d29d34433e3860d4d337db33b05e3b3`), `extension validate` exit 0** |

| Traduzione inglese addon (codice/UI/messaggi, docs restano italiani) | 12 moduli `flexforge/*.py` + 11 test tradotti; nomi EN: `read_weights`, `export_glb`, `validate_deformation`, `clean_weights`, `mirror_weights`, `nearest_vertex`, `path` | **Configurato** (eseguito 2026-11-21: suite 85/85 su 4.2.23 e 5.3.0; gate MCP+GUI inglese 5/5 `FINISHED` con messaggi EN `FlexForge - weights: vertices=8 ...`, `FlexForge - glTF: file=... bones=3 meshes=1 max_influences=4`; Godot `ENGINE_CHECK_OK` e Unity `ENGINE_CHECK_OK` rieseguiti sul `.glb`/`.fbx` nuovi; screenshot sidebar fornito dall'utente con 7 bottoni in inglese) |
| Engine smoke test (Godot headless) | `python "%USERPROFILE%\.agents\scripts\godot_import_check.py" flexforge_test.glb --min-bones 1 --min-meshes 1` (da `<tmp_dir>/`, dove l'export produce il `.glb`; Godot 4.7.2 su host) | **Configurato** (eseguito 2026-11-21, exit 0: `ENGINE_CHECK_OK | engine=godot | file=flexforge_test.glb | bones=3 | seg_bones=3 | meshes=1 | anims=0 | max_len=0.00s`; Unity `ENGINE_CHECK_OK` (2026-11-21, FBX di prova, bones=3 meshes=1 clips=2 max_len=1,21s; licenza Personal copiata dalla sandbox Flatpak di Hub); Unreal fuori perimetro per decisione) |

Il runner headless e l'Engine smoke test (Godot) sono oggi le uniche verifiche configurate; lo Smoke test GUI e il Gate interattivo GUI restano `NOT CONFIGURED`. Nota non bloccante (2026-11-21): MeshOptimizer assente in Blender 5.2.2 Ã¢â‚¬â€ errore non bloccante, esiti di test e smoke comunque verdi. Gate GUI interattivo chiuso via MCP+GUI su sessione live (skill `addon-mcp-gui-gate`); la probe UI headless resta sonda automatica.

## Vincoli macchina (Windows, runtime Goose)

- Ambiente unico: **Windows**. Shell: PowerShell 5.1/7
  (`powershell -NoProfile -ExecutionPolicy Bypass -File ...`).
- Il sandbox Fedora/Flatpak non esiste piu': nessun `flatpak-spawn`, nessuna
  traduzione Linux degli script.
- Gli script del repo stanno in `tools\scripts\` (verificati il 2026-11-23:
  `RISULTATO passati=204 falliti=0 totale=204`). Gli script globali condivisi
  stanno in `%USERPROFILE%\.agents\scripts\`.
- File temporanei solo in `$env:TEMP` (`%TEMP%`), mai nella radice del repo.
- Se un programma richiesto non e' raggiungibile, dichiarare NON ESEGUIBILE +
  motivo e fermarsi; non improvvisare sostituzioni.

## Regole di codice

1. **Un test automatico per ogni funzione**: ogni funzione pubblica nuova ha il suo caso di test in `tests/test_*.py`; niente funzioni senza copertura.
2. **Niente file monolitici**: un modulo per responsabilitÃƒÂ  (es. `muscle.py`, `ui.py`), funzioni corte e singole responsabilitÃƒÂ , file che restano correggibili a occhio; se un modulo supera ~250 righe va spezzato.
3. Il `coder` scrive il test insieme alla funzione, nello stesso sprint; il tester esegue, non riscrive.
4. Se una correzione rompe un test esistente, si corregge il codice, mai l'assert.

## Regole di lavoro

1. Documentazione in **italiano**; codice, UI e messaggi dell'addon interamente in **inglese** (per decisione 2026-11-21).
2. Dati reali soltanto: mai inventare conteggi, log o hash; riportarli verbatim dalla fonte reale.
3. Nessun gate dichiarato superato: la decisione spetta ai comandi reali della Tabella Verifica, quando esisteranno.
4. Il `coder` scrive codice e test; `ops` tiene allineati documenti e specchio Drive.
  
"5. **Subagent obbligatori**: ogni lavoro che richiede strumenti (script, gate, audit, test, revisione) va delegato a un subagent con istruzioni autosufficienti e con il file di contesto che serve. Non si esegue a mano. Se un sub fallisce o va in timeout, si riavvia con `resume` spezzando il compito, non si ripete il tentativo."  

## Milestone A chiusa — release 1.5.0 (2026-11-25)

Milestone A (“Rig Detection + One-Click Full-Body Preset”) è chiusa su rig reali e l'addon è a **1.5.0**.

- **Nuovo operatore** `flexforge.apply_full_body` (`flexforge/muscle_fullbody.py`, pulsante “Create full body” nel box *Muscle Workflow*): crea in un solo click i chain helper di **tutte** le preset che risolvono sull'armatura attiva, con `mirror_lr`, ripristino selezione/mode e report `FlexForge - rig: type=standard ... presets=biceps,... | created 44 bones on 9 presets`.
- **`rig_detect.apply_full_body`** ora espone `segments` e usa `full_body_message()`: prima restituiva solo `detect_message`, quindi l'utente non sapeva se qualcosa era stato creato. Test `test_full_body_message_counts_created` in `tests/test_muscle_fullbody.py`.
- **Verifica su rig reale (SpaceDwarf_Rigging_BYPEFFO2_NEW.blend, copiata in `%TEMP%`, originale non toccato)**: `detect_rig` -> `rig_type=standard`, matched 9/9, coverage 1.00, 9 preset; `apply_full_body` -> `{'FINISHED'}`, armature **350 -> 394 ossa** (44 helper create), 0,02 s. Verifica eseguita con headless Blender 5.2, script `verify_fullbody.py` in `%TEMP%\flexforge_rigtest\`.
- **Verifica su rig Mixamo (sintetica in test)**: 9 preset x L/R -> `created 44 bones on 9 presets`, `{'FINISHED'}`, mode e selezione ripristinati.
- **Release 1.5.0**: `bl_info` e `blender_manifest.toml` a 1.5.0, README aggiornato (flusso 5 passi, rig detection, “Not yet published”), `dist/flexforge-1.5.0.zip` = 29 file, 64874 byte, sha256 `e05a873e49404f0314023acc909b4dc386ab518773b36d644a27ecb6fc28d5ba`; `blender --command extension validate` exit 0; gate 4/4 (`ALL_GATES_OK | gates=4/4 | zip=flexforge-1.5.0.zip | task=release-1.5.0-01`), suite `RISULTATO passati=256 falliti=0 totale=256`.
- **Ancora aperto**: Bip01 mai testato su un rig Bip01 reale (le alias ci sono in `weight_nomi.py`). Pubblicazione su Extensions/Blender Artists/Reddit: pianificata, non ancora fatta (utente ha chiesto prima un piano di pubblicazione).

## Release 1.5.0 - repo e promo chiuse (2026-11-25)

- `docs/PROMO.md` riscritto da 1.0.0 a 1.5.0: short description, thread Blender Artists, post
  Reddit e checklist. La promo porta i numeri misurati dal progetto (9 presets, 44 helper,
  350 -> 394 ossa, 0,02 s, 256/256) e dice in modo esplicito che "Create full body" crea i
  chain helper e non mesh né pesi: `Bind muscles` è un passaggio separato.
- `docs/PUBLICATION_PLAN.md` resta il piano a 3 fasi (Extensions -> Blender Artists -> Reddit).
  Nessun trailer o video di marketing.
- Repo GitHub: la CI è stata portata su `.github/workflows/ci.yml` con job di packaging
  version-aware - legge `version` da `flexforge/blender_manifest.toml`, costruisce
  `dist/flexforge-<v>.zip` invece del nome flesso `flexforge-1.0.2.zip`, valida l'estensione
  e carica l'artifact - e un passo `Check versions` che confronta `bl_info` e manifest.
  Modifica sul branch `chore/standardize-and-gates`.
- `tools/verify.config.psd1`: `ExpectedTotal` portato da 246 a 256 (era stantio rispetto ai
  256 test reali della release).
- Gate su `chore/standardize-and-gates` dopo la promo, eseguito il 2026-11-25:

  `ALL_GATES_OK | gates=4/4 | zip=flexforge-1.5.0.zip | task=promo-repo-20261125-01`

  Suite `RISULTATO passati=256 falliti=0 totale=256`; `INSTALL_OK | zip=flexforge-1.5.0.zip`;
  `ZIP_AUDIT_OK | sha256=e05a873e49404f0314023acc909b4dc386ab518773b36d644a27ecb6fc28d5ba |
  files=29`. Il sha256 del pacchetto non cambia rispetto al release: solo documentazione e CI
  sono stati toccati, il codice del pacchetto resta identico.
- Repo GitHub: PR #1 (`chore/standardize-and-gates` -> `main`) aperta il 2026-11-25 con tag
  `v1.5.0`. La merge di `main` è senza conflitti di contenuto (i suoi commit CI erano già
  riapplicati); il pacchetto non cambia.
- **Corretto un fallimento vero della matrice CI su Blender 4.2.3**: la suite
  `test_muscle_fullbody` falliva con `AssertionError: muscle_biceps_01` perché la fixture
  `_make_mixamo_armature` metteva tutti i teste degli osso a `(0,0,0)`: le catene di muscolo
  risultavano a lunghezza zero e il Blender 4.2.3 **scarta** un edit bone con head e tail
  coincidenti quando si esce da Edit Mode (il 5.2 lo conserva). Fixture corretta con teste
  distinte lungo il corpo; la suite 256/256 passa ora sia su 4.2.3 sia su 5.2.0, quindi la
  matrice CI (4.2.3 + 5.2.0, Ubuntu + Windows) è verificata su entrambi i Blender.
  Nota da tenere: una fixture a teste coincidenti non è un caso reale, ma è la ragione per
  cui non si deve mai "dimostrare" una feature su una riga sintetica degenere.


## Chiusura CI e documentazione (2026-11-25)

Chiusura della sessione su documentazione e workflow CI del branch
`chore/standardize-and-gates` (repository gia' su GitHub). Nessuna modifica al
codice dell'addon: solo documentazione, CI e allineamento.

- `README.md` allineato al codice: rimosse le affermazioni false (nessuna mesh
  muscolare generata, export solo glTF `.glb`, non FBX); aggiunto il bullet
  Limitations "No muscle mesh is generated". Commit `a30ab41`.
- Nuovo `docs/VIDEO_PIPELINE.md`: piano operativo della pipeline video
  (blender-gui-capture / obs-screen-capture / ffmpeg, verifiche `gif_check.py`)
  dichiarato esplicitamente come piano e NON come risultato. Nessun trailer,
  video o GIF prodotto (vincolo utente). Commit `98c98fa`.
- Tre bug veri del workflow CI trovati e chiusi, tutti rivelati dal fix
  precedente dei test su Blender 4.2.3:
  1. step "Check versions": su `ubuntu-latest` `python3` riceveva il path
     troncato `'.../FlexForge/t'`. Causa radice: l'array condizionale di UN
     elemento su Linux diventa una stringa scalare e `& $py @pyArgs` la splatta
     carattere per carattere. Fix: due rami espliciti senza splat. Commit
     `6179556`.
  2. step "Read version" (job package): scriveva il valore nudo `1.5.0` su
     `GITHUB_OUTPUT` -> "Invalid format '1.5.0'". Fix: forma `key=value`
     (`version=...`). Commit `29e2574`. (Era mascherato dal fatto che il job
     package saltava finche' i test erano rossi.)
  3. un primo tentativo di fix (solo rename `$args`->`$pyArgs`, commit
     `adfd00a`) NON era la causa: documentato come falso bersaglio, per non
     ripetere l'errore.
- Esito finale: CI 5/5 job verdi (ubuntu+windows x Blender 4.2.3/5.2.0 +
  package), PR #1 mergeable/CLEAN, artifact `flexforge-1.5.0`, 63053 byte.
  Gate locale (2026-11-25, HEAD `29e2574`):
  `ALL_GATES_OK | gates=4/4 | zip=flexforge-1.5.0.zip | task=final-20261125-01`.
- Nota: il tag `v1.5.0` resta su `768a630` (il pacchetto non e' cambiato: i 4
  commit successivi sono solo documentazione e CI).


## Bugfix 2026-11-25 (post-1.5.0)

Due bug riparati dalla sessione post-release, piu' un terzo aperto. Versione
invariata: **1.5.0**.

- **Alias spine a due cifre** (`flexforge/weight_nomi.py`): i rig che scrivono le
  spine come `Spine01`/`Spine02` non risolvevano alcun ancoraggio, quindi i
  muscoli del torso non venivano creati. Causa radice: mancavano gli alias
  `"Spine01" -> spine.001` e `"Spine02" -> spine.002` nella mappa nomi.
- **Raggi capsula scala-invarianti** (`flexforge/muscle_skinning.py`,
  `flexforge/muscle_capsule.py`): su una scena in metri i raggi delle capsule
  venivano misurati in unita' di scena e non scalati dal `unit_scale`, quindi il
  bind legava meno helper del dovuto. Causa radice: i raggi usavano distanze
  assolute invece di essere normalizzati per `unit_scale`. In metri i pesi
  restano identici a prima (`vertices_bound=15583`/`muscles_bound=13` prima e
  dopo su scena ripulita).

**Test nuovi (5):** `tests/test_alias_gap.py` (2 casi: alias spine a due cifre),
`tests/test_skinning_scale.py` (3 casi: raggi capsula scala-invarianti).

**Totale suite: `RISULTATO passati=261 falliti=0 totale=261`** su Blender 4.2.3 e
5.2 (prima 256/256).

**Gate (2026-11-25, task `skinfix-20261125-01`):**
`ALL_GATES_OK | gates=4/4 | zip=flexforge-1.5.0.zip | task=skinfix-20261125-01`;
`ZIP_AUDIT_OK | sha256=9aa49cb0d06930827e8b9147e65d104a172b1fe1cbb4f784e217acd3cb8b4286 | files=29`.
Pacchetto `dist/flexforge-1.5.0.zip` ricostruito: 29 file, 66153 byte (prima
64874 byte, sha256 `e05a873e49404f0314023acc909b4dc386ab518773b36d644a27ecb6fc28d5ba`).

**BUG 3 — APERTO:** il `bind` reale lega **13/44** helper su scena ripulita; il
`muscles_bound=35` visto nei log era gonfiato da pesi preesistenti sulla mesh.
I 31 helper non legati dipendono dal cap di raggio = 1/4 dello span dell'helper,
che resta sotto la distanza helper->pelle; alzare il cap cambierebbe i pesi in
metri e romperebbe 3 test pinnati: serve una decisione di design.

## Release 1.5.1 (2026-11-25)

Release 1.5.1 chiude il BUG 3 aperto in 1.5.0: il `bind` reale legava 13/44
helper. Causa radice: il raggio della capsula era cappato a 1/4 dello span
dell'helper, e sui helper corti quel cap resta sotto la distanza helper->pelle,
quindi la capsula non raggiungeva la superficie da pesare. Fix in
`flexforge/muscle_capsule.py`: un coverage-floor alza il raggio a
`SKIN_REACH_FACTOR` (1.9) volte la distanza dall'asse dell'helper al vertice
piu' vicino che puo' pesare (la sua bone mask, sul lato giusto), ma mai oltre
il raggio effettivo dell'envelope (tetto `DEFAULT_RADIUS`). La formula e'
`radius = max(span_cap, min(1.9 * skin_distance, radius_eff))`; il percorso
vecchio resta invariato quando `skin_distance` e' assente.

- **Evidenza (scena reale ripulita, Blender 5.2):** il bind passa da
  `muscles_bound=13` a **34** (`vertices_bound` 15583 -> **45505**); niente
  bleeding: `high_pairs w>0.3 = 0`, `opposite_side = 0`.
- **Test nuovi (5):** `tests/test_muscle_coverage.py` (lo span cap da solo
  lascia l'helper corto fuori dalla pelle; l'helper corto raggiunge la pelle; il
  reach si ferma appena oltre la pelle; nessun bleeding sull'altro lato;
  coverage scala-invariante). Aggiornati i due pin di versione in
  `tests/test_bootstrap.py` a 1.5.1.
- **Totale suite: `RISULTATO passati=266 falliti=0 totale=266`** su Blender
  4.2.3 e 5.2 (prima 261/261).
- **Gate (2026-11-25, task `release-1.5.1-20261125`):**
  `ALL_GATES_OK | gates=4/4 | zip=flexforge-1.5.1.zip | task=release-1.5.1-20261125`.

**BUG 3 — ancora APERTO (residuo):** restano **11/44** helper non legati, per
ragioni diverse dal cap: il tetto dell'envelope `DEFAULT_BONE_RADIUS = 0.1 m`
e la competizione/sbudget tra capsule sovrapposte (piu' helper che
reclamerebbero lo stesso vertice oltre il budget di influenze). Da decidere.

**Nota documenti:** `docs/PROMO.md` e' aggiornato su disco a 1.5.1 ma resta
escluso dal gitignore globale dell'utente (`~/.gitignore_global`), quindi non e'
versionato in questo commit.
