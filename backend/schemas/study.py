"""Esquemas Pydantic de la configuración de estudio (V3.87.0 · FASE 2)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

#: Los `Literal` son el contrato de la API: un valor fuera de la lista lo rechaza
#: Pydantic antes de llegar al dominio (mismo criterio que `DictionaryDirection`).
StudyDirection = Literal["en-es", "es-en"]
StudyMode = Literal["recognition", "production", "mixed"]
StudyHints = Literal["off", "definition", "mnemonic", "all"]
StudyDifficulty = Literal["gentle", "auto", "intensive"]
StudyScope = Literal["all", "level", "deck"]
StudyQueueMode = Literal["pending", "failed", "all"]
LessonFacetName = Literal["pronunciation", "context", "senses", "related"]
LessonFacetStatus = Literal["done", "pending", "na"]


class StudyConfigOut(BaseModel):
    """Configuración vigente. `configured` dice si el alumno la ha guardado."""

    direction: StudyDirection = "en-es"
    mode: StudyMode = "recognition"
    hints: StudyHints = "off"
    difficulty: StudyDifficulty = "auto"
    #: Tope de palabras de la sesión de hoy en el banco (nuevas + repasos).
    words_per_day: int = 20
    #: Pasos opcionales que, si quedan pendientes, impiden contar la palabra
    #: como aprendida. El significado siempre cuenta y no se lista aquí.
    required_facets: list[LessonFacetName] = Field(default_factory=list)
    configured: bool = False


class StudyConfigUpdate(BaseModel):
    """PATCH parcial: un campo ausente/`None` significa «no lo cambies»."""

    direction: StudyDirection | None = None
    mode: StudyMode | None = None
    hints: StudyHints | None = None
    difficulty: StudyDifficulty | None = None
    words_per_day: int | None = Field(default=None, ge=1, le=200)
    required_facets: list[LessonFacetName] | None = None


class StudySummaryOut(BaseModel):
    """Cinco contadores del ámbito activo de Estudiar, más lo que entra hoy."""

    scope: StudyScope = "all"
    mode: StudyQueueMode = "pending"
    level: str = ""
    deck_id: int = 0
    collection_id: int | None = None
    total: int = 0
    studied: int = 0
    learned: int = 0
    due: int = 0
    times_studied: int = 0
    queued: int = 0


class StudyLessonItemOut(BaseModel):
    #: Identidad opaca que emitió esta cola. El complete solo acepta este id.
    item_id: str
    word: str
    cefr: str = ""
    card_type: str
    card_id: str
    deck_id: int = 0
    is_new: bool = True
    translation: str = ""
    definition: str = ""
    facets: dict[str, str] = Field(default_factory=dict)
    state: str = "new"


class StudyQueueOut(BaseModel):
    """Cola de la lección de hoy, con los mismos contadores que el resumen."""

    scope: StudyScope = "all"
    mode: StudyQueueMode = "pending"
    level: str = ""
    deck_id: int = 0
    collection_id: int | None = None
    items: list[StudyLessonItemOut] = Field(default_factory=list)
    total: int = 0
    studied: int = 0
    learned: int = 0
    due: int = 0
    times_studied: int = 0
    queued: int = 0
    study_config: StudyConfigOut | None = None


class StudyCompleteIn(BaseModel):
    """Cierre del ítem que sirvió la cola.

    ``item_id`` lo emitió ``GET /study/queue``. Palabra, tipo de carta, id y
    mazo salen de esa fila: si el cuerpo los trae, se ignoran.

    ``facets`` son lo que el cliente afirma al cerrar. El servidor no comprueba
    que el paso se haya mostrado. Un paso saltado sigue en ``pending``.

    ``learned`` de la respuesta se calcula sobre la carta que recibió esta nota
    y los ``required_facets`` vigentes en ese momento. No es un hecho histórico.
    """

    item_id: str = Field(min_length=1, max_length=80)
    grade: int = Field(ge=1, le=4)
    translation: str = ""
    facets: dict[str, str] = Field(default_factory=dict)


class StudyCompleteOut(BaseModel):
    """``learned`` mira la carta calificada y la configuración de ahora.

    ``state == review`` no es mastery: hacen falta además los pasos obligatorios.
    Cambiar ``required_facets`` puede cambiar este booleano sin un repaso nuevo.
    """

    word: str
    grade: int
    card_type: str
    card_id: str
    deck_id: int
    due_at: str = ""
    next_in_days: float = 0.0
    facets: dict[str, str] = Field(default_factory=dict)
    learned: bool = False
