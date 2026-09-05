"""Esquemas del registro cross-skill por estructura (V3.13, P1.2).

Endpoint SOLO LECTURA `/api/cross-skill`: por cada estructura gramatical del
nivel (objetivo con checks MC de grammar) devuelve la matriz de instrumentos
ofrecidos por destreza y la evidencia real del usuario en cada canal. El panel
frontend lo pinta como tabla/heatmap; nunca escribe.
"""
from __future__ import annotations

from pydantic import BaseModel


class StructureChannelOut(BaseModel):
    """Una celda de la matriz: instrumento ofrecido vs evidencia del usuario.

    - `offered=True, evidence=0` → instrumento disponible, aún sin evidencia (✗)
    - `offered=True, evidence>0` → evidencia correcta en esa destreza (✓)
    - `offered=False`           → el currículo no expone la estructura ahí (–)
    """

    offered: bool
    evidence: int


class StructureRowOut(BaseModel):
    structure_id: str
    name: str
    can_do: str = ""
    channels: dict[str, StructureChannelOut]


class CrossSkillMatrixOut(BaseModel):
    level_id: str
    level: str
    proto: bool
    structures: list[StructureRowOut]
