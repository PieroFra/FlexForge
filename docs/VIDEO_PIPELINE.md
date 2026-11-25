# FlexForge — Pipeline video (piano operativo, NON un risultato)

**Versione doc:** 2026-11-25 · **Addon:** FlexForge 1.5.0 · **Repo:** `C:\Users\checc\Desktop\BLENDER ADDONS\FlexForge`

## 1. Scopo e stato

Questo file documenta la **pipeline video verificata a livello di strumenti** per
FlexForge: quali materiali servono, quali comandi esatti eseguire, come si verifica
in modo deterministico che un output sia sano, quali rischi esistono e cosa non si
deve fare.

**Vincolo utente (rispettato alla lettera): "fermati, non fare nessun trailer".**
Quindi:

- **Nessun trailer è stato prodotto.**
- **Nessun video, GIF o screenshot è stato renderizzato o registrato.**
- Questo documento è un **piano operativo**, non la prova di un risultato.

La pipeline è verificata solo per presenza e funzionamento degli strumenti (ffmpeg
9.0.2, Blender 5.2, script `gif_check.py`/`compose_gif.py`). Il montaggio vero e
proprio resta da fare **solo quando l'utente lo autorizzerà esplicitamente**.

## 2. Strumenti verificati sul PC (stato reale)

| Strumento | Stato | Note |
| --- | --- | --- |
| `ffmpeg` | **OK** — `ffmpeg version 9.0.2-full_build-www.gyan.dev` | x264, palettegen/paletteuse, gdigrab disponibili |
| Blender 5.2 | **OK** — `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe` (112.975.320 byte) | junction `C:\flex52` → stessa installazione, `blender.exe` presente |
| `C:\Users\checc\.agents\scripts\gif_check.py` | **OK** (20.747 byte) | gate deterministico GIF |
| `C:\Users\checc\.agents\scripts\compose_gif.py` | **OK** (3.165 byte) | composizione GIF da PNG |
| Blender "4.5" | **NON USARE** — `blender.exe` **assente** | installazione incompleta (solo python/scripts) |

Python per gli script: `C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe`.

## 3. Percorso A — catture dentro Blender (`blender-gui-capture`)

Serve per screenshot PNG, crop della Sidebar UI (IT/EN) e GIF del flusso reale
**"Detect rig → Create full body"** generate in modo deterministico dentro Blender,
senza splash screen.

### 3.1 Avvio Blender (senza splash del lupo)

```powershell
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --factory-startup --no-window-focus --python "%TEMP%\opencode\capture_gui.py"
```

Dentro lo script, nel `timer1` (`first_interval=0.8`), elimina splash e scena:

```python
bpy.context.preferences.view.show_splash = False
bpy.ops.wm.read_homefile(use_empty=True)   # chiude lo splash modale e svuota la scena
```

`--factory-startup` → preferenze pulite; `--no-window-focus` → niente splash in primo piano.

### 3.2 Inquadratura camera esatta (senza `view_selected`) e Sidebar N

```python
r3d = space.region_3d
r3d.view_perspective = 'ORTHO'
r3d.view_location = Vector((0.35, 0.0, 1.1))   # centro del rig + offset X per non finire sotto la Sidebar N
r3d.view_distance = 2.6                         # zoom esatto
r3d.view_rotation = Euler((math.radians(78), 0.0, math.radians(25))).to_quaternion()

space.show_region_ui = True
bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=2)  # Blender popola le categorie dei pannelli
ui_region = next(r for r in area.regions if r.type == 'UI')
ui_region.active_panel_category = "<Nome Tab>"                # apre il tab dell'addon
bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=2)
```

### 3.3 Catturare l'area View3D + Sidebar

```python
with bpy.context.temp_override(window=w, area=a, region=win_region):
    bpy.ops.screen.screenshot_area(filepath="...")
```

`screenshot_area` cattura l'area `VIEW_3D` comprensiva della Sidebar `N`, escludendo
topbar, timeline, outliner e properties. Per il solo crop della Sidebar si ritaglia la
fascia destra (`x0 = width - ui_region.width`).

### 3.4 Comporre la GIF dai frame PNG già catturati

```powershell
$py = "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe"
$cmp = Join-Path $env:USERPROFILE "..agents\\scripts\compose_gif.py"
& $py $cmp frame-it.png frame-en.png frame-it.png frame-en.png -o docs\demo-ui.gif -d 1200 -w 1024
```

- Argomenti: uno o più PNG (o cartelle), `-o` output, `-d` durata per frame in ms (default 1200),
  `-w` larghezza massima (default 1024).
