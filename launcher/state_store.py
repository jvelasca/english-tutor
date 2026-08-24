"""Persistencia del estado visual del launcher (JSON, sin dependencias externas).

Guarda el tamaño y la posición de la ventana, la posición del divisor entre las
dos columnas y qué secciones están expandidas o colapsadas, para restaurarlas al
volver a abrir el launcher. Si el archivo no existe o está corrupto, se usan
valores por defecto; si no se puede escribir, se ignora silenciosamente (el
launcher funciona igual sin persistencia).
"""
from __future__ import annotations

import json
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parent / "state.json"

DEFAULTS: dict = {
    "window": {"width": 1160, "height": 800, "x": None, "y": None},
    "sash": 580,
    "sections": {},
}


def load_state(path: Path | None = None) -> dict:
    """Carga el estado guardado; si falta o es inválido, devuelve los defaults."""
    path = path or STATE_PATH
    state: dict = {
        "window": dict(DEFAULTS["window"]),
        "sash": DEFAULTS["sash"],
        "sections": dict(DEFAULTS["sections"]),
    }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return state
    if not isinstance(data, dict):
        return state

    win = data.get("window")
    if isinstance(win, dict):
        for key in ("width", "height"):
            val = win.get(key)
            if isinstance(val, int) and val > 0:
                state["window"][key] = val
        for key in ("x", "y"):
            val = win.get(key)
            if isinstance(val, int):
                state["window"][key] = val

    sash = data.get("sash")
    if isinstance(sash, int) and sash > 0:
        state["sash"] = sash

    sections = data.get("sections")
    if isinstance(sections, dict):
        for key, val in sections.items():
            if isinstance(key, str) and isinstance(val, bool):
                state["sections"][key] = val

    return state


def save_state(state: dict, path: Path | None = None) -> None:
    """Guarda el estado en disco (JSON indentado); ignora errores de escritura."""
    path = path or STATE_PATH
    try:
        path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
