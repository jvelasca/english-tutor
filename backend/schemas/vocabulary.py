"""Esquemas Pydantic de vocabulario."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from config import MAX_CONTENT_CHARS
from schemas.pronunciation import (
    FluencyStats,
    PhonemeBreakdown,
    PronunciationBreakdown,
)
from schemas.pronunciation import Level as PronunciationLevel

VocabularyStatus = Literal["exposed", "learning", "mastered"]

# Estado determinista por ítem léxico (V2.3). Más granular que `VocabularyStatus`
# porque distingue reconocimiento (`known`) de producción incipiente (`learning`)
# y añade `weak` (producido pero con recuerdo bajo).
LexicalStatus = Literal["mastered", "known", "learning", "weak"]


class VocabularyAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CONTENT_CHARS)


class VocabularyAnalyzeResponse(BaseModel):
    words: list[str]


class VocabularyItem(BaseModel):
    """Ítem léxico histórico (V2.3).

    V3.25 (F-K7/P2-01): los contadores pasan a los nombres canónicos
    `production_count` (producción del alumno) y `exposure_count` (input del
    tutor). `word` conserva la forma superficial (surface form).
    """

    word: str
    production_count: int
    first_seen: str
    last_seen: str
    exposure_count: int
    last_exposed_at: str
    production_days: int
    status: VocabularyStatus


class VocabularyEventOut(BaseModel):
    """Evento del ledger léxico (V3.26, Eje B/F-B2).

    Historia detallada por FORMA DE SUPERFICIE (`word`), con su unidad canónica
    (`lexical_unit`) para poder agregar sin perder la superficie. La semántica
    de conteo es idéntica a la de los contadores: presencia de la palabra en un
    mensaje/intento (nunca frecuencia de tokens). El ledger empieza en V3.26
    (sin backfill) y es señal, no evidencia de mastery."""

    word: str
    lexical_unit: str
    event_type: Literal["produced", "exposed", "retrieval"]
    channel: str
    activity: str
    created_at: str


class LexicalCompetence(BaseModel):
    """Matriz de competencia por ítem léxico (V3.21, V20-16; V3.22; V3.23).

    Derivada de las filas existentes (sin migrar columnas de producción): pura y
    determinista. V3.22 separó Retention de Transfer; V3.23 (P1-02/P1-04):
    - `retention` exige recuperación DEMORADA (`retrieval_days >= umbral`), no
      exposición/producción espaciada (que pasan a `spaced_exposure` /
      `spaced_production`, señales independientes informativas).
    - `transfer` se mide por CONTEXTO de actividad (`channel:activity`,
      `transfer_contexts`), no solo por canal.
    `production_gap` (reconocida y nunca producida) es el gap que cierra el
    micro-drill; `transfer_gap` (producida pero nunca transferida a otro
    contexto) queda como señal de falta de transferencia real.

    F-K5 (V3.25): desambiguación por dominio. `transfer`/`retention` en esta
    capa LÉXICA (señal informativa por ítem, D5/E3) NO comparten semántica con
    la capa ACADÉMICA (evidence_kind `transfer`/`delayed` de la escalera
    Assessment 2.0 y la certificación §6.3). Si un schema de dominio las
    renombra, pasarán a `contextual_transfer` / `delayed_recall`.
    """

    recognition: bool
    production: bool
    production_channels: list[str] = Field(default_factory=list)
    transfer_contexts: int = 0
    transfer: bool
    retention: bool
    spaced_exposure: bool = False
    spaced_production: bool = False
    retrieval_successes: int = 0
    retrieval_days: int = 0
    production_gap: bool
    transfer_gap: bool


class LexicalItemOut(BaseModel):
    """Ítem del léxico personal (lexicón).

    V3.25 (F-K7/P2-01/P2-02): `word` es la FORMA SUPERFICIAL (surface form:
    "going"); `lemma` el lema que el currículo declara cuando el ítem es de
    currículo ("" para léxico libre); y `lexical_unit` la UNIDAD de análisis
    canónica (lemma si existe, superficie normalizada si no). Los contadores
    usan los nombres canónicos `production_count`/`exposure_count` (el
    histórico `appearances`/`exposures` quedó renombrado en la migración
    V3.25). El agregado de dominio por `lexical_unit` evita tratar
    `go/going/went/gone` como conocimientos independientes cuando comparten
    lemma.
    """

    word: str
    lemma: str
    cefr: str
    # LEXICAL_KINDS: word/collocation/phrasal_verb/expression/sentence_frame/
    # functional_chunk/structure (P1, §3.2)
    kind: str
    source: str  # "curriculum" | "user" | "imported"
    status: LexicalStatus
    recall: float
    next_review_days: int
    production_count: int
    exposure_count: int
    lexical_unit: str = ""
    # V3.19: desglose de producción por destreza (columnas `<channel>_prod`).
    # Invariante: chat_prod + speaking_prod + writing_prod + conversation_prod
    # == production_count (producción agregada histórica).
    chat_prod: int = 0
    speaking_prod: int = 0
    writing_prod: int = 0
    conversation_prod: int = 0
    # V3.21 (V20-16): matriz Recognition/Production/Transfer/Retention.
    competence: LexicalCompetence | None = None


class LexicalUnitSurfaceOut(BaseModel):
    """Forma superficial (surface form) dentro de una unidad léxica agregada
    (V3.25.1/P1-02).

    Cada superficie conserva su PROPIO estado/mastery/recall: dominar `go` no
    domina automáticamente `going`/`went`/`gone`, que requieren conocimiento
    productivo distinto."""

    word: str
    lemma: str = ""
    cefr: str = ""
    kind: str = "word"
    source: str = "user"  # "curriculum" | "user" | "imported"
    status: LexicalStatus
    mastery: float
    recall: float
    production_count: int
    exposure_count: int
    speaking_prod: int = 0
    competence: LexicalCompetence | None = None


class LexicalUnitOut(BaseModel):
    """Unidad léxica agregada (V3.25.1/P1-02): el conocimiento a nivel de
    `lexical_unit` (lema o superficie normalizada) SIN fundir las superficies.

    `mastery`/`recall` de unidad son derivados informativos (máximo entre
    superficies); `status` agrega los estados de las superficies (mastered si
    alguna lo está). El contrato por superficie (`items`/`summary`) no cambia:
    esta sección es aditiva y expone `surfaces` con su competencia propia."""

    lexical_unit: str
    kind: str
    cefr: str
    lemma: str = ""
    source: str = "user"  # "curriculum" si alguna superficie es de currículo
    status: LexicalStatus
    mastery: float
    recall: float
    surface_count: int
    mastered_surfaces: int
    recognized: bool
    produced: bool
    transfer: bool
    production_count: int
    exposure_count: int
    production_gap: bool
    transfer_gap: bool
    surfaces: list[LexicalUnitSurfaceOut] = Field(default_factory=list)


class CefrBucket(BaseModel):
    cefr: str
    count: int


class LexiconSummary(BaseModel):
    total: int
    known: int
    learning: int
    weak: int
    mastered: int
    by_cefr: list[CefrBucket]
    # V3.21 (V20-16) / V3.22 / V3.23: contadores de la matriz de competencia.
    # V3.23: `retention` cuenta recuperaciones demoradas; `spaced_exposure` es
    # el contador informativo de exposición espaciada (señal independiente).
    recognized: int = 0
    produced: int = 0
    transfer: int = 0
    retention: int = 0
    spaced_exposure: int = 0
    production_gap: int = 0
    transfer_gap: int = 0
    # V3.25.1 (P1-02): resumen del agregado por `lexical_unit` (cada unidad
    # cuenta una sola vez; opcional y aditivo, el contrato de superficie no
    # cambia). Ver `LexicalUnitOut` y `services.lexicon.summary_units`.
    units: dict | None = None


class LexiconCoverageLevel(BaseModel):
    """Cobertura léxica de un nivel (Constitución §3.1): indicador, no puerta."""

    cefr: str
    total: int
    receptive: int  # encontradas (input o producción)
    productive: int  # con producción al menos una vez
    mastered: int
    known: int
    learning: int
    weak: int
    # Ratio 0..1 frente al extremo superior de la banda objetivo; None si la
    # banda no es numérica (p. ej. C2).
    receptive_pct: float | None
    productive_pct: float | None


class LexiconCoverage(BaseModel):
    receptive: int
    productive: int
    mastered: int
    by_level: list[LexiconCoverageLevel] = Field(default_factory=list)


class LexiconOut(BaseModel):
    summary: LexiconSummary
    items: list[LexicalItemOut]
    coverage: LexiconCoverage | None = None
    # V3.25.1 (P1-02): agregado por `lexical_unit` (aditivo, contrato intacto).
    units: list[LexicalUnitOut] = Field(default_factory=list)


class DrillCandidatesOut(BaseModel):
    """Candidatos al speaking micro-drill (V3.19).

    Palabras expuestas (leídas/oídas) y nunca producidas en práctica de
    speaking (`speaking_prod == 0`), ordenadas por recuerdo ascendente.
    """

    words: list[str]


class DrillAttemptOut(BaseModel):
    """Resultado de un intento de speaking micro-drill (V3.19).

    Reutiliza el scoring de pronunciación existente (`score_pronunciation`
    sobre la palabra esperada) y declara si la palabra se produjo (entra en el
    `breakdown.correct`). El drill NO declara dominio ni crea evidencia
    curricular (D5/E3): `produced=True` solo suma `speaking_prod` y saca la
    palabra de la lista de candidatas.
    """

    word: str
    produced: bool
    expected: str
    heard: str
    score: int
    level: PronunciationLevel
    ok: bool
    word_accuracy: int
    phonetic_score: int
    phoneme_accuracy_proxy: int
    prosody_proxy: int
    pronunciation_source: str
    breakdown: PronunciationBreakdown
    phoneme_breakdown: PhonemeBreakdown
    fluency: FluencyStats | None = None
    # V3.21 (V20-14/V20-15): metadatos ASR del intento. Cuando `asr_status !=
    # "ok"` el audio no se reconoció con fiabilidad (silencio/ilegible/confianza
    # baja): `produced` va forzado a False y NO se acredita fallo al alumno.
    asr_status: str = "ok"  # ok | no_speech | unintelligible | low_confidence
    asr_confidence: float | None = None


class SentenceContextOut(BaseModel):
    """Contexto del paso "Sentence" del micro-drill (V3.21/F6.1).

    Frase determinista que contiene la palabra objetivo: del banco oficial de
    read-aloud del nivel (`source: "route"`) o una plantilla simple sin
    significado inventado (`source: "template"`)."""

    word: str
    phrase: str
    source: str  # "route" | "template"
    level: str


class SentenceAttemptOut(BaseModel):
    """Resultado del paso "Sentence" del micro-drill (V3.21/F6.1).

    El alumno repite la frase de contexto en voz alta:
    - `produced`: la palabra objetivo quedó alineada en la transcripción.
    - `phrase_ok`: la frase COMPLETA superó el umbral del scorer (>= 80).
    - `passed` = produced AND phrase_ok: es lo que acredita producción oral por
      este paso (decir la palabra dentro de la frase, no suelta).

    Igual que el paso palabra, el drill no declara dominio ni crea evidencia
    curricular (D5/E3). Con `asr_status != "ok"` no se puntúa ni se penaliza.
    """

    word: str
    phrase: str
    source: str  # "route" | "template"
    produced: bool
    phrase_ok: bool
    passed: bool
    heard: str
    score: int
    level: PronunciationLevel
    fluency: FluencyStats | None = None
    asr_status: str = "ok"  # ok | no_speech | unintelligible | low_confidence
    asr_confidence: float | None = None
