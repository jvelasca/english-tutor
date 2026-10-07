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
StudyQueueMode = Literal["pending", "unlearned", "hard", "good", "failed", "all"]
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
    """Contadores del ámbito activo de Estudiar, más lo que entra hoy."""

    scope: StudyScope = "all"
    mode: StudyQueueMode = "pending"
    level: str = ""
    deck_id: int = 0
    collection_id: int | None = None
    total: int = 0
    studied: int = 0
    learned: int = 0
    unlearned: int = 0
    due: int = 0
    hard: int = 0
    good: int = 0
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
    #: Recordatorio de la ficha o del léxico. El complete no lo lee.
    mnemonic: str = ""
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
    unlearned: int = 0
    due: int = 0
    hard: int = 0
    good: int = 0
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


class StudyExampleIn(BaseModel):
    """Pide otra frase de ejemplo. No cierra la lección ni agenda FSRS."""

    word: str = Field(min_length=1, max_length=80)
    avoid: list[str] = Field(default_factory=list, max_length=12)


class StudyExampleOut(BaseModel):
    word: str
    phrase: str
    translation: str


class StudyQuizIn(BaseModel):
    """Pide las opciones de «¿Cuál es?». No cierra la lección ni agenda FSRS.

    ``exclude`` son las respuestas de las otras palabras de esta sesión
    (traducciones en EN→ES, palabras inglesas en ES→EN), para no volver a
    ofrecer el mazo que se está estudiando.
    """

    word: str = Field(min_length=1, max_length=80)
    translation: str = Field(min_length=1, max_length=500)
    exclude: list[str] = Field(default_factory=list, max_length=40)
    direction: StudyDirection = "en-es"


class StudyQuizOut(BaseModel):
    choices: list[str]


class StudyHintIn(BaseModel):
    """Pide una pista. No cierra la lección ni agenda FSRS.

    Si llega una ficha manual, la pista se guarda en su recordatorio. Si no,
    se guarda en la palabra del léxico.
    """

    word: str = Field(min_length=1, max_length=80)
    translation: str = ""
    card_type: str = ""
    card_id: str = ""
    direction: StudyDirection = "en-es"


class StudyHintOut(BaseModel):
    word: str
    hint: str


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
