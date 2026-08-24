"""Carga y validación del currículum (puro, determinista).

El contenido del currículum vive como JSON versionado en `backend/curriculum/` y
no en Python, para que el equipo pedagógico pueda editarlo sin tocar lógica. Este
módulo solo lo carga, lo valida (Pydantic) y expone funciones de consulta.

Separación conceptual:
- Curriculum Engine (aquí): "qué debe aprender" (estático).
- Learning Engine (profile/grammar/vocabulary/...): "qué sabe" (dinámico).
- Adaptive Engine (`services/adaptive.py`): "qué hacer ahora".
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

# Destrezas canónicas del modelo pedagógico (subconjunto CEFR ampliado con las
# señales que ya mide el Learning Engine).
CANONICAL_SKILLS: tuple[str, ...] = (
    "vocabulary",
    "grammar",
    "pronunciation",
    "listening",
    "speaking",
    "reading",
    "writing",
)

# Umbral por defecto para dominar una destreza de un objetivo (0..1).
DEFAULT_THRESHOLD = 0.8

# Niveles CEFR disponibles (los archivos `curriculum/<level_id>.json` son la
# fuente de verdad del contenido; este orden fija la progresión).
CEFR_ORDER: tuple[str, ...] = ("A1", "A2", "B1", "B2", "C1", "C2")

CURRICULUM_DIR = Path(__file__).resolve().parent.parent / "curriculum"


class Activity(BaseModel):
    id: str
    type: str
    instruction: str
    target: str = ""


class ObjectiveCheck(BaseModel):
    """Check determinista de un objetivo (auto-evaluable, con respuesta correcta).

    A diferencia de `Activity` (instrucción abierta), un check es una pregunta de
    opción múltiple con `correct_index`, que el Mastery Engine puntúa en servidor.
    El cliente nunca recibe `correct_index` (se oculta en los esquemas de salida)."""

    id: str
    skill: str
    prompt: str
    options: list[str]
    correct_index: int


class Objective(BaseModel):
    id: str
    can_do: str
    title: str
    skills: list[str]
    concepts: list[str] = Field(default_factory=list)
    vocabulary: list[str] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)
    activities: list[Activity] = Field(default_factory=list)
    checks: list[ObjectiveCheck] = Field(default_factory=list)

    def threshold(self, skill: str) -> float:
        """Umbral de dominio de una destreza (0..1); por defecto 0.8."""
        return self.thresholds.get(skill, DEFAULT_THRESHOLD)


class Lesson(BaseModel):
    id: str
    title: str
    order: int
    objectives: list[Objective]


class Unit(BaseModel):
    id: str
    title: str
    order: int
    lessons: list[Lesson]


class Module(BaseModel):
    id: str
    title: str
    order: int
    units: list[Unit]


class Level(BaseModel):
    course_id: str
    level_id: str
    level: str
    title: str
    description: str = ""
    modules: list[Module]

    def objectives(self) -> list[Objective]:
        return [
            o
            for m in self.modules
            for u in m.units
            for les in u.lessons
            for o in les.objectives
        ]


class AssessmentItem(BaseModel):
    id: str
    skill: str
    prompt: str
    options: list[str]
    correct_index: int
    difficulty: int = 1


class PlacementTest(BaseModel):
    id: str
    title: str
    description: str = ""
    items: list[AssessmentItem]


class Exam(BaseModel):
    id: str
    title: str
    min_per_skill: float = 0.75
    skills: list[str] = Field(default_factory=list)
    items: list[AssessmentItem]


class AssessmentData(BaseModel):
    placement: PlacementTest
    exams: dict[str, Exam] = Field(default_factory=dict)
    remediation: dict[str, list[str]] = Field(default_factory=dict)


def _level_file(level_id: str) -> Path:
    return CURRICULUM_DIR / f"{level_id}.json"


def available_level_ids() -> list[str]:
    """Devuelve los ids de nivel con archivo de contenido (p. ej. ['a1'])."""
    return sorted(
        p.stem for p in CURRICULUM_DIR.glob("*.json") if p.name != "assessments.json"
    )


def load_level(level_id: str) -> Level:
    """Carga y valida el contenido de un nivel. Lanza `FileNotFoundError` si no
    existe el archivo."""
    path = _level_file(level_id)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return Level.model_validate(data)


def load_all_levels() -> list[Level]:
    """Carga todos los niveles disponibles ordenados por el orden CEFR."""
    levels = [load_level(lid) for lid in available_level_ids()]
    return sorted(
        levels,
        key=lambda lv: CEFR_ORDER.index(lv.level) if lv.level in CEFR_ORDER else 99,
    )


def load_assessments() -> AssessmentData:
    path = CURRICULUM_DIR / "assessments.json"
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return AssessmentData.model_validate(data)


def get_objective(level: Level, objective_id: str) -> Objective | None:
    for obj in level.objectives():
        if obj.id == objective_id:
            return obj
    return None


def objective_index(level: Level, objective_id: str) -> int:
    """Posición ordinal (0-based) del objetivo dentro del nivel, según el orden
    de aparición en el JSON (que define la secuencia de desbloqueo)."""
    ids = [o.id for o in level.objectives()]
    return ids.index(objective_id) if objective_id in ids else -1


def next_level_id(level: str) -> str | None:
    """Devuelve el id del siguiente nivel CEFR, o None si es el último."""
    if level not in CEFR_ORDER:
        return None
    idx = CEFR_ORDER.index(level)
    return CEFR_ORDER[idx + 1].lower() if idx + 1 < len(CEFR_ORDER) else None
