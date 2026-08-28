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
from collections import Counter
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

# Destrezas auto-scorables: el Mastery Engine las evalúa con evidencia
# determinista (ObjectiveCheck de opción múltiple). Solo estas gatean el dominio.
ASSESSABLE_SKILLS: tuple[str, ...] = (
    "grammar",
    "vocabulary",
    "reading",
    "listening",
)

# Destrezas performance-scorables: se evalúan con rúbricas deterministas + LLM
# (voz/texto) y registran evidencia de rendimiento versionada. Ambas familias
# son evaluables; difieren en el mecanismo de puntuación, no en si lo son.
PERFORMANCE_SKILLS: tuple[str, ...] = (
    "speaking",
    "writing",
    "pronunciation",
)

# Subdestrezas por destreza canónica. Son una descomposición más granular del
# "can-do" CEFR: cada objetivo puede declarar a qué subdestrezas entrena. La
# validación exige que cada subdestreza pertenezca a la tupla de su destreza.
SUBSKILLS: dict[str, tuple[str, ...]] = {
    "listening": (
        "sound_recognition",
        "word_recognition",
        "phrase_recognition",
        "connected_speech",
        "gist",
        "detail",
        "inference",
        "speaker_intention",
        "attitude",
        "multiple_speakers",
        "fast_speech",
        "accents",
        "dictation",
        "shadowing",
        "real_world",
    ),
    "speaking": (
        "pronunciation",
        "fluency",
        "grammar",
        "vocabulary",
        "interaction",
        "coherence",
        "intelligibility",
        "lexical_retrieval",
        "self_correction",
        "turn_taking",
    ),
    "reading": (
        "skimming",
        "scanning",
        "detail",
        "inference",
        "vocabulary",
        "structure",
    ),
    "writing": (
        "grammar",
        "vocabulary",
        "coherence",
        "cohesion",
        "register",
        "spelling",
        "punctuation",
    ),
    "grammar": (
        "tenses",
        "modals",
        "articles",
        "prepositions",
        "conditionals",
        "passive",
        "reported_speech",
        "relative_clauses",
        "word_order",
    ),
    "vocabulary": (
        "collocations",
        "phrasal_verbs",
        "word_families",
        "idioms",
        "register",
        "spelling",
    ),
    "pronunciation": (
        "sounds",
        "stress",
        "intonation",
        "rhythm",
        "linking",
        "minimal_pairs",
    ),
}

# Umbral por defecto para dominar una destreza de un objetivo (0..1).
DEFAULT_THRESHOLD = 0.8

# Nº mínimo de evidencias (intentos) por destreza para poder declarar dominio.
# Evita que un único acierto marque un objetivo como dominado.
DEFAULT_MINIMUM_ATTEMPTS = 3

# Niveles CEFR disponibles (los archivos `curriculum/<level_id>.json` son la
# fuente de verdad del contenido; este orden fija la progresión).
CEFR_ORDER: tuple[str, ...] = ("A1", "A2", "B1", "B2", "C1", "C2")

# Versión del esquema/contenido del currículum y las evaluaciones. Independiente
# de la versión de la aplicación: identifica QUÉ contenido se evaluó.
CURRICULUM_VERSION = "1.2.5"

# Versiones de los instrumentos de evaluación (independientes de la versión de la
# app y del currículum). Identifican QUÉ instrumento produjo cada resultado para
# que dos respuestas idénticas sean reproducibles aunque el contenido evolucione.
ASSESSMENT_VERSION = "1.0.0"  # contenido de assessments.json (placement + exámenes)
PLACEMENT_VERSION = "2.0.0"  # motor de placement adaptativo (IRT-lite/1PL multiskill)
RUBRIC_VERSION = "1.0.0"  # rubrics de scoring (speaking/writing/pronunciation)
SPEAKING_ASSESSMENT_VERSION = "1.0.0"  # instrumento de Speaking Assessment 1.0
LISTENING_BANK_VERSION = "3.0.0"  # banco de listening (TTS pre-renderizado, 8D)

CURRICULUM_DIR = Path(__file__).resolve().parent.parent / "curriculum"

# Archivos JSON de `CURRICULUM_DIR` que NO son un nivel (instrumentos/índices).
_NON_LEVEL_FILES = frozenset(
    {
        "assessments.json",
        "speaking_assessment.json",
        "cefr_matrix.json",
        "cefr_descriptors.json",
    }
)


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
    subskills: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    vocabulary: list[str] = Field(default_factory=list)
    thresholds: dict[str, float] = Field(default_factory=dict)
    minimum_attempts: int = DEFAULT_MINIMUM_ATTEMPTS
    activities: list[Activity] = Field(default_factory=list)
    checks: list[ObjectiveCheck] = Field(default_factory=list)

    def threshold(self, skill: str) -> float:
        """Umbral de dominio de una destreza (0..1); por defecto 0.8."""
        return self.thresholds.get(skill, DEFAULT_THRESHOLD)

    def assessable_skills(self) -> list[str]:
        """Destrezas que gatean el dominio: las que tienen al menos un check
        determinista. Las destrezas de producción (speaking, writing,
        pronunciation) no aparecen hasta que exista evidencia real de rendimiento."""
        return list(dict.fromkeys(c.skill for c in self.checks))


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
    version: str = CURRICULUM_VERSION
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
    """Instrumento de placement (CAT adaptativo, IRT-lite/1PL).

    Los ítems de las destrezas de producción (speaking/writing/pronunciation) y de
    listening son de **reconocimiento o meta-lenguaje** (opción múltiple), NO
    evaluación de voz/texto real ni reproducción de audio: el placement no captura
    audio ni producción libre. Miden conciencia de la destreza, no su ejecución.
    """

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
        p.stem for p in CURRICULUM_DIR.glob("*.json") if p.name not in _NON_LEVEL_FILES
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


