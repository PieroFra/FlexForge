# Sincronizzazione `BLENDER ADDONS` (`C:\Users\checc\Desktop\BLENDER ADDONS\FlexForge`)

Questo documento descrive come mantenere allineata la cartella locale Windows `C:\Users\checc\Desktop\BLENDER ADDONS\FlexForge` con il repository `PieroFra/FlexForge`, rispettando rigorosamente `.gitignore`.

> **Nota ambiente:** la cartella `C:\Users\checc\Desktop\BLENDER ADDONS` risiede sul PC Windows dell'utente e **non** è montata nella VM Linux remota. Inoltre, il vecchio mirror Google Drive (`FlexForge`, ID `1h9JOJw6JednTHI_VEiXRRU3zLaTKqnae`) è fermo alla `1.0.2` (2026-11-21) e non va usato come sorgente.

## Cosa è tracciato vs cosa è ignorato (`.gitignore`)

| Percorso | Stato Git | Note |
|---|---|---|
| `flexforge/` (30 file: 29 `.py` + `blender_manifest.toml`) | **Tracciato** | Codice runtime dell'addon |
| `tests/` (22 suite `test_*.py`) + `tools/tests/` | **Tracciato** | Suite headless |
| `tools/scripts/`, `tools/verify.config.psd1` | **Tracciato** | Gate, audit, check versioni, E2E Godot |
| `docs/`, `README.md`, `ROADMAP.md`, `AGENTS.md`, `.gitignore` | **Tracciato** | Documentazione, roadmap e configurazione |
| `dist/` (`flexforge-*.zip`) | **Ignorato** | Archivi buildati: non committare mai (`git add -f` vietato) |
| `.agents/` | **Ignorato** | Metadati interni teamwork: mai committare |
| `__pycache__/`, `*.pyc`, `*.pyo` | **Ignorato** | Bytecode Python |
| `tools/verdict.txt`, `tools/metrics.jsonl`, `tools/gate.lock`, `tools/tests/test_out.txt` | **Ignorato** | Artefatti generati a runtime dai gate |
| `_esperimenti/`, `.opencode/`, `_VIDEO_STUDIO/` | **Ignorato** | Cartelle locali di lavoro/studio |

## Procedura consigliata su Windows (Git)

Dalla cartella del repository su Windows:

```powershell
cd "C:\Users\checc\Desktop\BLENDER ADDONS\FlexForge"
git status --ignored --short
git pull origin main
```

Git rispetta automaticamente `.gitignore`: `dist\`, `.agents\`, `__pycache__\` e i file runtime di `tools\` restano ignorati e non vengono mai inclusi nei commit.

## Verifica pre-commit obbligatoria (Windows PowerShell)

Prima di qualsiasi `git commit` o `git push` dalla cartella `BLENDER ADDONS\FlexForge`:

```powershell
git status --short
git check-ignore -v dist/flexforge-1.6.1.zip .agents/ tools/verdict.txt __pycache__/
```

Verificare che `dist/`, `.agents/`, `__pycache__/` e `tools/verdict.txt` non compaiano mai in `git diff --cached --name-only`.

## Copia manuale alternativa (senza sovrascrivere file ignorati)

Se si sincronizza da un'altra cartella locale su Windows invece di usare `git pull`:

```powershell
robocopy "<SORGENTE_REPO>" "C:\Users\checc\Desktop\BLENDER ADDONS\FlexForge" /E /XD .git __pycache__ dist .agents _esperimenti _VIDEO_STUDIO .opencode /XF verdict.txt metrics.jsonl gate.lock test_out.txt *.pyc *.pyo
```

## Ricostruzione dello `.zip` locale su Windows

Per generare `dist\flexforge-1.6.1.zip` in locale dentro `BLENDER ADDONS\FlexForge` (usando il Python di Blender 5.2, senza `__pycache__`):

```powershell
& "<BLENDER_52>\5.2\python\bin\python.exe" -c "import pathlib, zipfile; root=pathlib.Path('flexforge'); out=pathlib.Path('dist/flexforge-1.6.1.zip'); out.parent.mkdir(exist_ok=True); z=zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED); [z.write(p,p.as_posix()) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')]; z.close()"
```
