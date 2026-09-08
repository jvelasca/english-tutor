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
    word: str
    appearances: int
    first_seen: str
    last_seen: str
    exposures: int
    last_exposed_at: str
    production_days: int
    status: VocabularyStatus


class LexicalCompetence(BaseModel):
    """Matriz de competencia por ítem léxico (V3.21, V20-16; V3.22).

    Derivada de las filas existentes (sin migrar columnas de producción): pura y
    determinista. V3.22 separa Retention de Transfer: `retention` es señal
    espaciada (receptiva con `exposure_days` o productiva), mientras `transfer`
    exige producción en >= 2 canales/contextos. `production_gap` (reconocida y
    nunca producida) es el gap que cierra el micro-drill; `transfer_gap`
    (producida pero nunca transferida a otro contexto) queda como señal de
    falta de transferencia real.
    """

    recognition: bool
    production: bool
    production_channels: list[str] = Field(default_factory=list)
    transfer_contexts: int = 0
    transfer: bool
    retention: bool
    production_gap: bool
    transfer_gap: bool


class LexicalItemOut(BaseModel):
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
    exposures: int
    appearances: int
    # V3.19: desglose de producción por destreza (columnas `<channel>_prod`).
    # Invariante: chat_prod + speaking_prod + writing_prod + conversation_prod
    # == appearances (producción agregada histórica, sin cambio de semántica).
    chat_prod: int = 0
    speaking_prod: int = 0
    writing_prod: int = 0
    conversation_prod: int = 0
    # V3.21 (V20-16): matriz Recognition/Production/Transfer/Retention.
    competence: LexicalCompetence | None = None


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
    # V3.21 (V20-16) / V3.22: contadores de la matriz de competencia del léxico.
    recognized: int = 0
    produced: int = 0
    transfer: int = 0
    retention: int = 0
    production_gap: int = 0
    transfer_gap: int = 0


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