def validate_level(level: Level) -> list[str]:
    """Valida invariantes estructurales de un nivel y devuelve las violaciones.

    Cada elemento de la lista devuelta es un mensaje legible describiendo una
    violación. Lista vacía = nivel válido. Cubre: ids duplicados (objetivos,
    actividades, checks, módulos, unidades, lecciones), órdenes únicos por
    contenedor, skills canónicas, checks que mapean a skills del objetivo,
    thresholds válidos, minimum_attempts >= 1, opciones de check válidas y
    actividades con id/tipo/instrucción no vacíos.
    """
    errors: list[str] = []
    lid = level.level_id

    def _dupes(values: list, what: str) -> None:
        for value, count in Counter(values).items():
            if count > 1:
                errors.append(f"{lid}: {what} '{value}' duplicado ({count} veces)")

    objectives = level.objectives()

    # IDs únicos globales (objetivos, actividades, checks).
    _dupes([o.id for o in objectives], "objetivo")
    _dupes([a.id for o in objectives for a in o.activities], "actividad")
    _dupes([c.id for o in objectives for c in o.checks], "check")

    # Módulos: id y orden únicos en todo el nivel.
    _dupes([m.id for m in level.modules], "módulo")
    _dupes([m.order for m in level.modules], "orden de módulo")

    for module in level.modules:
        # Unidades: id y orden únicos dentro de cada módulo.
        _dupes([u.id for u in module.units], "unidad")
        _dupes([u.order for u in module.units], "orden de unidad")
        for unit in module.units:
            # Lecciones: id y orden únicos dentro de cada unidad.
            _dupes([les.id for les in unit.lessons], "lección")
            _dupes([les.order for les in unit.lessons], "orden de lección")

    for obj in objectives:
        # Skills: no vacías y canónicas.
        if not obj.skills:
            errors.append(f"{lid}: objetivo {obj.id} sin skills")
        for skill in obj.skills:
            if skill not in CANONICAL_SKILLS:
                errors.append(f"{lid}: objetivo {obj.id} skill '{skill}' no canónica")

        # Subskills: cada una debe pertenecer a la tupla de una de las destrezas
        # declaradas por el objetivo.
        for subskill in obj.subskills:
            if not any(
                subskill in SUBSKILLS.get(skill, ()) for skill in obj.skills
            ):
                errors.append(
                    f"{lid}: objetivo {obj.id} subskill '{subskill}' "
                    f"no pertenece a ninguna destreza declarada"
                )

        # Cada check solo evalúa una skill declarada por el objetivo.
        for check in obj.checks:
            if check.skill not in obj.skills:
                errors.append(
                    f"{lid}: check {check.id} evalúa '{check.skill}' "
                    f"no declarada en {obj.id}"
                )

        # Thresholds: claves canónicas y valor en (0, 1].
        for skill, value in obj.thresholds.items():
            if skill not in CANONICAL_SKILLS:
                errors.append(
                    f"{lid}: objetivo {obj.id} threshold '{skill}' no canónica"
                )
            if not 0 < value <= 1:
                errors.append(
                    f"{lid}: {obj.id} threshold '{skill}'={value} no en (0,1]"
                )

        # Mínimo de intentos para consolidar dominio.
        if obj.minimum_attempts < 1:
            errors.append(
                f"{lid}: objetivo {obj.id} minimum_attempts={obj.minimum_attempts} < 1"
            )

        # Checks: al menos 2 opciones e índice correcto dentro de rango.
        for check in obj.checks:
            if len(check.options) < 2:
                errors.append(f"{lid}: check {check.id} con menos de 2 opciones")
            if not 0 <= check.correct_index < len(check.options):
                errors.append(
                    f"{lid}: check {check.id} correct_index={check.correct_index} "
                    f"fuera de rango"
                )

        # Actividades: id, type e instruction no vacíos.
        for activity in obj.activities:
            if not activity.id:
                errors.append(f"{lid}: actividad sin id en {obj.id}")
            if not activity.type:
                errors.append(f"{lid}: actividad sin type en {obj.id}")
            if not activity.instruction:
                errors.append(f"{lid}: actividad sin instruction en {obj.id}")

    return errors
