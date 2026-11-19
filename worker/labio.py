"""labio.py - read lab output and reach the serpman lab modules in place (no copies)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SERPMAN_SRC = Path(os.getenv("SERPMAN_SRC", r"C:\Users\Keshav Sharma\Downloads\serpman"))


def lab_path() -> Path:
    """Put the serpman source folder on sys.path (idempotent) and return it."""
    if str(SERPMAN_SRC) not in sys.path:
        sys.path.insert(0, str(SERPMAN_SRC))
    return SERPMAN_SRC


def load_lab_json(path: Path) -> dict:
    """The CLI prints log lines (HH:MM:SS ...) before the JSON and PowerShell may add a BOM; skip both."""
    text = path.read_text(encoding="utf-8-sig")
    start = next((i for i, line in enumerate(text.splitlines()) if line.startswith("{")), None)
    if start is None:
        raise ValueError(f"{path}: no JSON object found")
    return json.loads("\n".join(text.splitlines()[start:]))
