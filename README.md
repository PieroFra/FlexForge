# FlexForge

**Release 1.0.1 (2026-11-22):** pacchetto `dist/flexforge-1.0.1.zip` — 24 file, 47077 byte, sha256 `3f836e818faba018224b818d2967615d3752b7151b36e621e01c54bc47ee1592`, `extension validate` exit 0; suite 17 file, 189/189 su Blender 5.2 Windows (anatomical muscle taper, anterior/posterior directional bias, Laplacian edge smoothing, smooth deltas).

**Release 1.0.0 (2026-11-22):** pacchetto `dist/flexforge-1.0.0.zip` — 24 file, 47074 byte, sha256 `f151f57e0de64902f30337bbdb624c267052f202cbeaf50390286c080e0748c0`, `extension validate` exit 0; suite 17 file, 189/189 su Blender 5.2 Windows (nuovi moduli `flexforge/muscle_anatomy.py` 93 righe con suite `test_muscle_anatomy.py` e `flexforge/muscle_drivers.py` 65 righe; modulo `flexforge/i18n.py` 84 righe, traduzione `it_IT`, con suite `test_i18n.py`; fix in `muscle_bake.py` e in `muscle_capsule.py`; split di `muscle_skinning.py` con nuovo modulo `flexforge/muscle_capsule.py`, 231 righe); 12 classi, 11 operatori; GUI a 5 box con icone, sezione `Muscle Bulge Controls`, contrazione `drive_by_pose`, alias `Bip01` multi-rig; smoke Godot 4.7.2 e Unity 6000.6.6f1 `ENGINE_CHECK_OK`.

Addon Blender con **MVP muscolare, verifica deformazione, export glTF e Toolkit Weight Paint completati** (Fasi 0–3): bootstrap installabile (pannello "FlexForge" nella Sidebar, `bl_info` 1.0.0, compatibilità **4.2+**), operatore bicipite `FLEXFORGE_OT_create_biceps`, utility pesi con operatore `FLEXFORGE_OT_limit_weights`, verifica deformazione con operatore `FLEXFORGE_OT_verify`, export glTF con operatore `FLEXFORGE_OT_export_gltf`, weight transfer con operatore `FLEXFORGE_OT_weight_transfer`, pulizia pesi con operatore `FLEXFORGE_OT_cleanup_weights` e mirror pesi con operatore `FLEXFORGE_OT_mirror_weights` (ottava classe registrata). Verificato con test headless (10 file) su Blender 4.2.23 e 5.3.0 e con smoke test ENGINE su Godot 4.7.1 headless: `ENGINE_CHECK_OK | engine=godot | file=flexforge_test.glb | bones=3 | seg_bones=3 | meshes=1 | anims=0 | max_len=0.00s`, exit 0; Unity smoke PASS (2026-11-21, editor 6000.6.10f1, `ENGINE_CHECK_OK | bones=3 | meshes=1 | clips=2 | max_len=1,21s`); Unreal fuori perimetro. Probe UI headless attiva (VERDICT_UI_OK 3/3 su 4.2 e 5.3); Gate GUI interattivo manuale ancora NOT CONFIGURED. **Traduzione inglese (2026-11-21):** codice, UI e messaggi dell'addon interamente in inglese; suite rieseguita 85/85 su 4.2.23 e 5.3.0, gate MCP+GUI inglese 5/5 `FINISHED`, Godot e Unity `ENGINE_CHECK_OK` rieseguiti; pacchetto inglese `dist/flexforge-1.0.0.zip` (18722 byte, sha256 `576d579d4e570c9f2013fd46f2d0e92cd0801157838eb5bdbe8de73f7694ff92`). **Pacchetto ricostituito (2026-11-21, Python di Blender 5.2): 13 file, 20291 byte, sha256 `5ccaf5197496cae1b404a968789c754a2fbde92c03b987f5f43f0ab6fba53a4c`; suite rieseguita su Blender 5.2 Windows: 11 file, 88/88** (muscle 9/9 con STRETCH_TO/bulge, weights_mirror 9/9 con `mirror_weights_spatial` asse X, probe UI 4/4 con `context_summary`). **Aggiornamento 2026-11-21:** nuovo modulo `flexforge/spatial_grid.py` (62 righe, griglia spaziale 3D O(N)); `flexforge/weight_nomi.py` esteso con alias multi-rig e infissi L/R (test `test_weight_nomi.py` 3/3); suite su Blender 5.2 Windows: 14 file, 134/134; `dist/flexforge-1.0.0.zip` ricreato con il Python di Blender 5.2: 17 file, 31656 byte, sha256 `f47fbd54855d6fe861634f6fd044d910b114539531e37a3e406bedef71c51091`.

