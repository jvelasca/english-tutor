"""Esquemas Pydantic de la configuración de estudio (V3.87.0 · FASE 2)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

#: Los `Literal` son el contrato de la API: un valor fuera de la lista lo rechaza
#: Pydantic antes de llegar al dominio (mismo criterio que `DictionaryDirection`).
StudyDirection = Literal["en-es", "es-en"]
StudyMode = Literal["recognition", "production", "mixed"]
StudyHints = Literal["off", "definition", "mnemonic", "all"]
StudyDifficulty = Literal["gentle", "auto", "intensive"]


class StudyConfigOut(BaseModel):
    """Configuración vigente. `configured` dice si el alumno la ha guardado."""

    direction: StudyDirection = "en-es"
    mode: StudyMode = "recognition"
    hints: StudyHints = "off"
    difficulty: StudyDifficulty = "auto"
    configured: bool = False


class StudyConfigUpdate(BaseModel):
    """PATCH parcial: un campo ausente/`None` significa «no lo cambies»."""

    direction: StudyDirection | None = None
    mode: StudyMode | None = None
    hints: StudyHints | None = None
    difficulty: StudyDifficulty | None = None
