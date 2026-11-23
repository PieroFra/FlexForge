#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HARDCODED_PATHS -- scanner dei percorsi assoluti hardcoded.

Scansiona i file `.py` e `.ps1` del repository (esclusi `.git/`,
`__pycache__/`, `dist/`, `_esperimenti/`, `.opencode/` e questo script
stesso) alla ricerca di
percorsi assoluti hardcoded: lettere di unita' Windows (`C:\\`,
`C:/`), path UNC (`\\\\server\\share`) e percorsi POSIX assoluti
tra virgolette o con radici note (`/home/`, `/Users/`, `/tmp/`,
`/usr/`, ecc.). La riga di shebang (`#!...`) e' ignorata.
L'allowlist EXCLUDED copre solo le fixture `/tmp/` nei test e i
candidati OS in `tools/scripts/find_blender.ps1`; tutto il resto
viene segnalato.

Uso:
    python tools/scripts/hardcoded_paths.py [--root <radice>]

Output (riga di verdetto + elenco in caso di fallimento):
    HARDCODED_PATH_OK
    HARDCODED_PATH_FAIL | count=N
    <file>:<riga>: <contenuto>

Exit code: 0 = HARDCODED_PATH_OK, 1 = HARDCODED_PATH_FAIL,
2 = errore d'uso.
"""

import argparse
import os
import re
import sys


_SKIP_DIRS = frozenset((".git", "__pycache__", "dist", ".venv", "venv",
                        "_esperimenti", ".opencode"))
_SKIP_FILES = frozenset(("hardcoded_paths.py",))
_EXTENSIONS = (".py", ".ps1")

# Allowlist mirata EXCLUDED: (prefisso file, frammenti consentiti).
# - fixture /tmp nei test: gli stub dei test usano "/tmp/..." (mai path reale)
# - candidati OS in tools/scripts/find_blender.ps1: installazioni standard
#   Linux/macOS elencate come candidati (anche nel commento di testa).
EXCLUDED = (
    ("tests/", ("/tmp/",)),
    ("tools/scripts/find_blender.ps1", ("/opt", "/usr/", "/Applications/")),
)

_WIN_DRIVE_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]")
_UNC_RE = re.compile(r"\\\\[^\s\"']+")
_POSIX_KNOWN_RE = re.compile(
    r"(?<![\w.:/\\-])/(?:home|Users|tmp|var|etc|opt|usr|root|mnt|media|"
    r"Volumes|private|bin|sbin|lib|dev)/")
_POSIX_QUOTED_RE = re.compile(
    r"(?<![/:\w])[\"']/(?!/)(?:[^\s\"']+)[\"']")
_PATTERNS = (_WIN_DRIVE_RE, _UNC_RE, _POSIX_KNOWN_RE, _POSIX_QUOTED_RE)


def _read_lines(path):
    """Righe del file, [] se non leggibile."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read().splitlines()
    except OSError:
        return []


def _is_excluded(relative, line):
    """True se la riga e' coperta dall'allowlist EXCLUDED."""
    for prefix, fragments in EXCLUDED:
        if relative.startswith(prefix):
            for fragment in fragments:
                if fragment in line:
                    return True
    return False


def _is_hardcoded(line, lineno, relative=None):
    """True se la riga contiene un percorso assoluto hardcoded."""
    if lineno == 1 and line.lstrip().startswith("#!"):
        return False
    if relative is not None and _is_excluded(relative, line):
        return False
    for pattern in _PATTERNS:
        if pattern.search(line):
            return True
    return False


def _iter_files(root):
    """Percorsi relativi dei file `.py`/`.ps1` da scansionare."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in _SKIP_DIRS]
        for name in filenames:
            if name in _SKIP_FILES:
                continue
            if os.path.splitext(name)[1].lower() not in _EXTENSIONS:
                continue
            full = os.path.join(dirpath, name)
            found.append(os.path.relpath(full, root))
    return sorted(found)


def _scan(root):
    """Lista di hit `file:riga: contenuto` (vuota = nessun path assoluto)."""
    hits = []
    for relative in _iter_files(root):
        full = os.path.join(root, relative)
        shown = relative.replace(os.sep, "/")
        for lineno, line in enumerate(_read_lines(full), start=1):
            if _is_hardcoded(line, lineno, shown):
                hits.append("%s:%d: %s" % (shown, lineno, line.strip()))
    return hits


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Scanner dei percorsi assoluti hardcoded su .py e .ps1.")
    parser.add_argument("--root", default=None,
                        help="radice del progetto (default: tre livelli sopra lo script)")
    args = parser.parse_args(argv)
    root = args.root or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if not os.path.isdir(root):
        print("HARDCODED_PATH_FAIL | reason=BAD_ROOT | root=%s" % root)
        return 2
    hits = _scan(root)
    if hits:
        print("HARDCODED_PATH_FAIL | count=%d" % len(hits))
        for hit in hits:
            print(hit)
        return 1
    print("HARDCODED_PATH_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
