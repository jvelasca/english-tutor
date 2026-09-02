"""Loader de los datasets dorados de auditoría (V3.0, post-freeze).

Los fixtures viven como JSON versionado en `tests/golden/<area>/`. Su función:

- proteger la calibración auditada: si una edición de contenido o de motor hace
  que un ítem/nivel se salga de la banda que se verificó en la auditoría, el
  test golden correspondiente falla y obliga a re-auditar (no a ignorar).
- documentar el "golden": las muestras representativas por nivel y los casos de
  frontera que la auditoría A–E fijó con veredicto.

Convención: editar un golden solo es legítimo como resultado de una re-auditoría
explícita (comentario en el CHANGELOG o en el dossier `docs/audit/`).
"""
from __future__ import annotations

import json
from pathlib import Path

GOLDEN_DIR = Path(__file__).resolve().parent


def load_json(*parts: str):
    """Carga un fixture JSON relativo a `tests/golden/` (p. ej. listening/bands)."""
    path = GOLDEN_DIR.joinpath(*parts)
    if path.suffix != ".json":
        path = path.with_suffix(".json")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def corpus_item(item_id: str) -> dict | None:
    """Devuelve un ítem del banco completo de listening por id."""
    from services.listening import QUESTION_BANK

    for q in QUESTION_BANK:
        if q["id"] == item_id:
            return q
    return None


def corpus_items_by_level(level: str) -> list[dict]:
    from services.listening import QUESTION_BANK

    return [q for q in QUESTION_BANK if q["id"].startswith("c") and q["level"] == level]


def level(level_id: str):
    from services.curriculum import load_level

    return load_level(level_id)


def objective(level_id: str, objective_id: str):
    lv = level(level_id)
    for obj in lv.objectives():
        if obj.id == objective_id:
            return obj
    return None
