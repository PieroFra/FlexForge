# Piano di pubblicazione FlexForge 1.5.0

Regola d'oro: la pubblicazione parte solo dopo che il gate è verde sul pacchetto che si carica
(`ALL_GATES_OK | gates=4/4 | zip=flexforge-1.5.0.zip`), il pacchetto passa
`blender --command extension validate` e il README corrisponde al codice. Nessun trailer o
video di marketing: `_VIDEO_STUDIO/` resta fuori dal pacchetto e dal piano.

## Stato attuale

- Pacchetto: `dist/flexforge-1.5.0.zip`, 29 file, 64874 byte, sha256 `e05a873e49404f0314023acc909b4dc386ab518773b36d644a27ecb6fc28d5ba`.
- `extension validate` exit 0, gate 4/4, suite `RISULTATO passati=256 falliti=0 totale=256`.
- Prima pubblicazione: 1.2.0 già approvato su Blender Extensions.
- Materiale promozionale: `docs/PROMO.md` (bozza per Blender Artists e Reddit, in inglese).

## Fase 0 - materiale (prima di caricare)

1. Catturare la GUI reale con `blender-gui-capture`: screenshot sidebar IT/EN e una GIF breve
   del flusso *Detect rig -> Create full body* su un rig reale (SpaceDwarf o Mixamo). La GIF
   deve essere un render vero, non un mockup.
2. Aggiornare `docs/PROMO.md` da 1.0.0 a 1.5.0: aggiungere rig detection e "Create full body"
   tra le feature, aggiornare i riferimenti di versione.
3. Verificare che nessun link GitHub sia dentro il corpo del post Reddit (solo nel primo
   commento) e che il tag Blender Artists sia letto dal dizionario categoria 50.

## Fase 1 - Blender Extensions (canale ufficiale)

1. Caricare `dist/flexforge-1.5.0.zip` dalla pagina della versione 1.2.0
   (Upload new versione) con `publisher-extensions` (CDP su Chrome personale, login già attivo).
2. Compilare short description e changelog: "One-click full body preset on top of rig
   detection", flusso 5 passi, compatibilità 4.2+.
3. Nessuna permessa richiesta (nessun `[permissions] network`); nessun segreto nel pacchetto.
4. Attendere l'approvazione del reviewer. La versione 1.2.0 è già approvata: la 1.5.0 deve
   passare la stessa revisione, non una nuova autorizzazione dell'estensione.
5. Verifica post-upload: pagina pubblica, versione 1.5.0 visibile, zip scaricabile validato
   di nuovo con `extension validate`.

## Fase 2 - Blender Artists (forum)

1. Categoria 50 (Released Scripts and Themes), tag valido dal dizionario, mai `add-on` o
   `rigging`.
2. Titolo: `FlexForge 1.5.0: muscle detection and one-click full body preset on character rigs`.
3. Body: cosa fa (detect + full body + workflow muscolare + weights + budget + export), test
   su rig reali (Mixamo, Auto-Rig Pro SpaceDwarf), dove segnalare (issue GitHub).
4. Allegare la GIF della Fase 0; nessun link GitHub nel body se il canale lo richiede.

## Fase 3 - Reddit r/blender

1. Flair: Free Tools & Assets.
2. Titolo: `FlexForge 1.5.0 - detects your rig and creates every muscle preset in one click`.
3. Body: senza `https://`, senza claim non misurati; link solo nel primo commento.
4. Primo commento subito dopo il post: repo e issue tracker.
5. Nessun video: se serve un video, resta in `_VIDEO_STUDIO/` e non parte del pacchetto.

## Criterio di chiusura

Ogni canale si considera pubblicato solo con:

- URL verificato a mano (pagina carica, versione 1.5.0, download funziona);
- screenshot/link salvato in `docs/` o in `%TEMP%` per il registro della release;
- AGENTS.md aggiornato con la riga della pubblicazione e il gate ripreso dopo la release.

Ordine obbligatorio: Extensions -> Blender Artists -> Reddit. Non pubblicare su Reddit prima che
la versione sia visibile su Extensions, così il link nel primo commento funziona.