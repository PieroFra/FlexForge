#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHECK_VERSIONS — confronta la versione tra le fonti del progetto.

Fonti confrontate (la versione di `bl_info` e' quella canonica):
  1. `flexforge/__init__.py` — chiave `"version"` di `bl_info`;
  2. `flexforge/blender_manifest.toml` — chiave `version`;
  3. `README.md` — deve citare la versione canonica;
  4. CHANGELOG (se presente nella radice: `CHANGELOG.md`, `CHANGELOG`
     o `HISTORY.md`) — la prima versione citata deve essere quella
     canonica; se il file non esiste, la fonte viene saltata.

Uso:
    python tools/scripts/check_versions.py [--root <radice>]

Output (unica riga di verdetto):
    VERSION_CHECK_OK version 1.0.2
    VERSION_CHECK_FAIL | expected=1.0.2 | source=<fonte> found=<versione>

Exit code: 0 = VERSION_CHECK_OK, 1 = VERSION_CHECK_FAIL, 2 = errore d'uso.
"""

import argparse
import os
import re
import sys


_VERSION_RE = re.compile(r"\b(\d+\.\d+\.\d+)\b")
_CHANGELOG_NAMES = ("CHANGELOG.md", "CHANGELOG", "HISTORY.md")


def _read_text(path):
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _bl_info_version(root):
    """Versione canonica da bl_info, es. "1.0.2". None se non trovata."""
    text = _read_text(os.path.join(root, "flexforge", "__init__.py"))
    if not text:
        return None
    match = re.search(r'"version"\s*:\s*\(([^)]+)\)', text)
    if not match:
        return None
    parts = [part.strip() for part in match.group(1).split(",") if part.strip()]
    if not parts or not all(part.isdigit() for part in parts):
        return None
    return ".".join(parts)


def _manifest_version(root):
    """Versione da blender_manifest.toml. None se non trovata."""
    text = _read_text(os.path.join(root, "flexforge", "blender_manifest.toml"))
    if not text:
        return None
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else None


def _readme_mentions(root, version):
    """True se README.md cita la versione canonica."""
    text = _read_text(os.path.join(root, "README.md"))
    if not text:
        return False
    return version in _VERSION_RE.findall(text)


def _changelog_version(root):
    """Prima versione citata nel CHANGELOG. None se assente o senza versioni."""
    text = None
    for name in _CHANGELOG_NAMES:
        text = _read_text(os.path.join(root, name))
        if text:
            break
    if not text:
        return None
    match = _VERSION_RE.search(text)
    return match.group(1) if match else None


def _check(root):
    """Lista di problemi (vuota = tutto allineato)."""
    canonical = _bl_info_version(root)
    if canonical is None:
        return ["source=bl_info found=missing"]
    problems = []
    found = _manifest_version(root)
    if found != canonical:
        problems.append("source=blender_manifest.toml found=%s" % (found or "missing"))
    if not _readme_mentions(root, canonical):
        problems.append("source=README.md found=missing")
    changelog = _changelog_version(root)
    if changelog is not None and changelog != canonical:
        problems.append("source=CHANGELOG found=%s" % changelog)
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="Confronta le versioni del progetto.")
    parser.add_argument("--root", default=None,
                        help="radice del progetto (default: due livelli sopra lo script)")
    args = parser.parse_args(argv)
    root = args.root or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    problems = _check(root)
    if problems:
        print("VERSION_CHECK_FAIL | expected=%s | %s"
              % (_bl_info_version(root) or "?", " | ".join(problems)))
        return 1
    print("VERSION_CHECK_OK version %s" % _bl_info_version(root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
