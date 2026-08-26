"""Matriz de assessment CEFR (A1–B2 × 4 macro-destrezas).

Carga y valida `curriculum/cefr_matrix.json`: umbrales multidimensionales por
nivel y destreza (dominio, confianza, evidencia) más los mínimos de evidencia de
transferencia/novedad exigidos en B1/B2. Es **contenido**, no lógica: los valores
viven solo en el JSON y aquí solo se cargan (Pydantic) y se consultan.

Solo cubre las 4 macro-destrezas (`listening`, `speaking`, `reading`, `writing`).
`grammar`/`vocabulary`/`pronunciation` y los niveles C1/C2 quedan fuera: para ellos
`requirements_for` devuelve `None` y `services.adaptive.readiness` usa el fallback
plano (`READINESS_MINIMUMS`).
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from services.curriculum import CURRICULUM_DIR


class CefrSkillRequirement(BaseModel):
    minimum_mastery: float
    minimum_confidence: float
    minimum_evidence: int
    transfer_required: int = 0
    novel_required: int = 0


class CefrLevelRequirements(BaseModel):
    level: str
    skills: dict[str, CefrSkillRequirement]


class CefrMatrix(BaseModel):
    version: str
    levels: dict[str, CefrLevelRequirements]


# Cache a nivel de módulo: el contenido es estático durante el proceso.
_MATRIX_CACHE: CefrMatrix | None = None


def load_matrix() -> CefrMatrix:
    """Carga y valida la matriz CEFR (cacheada a nivel de módulo)."""
    global _MATRIX_CACHE
    if _MATRIX_CACHE is None:
        path = CURRICULUM_DIR / "cefr_matrix.json"
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        levels = {
            level_id: CefrLevelRequirements(level=level_id, skills=skills)
            for level_id, skills in data["levels"].items()
        }
        _MATRIX_CACHE = CefrMatrix(version=data["version"], levels=levels)
    return _MATRIX_CACHE


def requirements_for(level_id: str, skill: str) -> CefrSkillRequirement | None:
    """Requisitos de una destreza en un nivel, o `None` si no están en la matriz."""
    level = load_matrix().levels.get(level_id)
    if level is None:
        return None
    return level.skills.get(skill)
