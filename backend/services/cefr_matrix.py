"""Matriz de requisitos CEFR (A1–C2 × 8 destrezas).

Carga y valida `curriculum/cefr_matrix.json`: umbrales multidimensionales por
nivel y destreza (dominio, confianza, evidencia) más los mínimos de evidencia de
transferencia/novedad exigidos a partir de B1. Es **contenido**, no lógica: los
valores viven solo en el JSON y aquí solo se cargan (Pydantic) y se consultan.

Cubre las 8 destrezas de la Constitución §7 (`vocabulary`, `grammar`,
`listening`, `speaking`, `interaction`, `reading`, `writing`, `mediation`) en
los 6 niveles A1–C2. `pronunciation` queda fuera a propósito: es componente de
Speaking y conserva su mínimo plano (`READINESS_MINIMUMS`, `services/adaptive`),
como define la sección 7 de la constitución. Para las destrezas sin calibración
per-nivel (`vocabulary`/`grammar`/`interaction`/`mediation`) la fila declara el
mismo suelo que su fallback plano histórico, de modo que la matriz es la fuente
única y completa de requisitos (H4) sin inventar escalados no calibrados; los
escalados por nivel de listening/speaking/reading/writing (A1–B2 calibrados en
V2.x) se extrapolan con la misma pauta a C1/C2.
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