## Idea (dal progettista, da trasformare in specifica)

FlexForge punta a essere un addon Blender per la costruzione e la deformazione di **sistemi muscolari / flessioni anatomiche** su rig di personaggi. Il perimetro esatto è **da concordare**: questa descrizione è il punto di partenza, non una specifica chiusa.

## Primo modulo — DEFINITO: bootstrap installabile

- metadata/manifest dell'addon (`bl_info` o manifest Extensions, scelta legata alla compatibilità Blender fissata);
- registrazione classi;
- pannello vuoto "FlexForge" nella Sidebar.

**Esplicitamente escluso dal primo modulo:** sistema muscolare, strumenti Weight Paint.
**Non fissato:** target engine — resta decisione aperta (la compatibilità Blender è chiusa: **4.2+**, con test su 4.2 e 5.3 **ESEGUITI il 2026-11-21**: `RISULTATO passati=6 falliti=0 totale=6` su entrambi. Il 5.3 è già disponibile al path `/home/pierofra/apps/blender-5.3/blender-5.3.0-linux-x64/`; l'host di sistema resta 5.2.2 LTS invariato).

## MVP — resto DA CONCORDARE

Nota: l'MVP muscolare della Fase 1 (bicipite + utility pesi) è realizzato e verificato; vedi `ROADMAP.md` per le fasi successive.

Oltre al bootstrap, il Minimum Viable Product completo non è ancora definito. Prima di scrivere i moduli successivi vanno decisi insieme (utente + architetto + coder) almeno:

- che cosa fa il primo pacchetto utilizzabile (un solo flusso end-to-end);
- su quali tipi di rig funziona (basi umanoidi? rig esistenti?);
- quali controlli sono esposti nella UI.

## Decisioni aperte

| Decisione | Stato |
| --- | --- |
| Modello muscolare (bones/bbone, shape keys, mesh deform, curve, GN) | Aperta |
| Export / engine target (solo Blender, glTF → Godot + Unity) | Chiusa — Fase 2, Unreal fuori perimetro per decisione (smoke Godot PASS; Unity NON ESEGUIBILE per licenza) |
| Toolkit Weight Paint (brush, transfer, auto-weights) | Chiusa — Fase 3: transfer + pulizia + mirror (brush/auto-weights esclusi) |

Nota: il primo modulo (bootstrap) non dipende da nessuna di queste decisioni e le esclude esplicitamente dal suo perimetro.

## Sorgente e specchio

- **Sorgente di verità (locale):** `/mnt/windows_c/Users/checc/Desktop/BLENDER ADDONS/FlexForge/`
- **Specchio (Google Drive):** `/home/pierofra/GoogleDrive/ADDON BLENDER/FlexForge/`
- Lo specchio è **solo copia di backup**: non si lavora mai direttamente sul Drive.

### Regola di sincronizzazione

Dopo **ogni avanzamento** (anche un solo documento modificato) si risincronizza la cartella FlexForge sul Drive **senza mai usare `--delete`**, per preservare ogni altro contenuto:

```bash
rsync -av "/mnt/windows_c/Users/checc/Desktop/BLENDER ADDONS/FlexForge/" \
      "/home/pierofra/GoogleDrive/ADDON BLENDER/FlexForge/"
```

Il `--delete` è vietato anche per evitare cancellazioni accidentali indotte da file temporanei.

## Stato

- Documenti presenti: `README.md`, `AGENTS.md`, `ROADMAP.md`, `COMPETIZIONE.md`. Nessun INDEX (non se ne crea uno fittizio).
- Moduli realizzati (Fasi 0–3): bootstrap installabile (`flexforge/__init__.py` 56 righe + `flexforge/ui.py` 47 righe, pannello `FLEXFORGE_PT_main` + `flexforge/blender_manifest.toml` 17 righe), bicipite (`flexforge/muscle.py` 234 righe, operatore `FLEXFORGE_OT_create_biceps`), utility pesi (`flexforge/weights.py` 180 righe, operatore `FLEXFORGE_OT_limit_weights`, terza classe registrata), verifica deformazione (`flexforge/verify.py` 181 righe, `valida_deformazione` + operatore `FLEXFORGE_OT_verify`, quarta classe registrata), export glTF (`flexforge/export_gltf.py` 214 righe + `flexforge/export_selezione.py` 69 righe, operatore `FLEXFORGE_OT_export_gltf`, quinta classe registrata: selezione esplicita mesh+armatura+helper, budget pesi applicato prima dell'export) e weight transfer (`flexforge/weight_transfer.py` 244 righe, operatore `FLEXFORGE_OT_weight_transfer`, sesta classe registrata), pulizia pesi (`flexforge/weights_cleanup.py` 138 righe, operatore `FLEXFORGE_OT_cleanup_weights`, settima classe) e mirror pesi (`flexforge/weights_mirror.py` 237 righe, operatore `FLEXFORGE_OT_mirror_weights`, ottava classe); helper condivisi `flexforge/weight_nomi.py` (94 righe, alias multi-rig + infissi L/R) e `flexforge/armatura.py` (16 righe); griglia spaziale `flexforge/spatial_grid.py` (62 righe, 3D O(N)); helper shape `flexforge/muscle_shape.py` (104 righe, nessun operatore registrato).
- Test (10 file) superati su Blender 4.2.23 e 5.3.0 il 2026-11-21, exit 0 su entrambi: cleanup `RISULTATO passati=9 falliti=0 totale=9`, mirror `RISULTATO passati=8 falliti=0 totale=8`, weight transfer `RISULTATO passati=10 falliti=0 totale=10`, export `RISULTATO passati=18 falliti=0 totale=18`, weights `RISULTATO passati=10 falliti=0 totale=10`, verify `RISULTATO passati=8 falliti=0 totale=8`, muscle `RISULTATO passati=8 falliti=0 totale=8`, bootstrap `RISULTATO passati=6 falliti=0 totale=6`; audit `preset-compatible` **SAFE** (validazione) e **PASS 6/6** (export); revisore con fix applicati (verify: EPS unico, controlli negativi, helper vuoto; export: fix applicati). Verifica: Test headless runner ed Engine smoke test (Godot) sono **Configurati**; smoke ENGINE su Godot 4.7.1 headless: `ENGINE_CHECK_OK | engine=godot | file=flexforge_test.glb | bones=3 | seg_bones=3 | meshes=1 | anims=0 | max_len=0.00s`, exit 0 (`.glb` reale di 3120 byte); Unity PASS (2026-11-21); Unreal fuori perimetro. Nota non bloccante: MeshOptimizer assente in Blender 5.2.2 (errore non bloccante). Smoke test GUI e Gate interattivo restano **NOT CONFIGURED**; probe UI headless attiva (`VERDICT_UI_OK | passati=3 falliti=0 totale=3` su 4.2 e 5.3); Gate GUI interattivo manualmente NOT CONFIGURED. **Riesecuzione su Blender 5.2 Windows (2026-11-21): 11 suite, 88/88** — muscle `RISULTATO passati=9 falliti=0 totale=9` (STRETCH_TO/bulge), mirror `RISULTATO passati=9 falliti=0 totale=9` (`mirror_weights_spatial` asse X), probe UI `RISULTATO passati=4 falliti=0 totale=4` (`context_summary`), altri conteggi invariati. **Estensione muscolo + pacchetto (2026-11-21): 3 nuovi moduli (`flexforge/muscle_presets.py` 184 righe, `flexforge/muscle_skinning.py` 192 righe, `flexforge/muscle_bake.py` 210 righe — classi 9/10/11: `FLEXFORGE_OT_create_muscle_preset`, `FLEXFORGE_OT_bind_muscles`, `FLEXFORGE_OT_bake_shape_keys`); suite su Blender 5.2 Windows: 14 file, 133/133 — `muscle_presets` `RISULTATO passati=15 falliti=0 totale=15`, `muscle_skinning` `RISULTATO passati=16 falliti=0 totale=16`, `muscle_bake` `RISULTATO passati=14 falliti=0 totale=14`, bootstrap 6/6 su 11 classi, ui_probe 4/4 su 10 operatori; `dist/flexforge-1.0.0.zip` ricreato con il Python di Blender 5.2: 16 file, 29295 byte, sha256 `89b4a39db80cf1635ee69d425fd20154f675f51f5e69b44bb5588695b7317415`.**