- Servono almeno 4 frame: con 2 soli stati (IT, EN) la sequenza si ripete `IT, EN, IT, EN`
  per garantire il ciclo, altrimenti `gif_check.py` chiude con `frame=2 (min 4)`.

**Uso FlexForge:** screenshot Sidebar IT/EN + GIF del flusso "Detect rig → Create full body".

## 4. Percorso B — registrazione GUI reale multi-finestra (`obs-screen-capture`)

Serve quando il flusso va mostrato insieme ad **altre finestre** (es. Blender + RizomUV
Live Link / Export-Import). gdigrab NON cattura finestre minimizzate o coperte: tieni
tutto visibile e in primo piano per tutta la durata.

### 4.1 OBS Studio (sessione guidata, 1080p60, multi-monitor)

```powershell
Test-Path "C:\Program Files\obs-studio\bin\64bit\obs64.exe"
Start-Process "C:\Program Files\obs-studio\bin\64bit\obs64.exe" -ArgumentList '--startrecording','--minimize-to-tray'
```

Stop: hotkey in OBS (Settings > Hotkeys, es. **F9**) o WebSocket (porta 4455). Output:
`%USERPROFILE%\Videos\OBS Studio\*.mkv`; se OBS crasha ripara senza ricodifica con
`ffmpeg -y -i ripresa.mkv -c copy ripresa.mp4`.

### 4.2 FFmpeg gdigrab (one-shot pilotato, zero config)

```powershell
Get-Command ffmpeg
ffmpeg -hide_banner -y -f gdigrab -framerate 30 -draw_mouse 1 -i desktop -t 90 -c:v libx264 -preset ultrafast -crf 18 -an raw.mp4
ffmpeg -hide_banner -y -f gdigrab -framerate 30 -draw_mouse 1 -i title="Blender*" -t 90 -c:v libx264 -preset ultrafast -crf 18 -an raw.mp4
```

Monitor secondario (offset prima di `-i desktop`):

```powershell
ffmpeg -hide_banner -y -f gdigrab -framerate 30 -offset_x 1920 -offset_y 0 -video_size 1920x1080 -i desktop -t 90 -c:v libx264 -preset ultrafast -crf 18 -an raw.mp4
```

### 4.3 Rimux `.mkv` → `.mp4` senza ricodifica

```powershell
ffmpeg -y -i ripresa.mkv -c copy ripresa.mp4
```

### 4.4 Preparazione pulita prima del rec (checklist)

UI Blender in inglese (`use_translate_interface = False`); zero dati personali a schermo,
Focus Assist e notifiche disattivate; Sidebar N sul tab dell'addon; RizomUV (o altra
finestra) avviato PRIMA del rec e affiancato (Win+Left / Win+Right); cursore visibile
(`-draw_mouse 1` o cursore normale in OBS).

## 5. Post-produzione ffmpeg

### 5.1 MP4 per i canali social — 1920x1080 @ 60fps

```powershell
ffmpeg -y -i raw.mp4 -vf "scale=1920:1080:flags=lanczos" -c:v libx264 -crf 14 -preset slow -pix_fmt yuv420p -movflags +faststart -an out-1080p60.mp4
```

Controllo geometria/codec:

```powershell
ffprobe -v error -show_entries stream=codec_name,width,height,pix_fmt,r_frame_rate -of default=nw=1 out-1080p60.mp4
```

### 5.2 GIF sotto i 10 MB — two-pass con palette

```powershell
ffmpeg -y -i out.mp4 -vf "fps=12,scale=1280:720:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=256:stats_mode=full[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3" docs\demo.gif
```

Variante skill (palette in due passaggi, 960px, fps 20):

```powershell
ffmpeg -y -i out.mp4 -vf "fps=20,scale=960:-2:flags=lanczos,palettegen=stats_mode=diff" palette.png
ffmpeg -y -i out.mp4 -i palette.png -lavfi "fps=20,scale=960:-2:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" demo.gif
```

Se sfora i 10 MB riduci nell'ordine: risoluzione → fps → durata (`-t 20`) → GIF spezzata in due file.

## 6. Verifiche deterministiche (mai consegnare senza)

Il verdetto lo dà lo script, non l'occhio.

### 6.1 Gate GIF — `gif_check.py`

```powershell
$py = "C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe"
$chk = Join-Path $env:USERPROFILE "..agents\\scripts\gif_check.py"
& $py $chk docs\demo.gif
```

Riga attesa (`exit 0`):

```
GIF_CHECK_OK | file=demo.gif | frame=48 | dist=41 | durata=6.40s | dim=960x540 | peso=4.31MB | loop=infinito | std_primo=41.2 | std_ultimo=38.7
```

