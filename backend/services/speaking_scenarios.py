"""Catálogo de escenarios comunicativos (Speaking 3.0) — contenido versionado.

Los escenarios comunicativos (Restaurant, Doctor, Travel, Telephone, Work meeting,
Small talk, Problem solving, Interview) viven como JSON versionado en
`backend/curriculum/speaking_scenarios.json` (mismo patrón que el placement y el
Speaking Assessment): el equipo pedagógico edita el contenido sin tocar lógica.
Cada escenario declara un **objetivo comunicativo** (qué debe conseguir el alumno
en la conversación) y las **métricas** que observa (task_completion, interaction,
fluency, repair, turn_taking), que se miden con la infraestructura ya existente
(`services.speaking` + `services.interaction`). Este módulo solo carga, valida y
expone consultas; no puntúa (el scoring es determinista y vive en `speaking`).
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, computed_field

from services import speaking as speaking_svc
from services.curriculum import SPEAKING_SCENARIOS_VERSION

SPEAKING_SCENARIOS_PATH = (
    Path(__file__).resolve().parent.parent / "curriculum" / "speaking_scenarios.json"
)

# Métricas canónicas de un escenario comunicativo. Cada una se corresponde con
# señales ya medidas: `task_completion` → criterion `task_achievement`;
# `interaction`/`repair`/`turn_taking` → criterion `interaction` + Interaction
# Quality (`services.interaction`); `fluency` → criterion `fluency`.
SCENARIO_METRICS: tuple[str, ...] = (
    "task_completion",
    "interaction",
    "fluency",
    "repair",
    "turn_taking",
)


class SpeakingScenario(BaseModel):
    """Un escenario comunicativo: qué conversación se simula y con qué objetivo."""

    id: str
    title: str
    category: str = "Everyday life"
    cefr_target: str = "B1"
    task_type: str = "role_play"
    communicative_objective: str
    prompt: str
    metrics: list[str] = Field(default_factory=list)
    difficulty_vector: dict[str, int] = Field(default_factory=dict)

    @computed_field
    @property
    def difficulty(self) -> int:
        return speaking_svc.difficulty_from_vector(self.difficulty_vector)


class SpeakingScenariosCatalog(BaseModel):
    """Catálogo completo de escenarios comunicativos (contenido estático versionado)."""

    version: str = SPEAKING_SCENARIOS_VERSION
    scenarios: list[SpeakingScenario]


def load_scenarios() -> SpeakingScenariosCatalog:
    """Carga y valida el catálogo de escenarios desde JSON."""
    with SPEAKING_SCENARIOS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return SpeakingScenariosCatalog.model_validate(data)


def list_scenarios() -> list[dict]:
    """Devuelve todos los escenarios como dicts, en el orden declarado en el JSON."""
    return [s.model_dump() for s in load_scenarios().scenarios]


def get_scenario(scenario_id: str) -> dict | None:
    """Devuelve un escenario por id, o None si no existe."""
    for scenario in load_scenarios().scenarios:
        if scenario.id == scenario_id:
            return scenario.model_dump()
    return None


def validate_scenarios() -> list[str]:
    """Valida invariantes del catálogo y devuelve las violaciones (lista vacía = OK).

    Cubre: ids únicos, `task_type` reconocido por `speaking.TASK_TYPES`, métricas
    dentro de `SCENARIO_METRICS`, `communicative_objective`/`prompt` no vacíos,
    y `cefr_target` dentro del orden CEFR conocido.
    """
    from services.curriculum import CEFR_ORDER

    errors: list[str] = []
    catalog = load_scenarios()
    seen: set[str] = set()
    for scenario in catalog.scenarios:
        if scenario.id in seen:
            errors.append(f"escenario '{scenario.id}' duplicado")
        seen.add(scenario.id)
        if not scenario.communicative_objective:
            errors.append(f"escenario '{scenario.id}' sin objetivo comunicativo")
        if not scenario.prompt:
            errors.append(f"escenario '{scenario.id}' sin prompt")
        if scenario.task_type not in speaking_svc.TASK_TYPES:
            errors.append(
                f"escenario '{scenario.id}' task_type "
                f"'{scenario.task_type}' no reconocido"
            )
        if scenario.cefr_target not in CEFR_ORDER:
            errors.append(
                f"escenario '{scenario.id}' cefr_target "
                f"'{scenario.cefr_target}' no CEFR"
            )
        for metric in scenario.metrics:
            if metric not in SCENARIO_METRICS:
                errors.append(
                    f"escenario '{scenario.id}' métrica '{metric}' no canónica"
                )
    return errors
