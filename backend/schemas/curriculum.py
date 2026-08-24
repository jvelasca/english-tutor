"""Esquemas Pydantic de la API del currículum (vista del contenido estático)."""

from __future__ import annotations

from pydantic import BaseModel


class CurriculumActivityOut(BaseModel):
    id: str
    type: str
    instruction: str
    target: str


class CurriculumObjectiveOut(BaseModel):
    id: str
    can_do: str
    title: str
    skills: list[str]
    concepts: list[str]
    vocabulary: list[str]
    thresholds: dict[str, float]
    activities: list[CurriculumActivityOut]
    # Contexto jerárquico (para el AI Teacher y la ruta de aprendizaje).
    module_id: str
    module_title: str
    unit_id: str
    unit_title: str
    lesson_id: str
    lesson_title: str
    order: int


class CurriculumModuleOut(BaseModel):
    id: str
    title: str
    order: int
    objectives: list[CurriculumObjectiveOut]


class CurriculumLevelOut(BaseModel):
    level_id: str
    level: str
    title: str
    description: str
    modules: list[CurriculumModuleOut]
    objective_count: int


class CurriculumLevelsOut(BaseModel):
    levels: list[CurriculumLevelOut]