Se fallisce: `GIF_CHECK_FAIL | ...` con il motivo, chiuso da `GIF_CHECK_SUMMARY | falliti=N su M` e `exit 1`.

Default: `--max-mb 10 --min-frames 4 --min-duration 1.0 --min-std 8.0`. Rifiuta:
firma GIF non valida (PNG rinominato), file assente, `frame=1 (min 4)`, frame tutti
identici, `durata=0.00s`, loop assente, primo/ultimo frame piatto/nero, `peso > 10 MB`.
Self-test dello script (se un verdetto sembra sbagliato, prima si sospetta lo script):
`& $py $chk --selftest` → atteso `GIF_SELFTEST_OK | casi=13`.

### 6.2 Gate MP4 — durata e geometria

```powershell
ffprobe -v error -show_entries format=duration -of csv=p=0 out.mp4
ffprobe -v error -show_entries format=duration,size -of csv=p=0 out.mp4
```

### 6.3 Verifica visiva (dopo il gate, mai al posto suo)

```powershell
$dur = [double](ffprobe -v error -show_entries format=duration -of csv=p=0 .\out.mp4)
$s = 0.5; $m = [math]::Round($dur / 2, 1); $e = [math]::Round($dur - 0.5, 1)
ffmpeg -hide_banner -y -ss $s -i out.mp4 -frames:v 1 chk_1.png
ffmpeg -hide_banner -y -ss $m -i out.mp4 -frames:v 1 chk_2.png
ffmpeg -hide_banner -y -ss $e -i out.mp4 -frames:v 1 chk_3.png
```

Controlli sui 3 frame: nessuno schermo nero/frame congelato; finestre attese visibili;
nessun dato personale; crop centrato senza taskbar.

## 7. Materiali da produrre (checklist per i tre canali)

Testi e short description: vedi **`docs/PROMO.md`**; ordine di pubblicazione e
workflow a 3 fasi: vedi **`docs/PUBLICATION_PLAN.md`**.

| Canale | Materiali necessari | Note |
| --- | --- | --- |
| **Blender Extensions** | zip `dist/flexforge-1.5.0.zip` (64.874 byte) + screenshot Sidebar + GIF demo | ZIP già validato (`extension validate` exit 0) |
| **Blender Artists** (categoria **50**) | GIF/MP4 demo + breve descrizione (da PROMO.md) | upload media via CDP |
| **Reddit r/blender** | MP4 ≤ 15 MB (o GIF < 10 MB) + titolo senza link | anti-spam: niente link nel corpo |

Naming: gli script di composizione si chiamano sempre `compose_*.py` (mai `build_*.py`).

## 8. Rischi e trappole note (verificate)

- **Splash screen del lupo:** si elimina con `--factory-startup --no-window-focus` +
  `read_homefile(use_empty=True)` nel `timer1`.
- **Output PowerShell rediretto è UTF-16 con BOM:** scrivi i file con
  `[IO.File]::WriteAllText($path, $code, [Text.UTF8Encoding]::new($false))`.
- **In `cmd` non usare `;`:** i comandi si concatenano con `&`.
- **`cmd` tronca i comandi multi-riga:** usa script `.py`, non `py -3 -c` multi-riga.
- **exe con path quotato non parte da `cmd`:** usa la junction `C:\flex52` o `cd /d` nel percorso.
- **Serve una scena riggata reale** (rig Mixamo o SpaceDwarf) per mostrare il flusso
  "Detect rig → Create full body": su una scena vuota non c'è nulla da dimostrare.
- **gdigrab non cattura finestre coperte/minimizzate;** DPI scaling 125%/150% può
  sbilanciare il crop (verifica sempre col frame).
- **`.resize((dw,dh))` non uniforme è vietato:** schiaccia il soggetto 3D; si usa
  sempre `scale_x == scale_y` al 100%.

## 9. Cosa NON fare

- **Nessun trailer, nessun video di marketing promozionale** finché l'utente non lo
  autorizza esplicitamente (vincolo attuale: "fermati, non fare nessun trailer").
- **Non pubblicare materiale** senza gate verde sul pacchetto di release
  (`ALL_GATES_OK`, `ZIP_AUDIT_OK`, suite verde).
- **Non usare "Blender 4.5"** : installazione incompleta (`blender.exe` assente).
- **Non consegnare una GIF** senza la riga `GIF_CHECK_OK` verbatim.
- **Non usare `build_*.py`** per gli script di composizione.
- **Non dichiarare chiuso un gate** senza aver letto l'exit code e la riga di verdetto reale.
