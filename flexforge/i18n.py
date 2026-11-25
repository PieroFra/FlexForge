# FlexForge — Italian translation catalogue for the addon UI.
# Code, UI and messages stay English: this module only registers the it_IT
# strings through bpy.app.translations, without adding any class.

import bpy

# Panel and layout strings drawn by flexforge/ui.py.
_UI_STRINGS = {
    "FlexForge - muscles and weights": "FlexForge - muscoli e pesi",
    "Muscle Workflow": "Flusso di lavoro muscoli",
    "Muscle Bulge Controls": "Controlli rigonfiamento muscolo",
    "No baked muscles on active mesh": "Nessun muscolo cotto sulla mesh attiva",
    "Weight Paint Toolkit": "Strumenti di weight paint",
    "Validation & Export": "Validazione ed esportazione",
    "Quick Single Muscle": "Muscolo singolo rapido",
    "Muscles: select a mesh": "Muscoli: seleziona una mesh",
    "Muscles: %d groups | %d baked keys": "Muscoli: %d gruppi | %d chiavi cotte",
    "Active: none": "Attivo: nessuno",
    "Active: %s (ARMATURE, %d bones)": "Attivo: %s (ARMATURA, %d ossa)",
    "Active: %s (MESH, %d groups)": "Attivo: %s (MESH, %d gruppi)",
    "Active: %s (%s)": "Attivo: %s (%s)",
}

# Operator buttons: used both as layout text ("*") and as operator label.
_OPERATOR_LABELS = {
    "Create muscle preset": "Crea preset muscolo",
    "Create biceps": "Crea bicipite",
    "Create biceps (quick)": "Crea bicipite (rapido)",
    "Bind muscles": "Collega muscoli",
    "Bake shape keys": "Cottura shape key",
    "Bake skin bounce": "Cottura rimbalzo pelle",
    "Clear muscles": "Pulisci muscoli",
    "Transfer weights": "Trasferisci pesi",
    "Clean weights": "Pulisci pesi",
    "Mirror weights": "Specchia pesi",
    "Limit weights": "Limita pesi",
    "Verify deformation": "Verifica deformazione",
    "Apply engine budget": "Applica budget motore",
    "Detect rig": "Rileva rig",
    "Create full body": "Crea corpo intero",
    "Export glTF": "Esporta glTF",
}

# Property names shown in the operator panels and in the redo panel.
_PROPERTY_NAMES = {
    "Preset": "Preset",
    "All available": "Tutti disponibili",
    "Custom": "Personalizzato",
    "Custom name": "Nome personalizzato",
    "Origin bone": "Osso di origine",
    "Insertion bone": "Osso di inserzione",
    "Mirror L/R": "Specchia L/R",
    "Invert L/R": "Inverti L/R",
    "Segments": "Segmenti",
    "Bulge": "Rigonfiamento",
    "Radius": "Raggio",
    "Intensity": "Intensità",
    "Displacement": "Spostamento",
    "Max displacement ratio": "Rapporto spostamento massimo",
    "Strip muscle weights": "Rimuovi pesi muscolo",
    "Drive by pose": "Guida dalla posa",
    "Anatomical taper": "Rastrematura anatomica",
    "Directional bias": "Inclinazione direzionale",
    "Smooth": "Levigatura",
    "Stiffness": "Rigidità",
    "Damping": "Smorzamento",
    "Overshoot limit": "Limite di superamento",
    "Max influences": "Influenze massime",
    "Max distance": "Distanza massima",
    "Path": "Percorso",
    "Export path": "Percorso di esportazione",
    "Threshold": "Soglia",
}


def _catalogue():
    """Build the it_IT catalogue from the three string tables above."""
    entries = {}
    for table in (_UI_STRINGS, _PROPERTY_NAMES):
        for text, translated in table.items():
            entries[("*", text)] = translated
    for text, translated in _OPERATOR_LABELS.items():
        entries[("*", text)] = translated
        entries[("Operator", text)] = translated
    return entries


TRANSLATIONS = {"it_IT": _catalogue()}

_MODULE_NAME = __package__ or "flexforge"


def register_translations():
    """Register the it_IT catalogue, ignoring an already registered one."""
    try:
        bpy.app.translations.register(_MODULE_NAME, TRANSLATIONS)
    except ValueError:
        pass


def unregister_translations():
    """Unregister the it_IT catalogue, ignoring one that is not registered."""
    try:
        bpy.app.translations.unregister(_MODULE_NAME)
    except ValueError:
        pass
