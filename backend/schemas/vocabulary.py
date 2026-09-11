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

# V3.39: tope de la frase escrita a mano en la actividad `write` del drill.
MAX_WRITE_CHARS = 600

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
    event_type: Literal["produced", "exposed", "retrieval", "recalled"]
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
    # V3.34 (Recall 2.0): recuperación de la palabra desde su significado
    # (paso Recall por texto). Señal propia: no acredita producción ni
    # sustituye la recuperación demorada (`retention`).
    cued_recall: bool = False
    recall_successes: int = 0
    # V3.35 (Longitudinal Learning Evidence): INTENTOS de recall (acierto o
    # fallo). Sin intentos no se distingue "no lo intentó" de "falló".
    recall_attempts: int = 0
    recall_days: int = 0
    production_gap: bool
    transfer_gap: bool


class LexicalEvidence(BaseModel):
    """Evidencia longitudinal por ítem léxico (V3.35).

    Derivada del ledger `learning_evidence` (no de los contadores rápidos de
    `vocabulary`): cada recuperación/producción es un EVENTO con su intervalo,
    y la retención se lee como la cadena `evento_n → intervalo → evento_{n+1}`.
    Los contadores agregados de `LexicalCompetence` siguen siendo el atajo.

    - `attempts` — nº de eventos (incluye fallos);
    - `successes` — nº de eventos correctos;
    - `distinct_success_days` — días naturales distintos con éxito;
    - `intervals` — intervalos (días) de los eventos con éxito, en orden
      cronológico (cadena de repasos, no lista ordenada por valor).

    V3.36 (Learning Evidence 2.0) añade las dimensiones del evento:
    `success_rate`, `independent_successes` (aciertos sin apoyo: lo único que
    puede pesar en automaticidad), `support_levels` y `error_types`
    (histogramas) y `mean_response_time_ms` (latencia media declarada).

    V3.37 (cues graduados) añade `independent_success_days` (días naturales
    distintos con éxito sin apoyo: lo que exige `is_automatic`) y
    `recall_rungs` (éxitos de recall por peldaño servido).

    V3.37.1 (consolidación y regresión) añade `recall_rung_days` (días
    distintos con éxito por peldaño: lo que exige dar el peldaño por superado)
    y `recall_rung_failures` (fallos por peldaño: lo que lee la regresión).

    V3.38 (P1-03) añade la segmentación por MODALIDAD, para que la automaticidad
    deje de ser un booleano global: `skill_successes`/`skill_success_days`
    (volumen y días con éxito por modalidad) y `skill_independent_successes`/
    `skill_independent_days` (restringidos a éxito sin apoyo: la base de
    `services.evidence.automatic_skills`). Las claves son valores de
    `LEXICAL_SKILLS`; un `skill` legacy fuera del vocabulario no entra.
    """

    attempts: int = 0
    successes: int = 0
    distinct_success_days: int = 0
    intervals: list[float] = Field(default_factory=list)
    success_rate: float = 0.0
    independent_successes: int = 0
    independent_success_days: int = 0
    support_levels: dict[str, int] = Field(default_factory=dict)
    error_types: dict[str, int] = Field(default_factory=dict)
    recall_rungs: dict[str, int] = Field(default_factory=dict)
    recall_rung_days: dict[str, int] = Field(default_factory=dict)
    recall_rung_failures: dict[str, int] = Field(default_factory=dict)
    skill_successes: dict[str, int] = Field(default_factory=dict)
    skill_success_days: dict[str, int] = Field(default_factory=dict)
    skill_independent_successes: dict[str, int] = Field(default_factory=dict)
    skill_independent_days: dict[str, int] = Field(default_factory=dict)
    # V3.38.1 (P1-02): intentos y latencia media POR MODALIDAD. `skill_attempts`
    # cuenta todos los eventos del skill (aciertos y fallos) y
    # `skill_mean_response_time_ms` mide la fluidez de cada modalidad (clave
    # ausente si no midió latencia), para no recomprimir la evidencia en una
    # sola media global.
    skill_attempts: dict[str, int] = Field(default_factory=dict)
    skill_mean_response_time_ms: dict[str, float] = Field(default_factory=dict)
    mean_response_time_ms: float | None = None


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
    # V3.35 (Longitudinal Learning Evidence): evidencia fina del ledger
    # (`attempts`/`successes`/`days`/`intervals`), aditiva a los contadores.
    evidence: LexicalEvidence | None = None


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
    # V3.34: recuperadas desde el significado en el paso Recall del drill.
    recalled: int = 0
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


# ---------------------------------------------------------------------------
# Diccionario de consulta (V3.30). D3: la consulta es SOLO LECTURA — nunca crea
# filas en `vocabulary` ni eventos en `vocabulary_events`. La definición llega
# de la caché global `dictionary_entries` (Fase B la rellena con el modelo
# local); hasta entonces `definition_source="none"`.
# ---------------------------------------------------------------------------


class DictionaryLookupRequest(BaseModel):
    """Petición de consulta del diccionario (V3.30).

    `model` es opcional (mismo contrato que `/api/translate`): el cliente puede
    pedir un modelo local concreto para la generación de contenido (Fase B).
    V3.31.1 (semántica documentada): el contenido cacheado es global y
    canónico, así que `model` solo influye en la generación de contenido
    NUEVO; nunca en qué contenido se sirve (si está cacheado, se sirve igual).
    """

    word: str = Field(min_length=1, max_length=80)
    model: str | None = None
    # V3.39 (diccionario reversible): dirección de la búsqueda. `en-es` es la
    # histórica (palabra inglesa → definición EN + traducción ES); `es-en`
    # busca un término español y devuelve su equivalente inglés. Aditivo: el
    # valor por defecto mantiene intactos los clientes anteriores.
    direction: Literal["en-es", "es-en"] = "en-es"


class DictionaryExampleOut(BaseModel):
    """Frase de ejemplo determinista del banco de la app que contiene la palabra
    (V3.30): sin LLM, nunca la plantilla neutra del micro-drill."""

    phrase: str
    source: str = "pronunciation_corpus"
    level: str = ""


class DictionarySurfaceUsageOut(BaseModel):
    """Marca de uso de la FORMA SUPERFICIAL exacta buscada (V3.30).

    Derivada en servidor con los mismos cómputos puros de `services/lexicon.py`
    que usa `get_lexicon` (premisa 21). Todos los campos con `None`/0 indican
    que la forma nunca se registró en la app."""

    status: LexicalStatus | None = None
    mastery: float = 0.0
    recall: float = 0.0
    next_review_days: int = 0
    production_count: int = 0
    exposure_count: int = 0
    production_channels: list[str] = Field(default_factory=list)
    competence: LexicalCompetence | None = None
    last_activity_at: str = ""


class DictionaryUnitUsageOut(BaseModel):
    """Marca de uso del agregado por `lexical_unit` (V3.30).

    Solo se expone cuando la unidad canónica difiere de la forma buscada
    (p. ej. buscar `going` agrega por la unidad `go`). Derivado informativo:
    `mastery`/`recall` son el máximo entre superficies; el dominio real sigue
    siendo por forma."""

    lexical_unit: str
    status: LexicalStatus | None = None
    mastery: float = 0.0
    recall: float = 0.0
    surface_count: int = 0
    mastered_surfaces: int = 0
    recognized: bool = False
    produced: bool = False
    transfer: bool = False
    production_count: int = 0
    exposure_count: int = 0


class DictionaryUsageOut(BaseModel):
    """Marca de uso/aprendizaje de una consulta al diccionario (V3.30)."""

    tracked: bool = False
    surface: DictionarySurfaceUsageOut | None = None
    unit: DictionaryUnitUsageOut | None = None


class DictionarySenseOut(BaseModel):
    """Sentido declarado de una unidad léxica (V3.44).

    Contenido generado por el modelo local y cacheado (`dictionary_entries` /
    `dictionary_reverse_entries`): cada sentido declara su categoría gramatical
    (`pos`) y una etiqueta corta (`gloss`). Es lo que permite que el scoring
    semántico deje de depender de una única `pos` global.
    """

    pos: str = ""
    gloss: str = ""


class DictionaryEntryOut(BaseModel):
    """Entrada del diccionario de consulta (V3.30).

    `definition`/`translation`/`pos` vienen de la caché global (generadas por el
    modelo local, Fase B). Cuando el modelo no está disponible o aún no se ha
    generado, `definition_source="none"` y `definition=null`: la respuesta se
    sirve igualmente con la frase de ejemplo y la marca de uso."""

    word: str
    kind: str = ""
    cefr: str = ""
    definition_source: Literal["llm", "none"] = "none"
    pos: str = ""
    definition: str | None = None
    translation: str | None = None
    # V3.39 (diccionario reversible): dirección servida y alternativas de la
    # búsqueda inversa. En `es-en`, `translation` es el equivalente INGLÉS y
    # `alternatives` las otras traducciones encontradas en la inversa
    # instantánea (sin la principal). En `en-es` siempre `[]`.
    direction: Literal["en-es", "es-en"] = "en-es"
    alternatives: list[str] = Field(default_factory=list)
    # V3.38: enunciado situacional (frase de escenario con un hueco `_____`) del
    # 4.º peldaño de la escalera de recall. `None` si el generador no lo produjo.
    situation: str | None = None
    # V3.44: sentidos declarados de la unidad (`[{pos, gloss}]`). Contenido
    # aditivo que explica la adecuación semántica; `[]` si el generador no los
    # dio (el scoring degrada a `unknown`, que nunca bloquea).
    senses: list[DictionarySenseOut] = Field(default_factory=list)
    example: DictionaryExampleOut | None = None
    usage: DictionaryUsageOut


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


# ---------------------------------------------------------------------------
# Paso Recognition del drill (V3.33, eslabón 2 del puente Dictionary → Learning).
# MCQ definición ↔ palabra servido y puntuado por el backend (premisa 21): el GET
# nunca expone la correcta; el POST la recomputa y devuelve `correct_index` solo
# al alumno que ya respondió. Evidencia SOLO informativa (evento `learning_events`
# `drill:<word>:recognition:ok|ko`): no escribe en `vocabulary` ni mueve mastery.
# ---------------------------------------------------------------------------


class RecognitionQuestionOut(BaseModel):
    """Pregunta del paso Recognition (V3.33).

    `available=false` con `options=[]` es la degradación controlada cuando la
    palabra no tiene entrada en la caché global o no hay distractores
    suficientes: el peldaño muestra aviso y no rompe la escalera.

    V3.33.1: `question_id` es un nonce por intento (seed del barajado) que el
    cliente reenvía en el POST; no es la respuesta correcta ni un dato del
    alumno, solo rompe la posición fija de la correcta entre intentos.
    """

    word: str
    available: bool
    options: list[str] = Field(default_factory=list)
    question_id: str = ""


class RecognitionAttemptIn(BaseModel):
    """Intento del paso Recognition (V3.33): el cliente solo envía qué opción
    eligió (`selected_index`) y el `question_id` que sirvió el GET (V3.33.1,
    seed para reconstruir la misma permutación). Nunca declara acierto
    (premisa 21)."""

    word: str = Field(min_length=1, max_length=120)
    selected_index: int = Field(ge=0)
    question_id: str = Field(default="", max_length=64)


class RecognitionAttemptOut(BaseModel):
    """Resultado puntuado por el servidor del paso Recognition (V3.33).

    `correct_index` se revela solo tras responder (para mostrar la opción
    correcta en el feedback del fallo).
    """

    word: str
    correct: bool
    correct_index: int
    selected_index: int


# ---------------------------------------------------------------------------
# Paso Recall del drill (V3.34, Recall 2.0). Camino INVERSO a Recognition: el
# alumno ve el SIGNIFICADO (cue) y teclea la palabra. El GET nunca expone la
# forma esperada; el POST la revela tras puntuar (premisa 21). A diferencia de
# Recognition, el acierto SÍ deja señal léxica (recall + FSRS), pero NUNCA
# cuenta como producción.
# ---------------------------------------------------------------------------


class RecallPromptOut(BaseModel):
    """Cue del paso Recall (V3.34; peldaños graduados en V3.37).

    `available=false` con `cue=""` es la degradación controlada cuando la
    palabra no tiene entrada en la caché global o no hay contenido para el
    peldaño pedido (traducción ausente, definición circular o frase de corpus
    inexistente): el peldaño muestra aviso y no rompe Sentence. Nunca incluye la
    forma esperada.

    V3.37: `cue_kind` admite el tercer peldaño (`cloze`, con la frase en blanco
    como `cue`) y el payload gana `support_level` (apoyo que declara el peldaño
    servido: `cued`/`cued`/`guided`/`guided`; vacío si no hay peldaño).

    V3.38: `cue_kind` admite el cuarto peldaño (`situation`, el enunciado
    situacional autorado con hueco `_____`, servido desde el contrato de
    contenido de la caché).
    """

    word: str
    available: bool
    cue: str = ""
    cue_kind: str = ""  # "translation" | "definition" | "cloze" | "situation" | ""
    support_level: str = ""


class RecallAttemptIn(BaseModel):
    """Intento del paso Recall (V3.34): el cliente envía la palabra tecleada.

    Nunca declara acierto (premisa 21): el servidor compara con la diana.
    V3.36: `response_time_ms` es la latencia medida por el cliente (ms desde que
    ve el cue hasta que envía). Opcional y aditiva: sin ella el evento se
    registra igual, con latencia no medida (NULL).

    V3.37: `cue` es el peldaño que el cliente dice que le sirvieron
    (`translation`/`definition`/`cloze`; vacío = cliente antiguo, escalera por
    defecto de V3.36). El servidor lo RE-DERIVA y puntúa igual: un peldaño no
    soportado o sin contenido para la palabra responde 422 sin evento.

    V3.38: `cue` admite también `situation`.
    """

    word: str = Field(min_length=1, max_length=120)
    answer: str = Field(default="", max_length=120)
    cue: str = Field(default="", max_length=32)
    response_time_ms: int | None = Field(
        default=None, ge=0, le=600_000
    )


class RecallAttemptOut(BaseModel):
    """Resultado puntuado por el servidor del paso Recall (V3.34).

    `expected` se revela solo tras responder (feedback del fallo y confirmación
    del acierto). `delayed` indica que el intento acreditó la recuperación
    demorada existente (superó el intervalo de retención); `recall_days` es el
    nº de días distintos con recall tras este intento.

    V3.36: `error_type` clasifica el intento (taxonomía de
    `services.evidence.RECALL_ERROR_TYPES`) para que el tutor pueda distinguir
    "no lo sabe" de "lo sabe y lo escribió mal" sin cambiar el scoring: una
    errata sigue siendo `correct=false`.
    """

    word: str
    correct: bool
    expected: str
    delayed: bool = False
    recall_days: int = 0
    error_type: str = ""


# ---------------------------------------------------------------------------
# Actividad de ESCRITURA del drill (V3.39, Fase 3): cierra la modalidad
# `written_production` del motor de tarea óptima. El alumno escribe una frase
# PROPIA que use la palabra objetivo (producción con el mínimo andamiaje: la
# palabra se muestra, la frase no). Determinista y sin LLM: el servidor
# comprueba la alineación de la unidad y la longitud mínima, así que el cliente
# nunca declara acierto (premisa 21). El drill no declara dominio (D5/E3).
# ---------------------------------------------------------------------------


class WriteAttemptIn(BaseModel):
    """Intento del paso Write (V3.39): el cliente envía la frase escrita.

    `response_time_ms` es la latencia medida por el cliente (ms desde que la
    consigna queda visible hasta que envía); opcional y observacional.
    """

    word: str = Field(min_length=1, max_length=120)
    text: str = Field(default="", max_length=MAX_WRITE_CHARS)
    response_time_ms: int | None = Field(default=None, ge=0, le=600_000)


class WriteAttemptOut(BaseModel):
    """Resultado puntuado por el servidor del paso Write (V3.39).

    - `used_word`: la unidad objetivo quedó alineada en la frase escrita;
    - `word_count`: nº de palabras de la frase (longitud mínima declarada en
      `services.lexicon.WRITE_MIN_WORDS`);
    - `passed` = `used_word` AND longitud mínima: es lo que acredita la
      modalidad `written_production` (`writing_prod += 1` + evidencia con
      `activity_id="drill:write"`).

    `error_type` clasifica el intento (`services.evidence.WRITE_ERROR_TYPES`)
    sin cambiar el scoring.
    """

    word: str
    text: str
    used_word: bool
    word_count: int
    passed: bool
    error_type: str = ""


class TransferContextOut(BaseModel):
    """Consigna de TRANSFERENCIA a un contexto nuevo (V3.40 → V3.47, solo lectura).

    El contexto (`context_id`) es el del ledger: se registra con el intento y es
    lo que permite acreditar la transferencia real. `available` es siempre `True`
    con el banco curado; se mantiene por simetría con los demás GET del drill.

    V3.43 (P1-01): la consigna da un ESCENARIO y un objetivo comunicativo, y
    NUNCA contiene la unidad objetivo. `communicative_goal`/`discourse_type`
    (aditivos) explican el tipo de producción pedida.

    V3.47: `cefr`/`difficulty_vector`/`difficulty` (aditivos) declaran el nivel y
    la carga del contexto servido.

    V3.50: `skills` (aditivo) declara las competencias que ejercita el contexto
    servido, con el vocabulario `services.transfer.CONTEXT_SKILLS`.
    """

    word: str
    context_id: str = ""
    topic: str = ""
    prompt: str = ""
    available: bool = True
    exhausted: bool = False
    communicative_goal: str = ""
    discourse_type: str = ""
    # V3.46 (P1-03): condición de recuperación SERVIDA (derivada por el servidor
    # del estado de evidencia; aditiva). `required_target=False` en
    # `open_context` (la unidad no es obligatoria); `unscaffolded=True` en las
    # condiciones que acreditan transferencia no andamiada.
    condition: str = ""
    required_target: bool = True
    unscaffolded: bool = False
    # V3.47: nivel CEFR del contexto servido y su carga declarada
    # (`lexical`/`syntax`/`discourse`/`interaction`), más el escalar derivado.
    # Aditivos: sirven para explicar la elección y ajustarla al alumno.
    cefr: str = ""
    difficulty_vector: dict[str, int] = Field(default_factory=dict)
    difficulty: int = 0
    # V3.50: competencias que ejercita el contexto servido (aditivo). Es la
    # INTENCIÓN del escenario (`context_skills`), no la modalidad evaluada.
    skills: list[str] = Field(default_factory=list)
    # V3.51 (P1-01/P1-02, Task/Skill semantics): dimensiones explícitas de la
    # tarea y de la dificultad (aditivas). `target_skill` es lo que la tarea
    # quiere provocar; `assessed_skill`/`assessment_mode` lo que puede MEDIR
    # (el transfer se entrega por texto: producción escrita); `item_level` es el
    # techo del ítem y `learner_level` el suelo demostrado del alumno.
    target_skill: str = ""
    assessed_skill: str = ""
    assessment_mode: str = ""
    item_level: str = ""
    learner_level: str = ""
    skill_priorities: dict[str, float] = Field(default_factory=dict)


class TransferAttemptIn(BaseModel):
    """Intento del paso Transfer (V3.40).

    `context_id` es el contexto servido por `TransferContextOut` (si falta, el
    servidor lo deriva del banco: nunca queda sin contexto).
    """

    word: str = Field(min_length=1, max_length=120)
    text: str = Field(default="", max_length=MAX_WRITE_CHARS)
    context_id: str = Field(default="", max_length=120)
    response_time_ms: int | None = Field(default=None, ge=0, le=600_000)


class TransferAttemptOut(BaseModel):
    """Resultado puntuado por el servidor del paso Transfer (V3.40 → V3.43).

    `passed` = unidad alineada AND longitud mínima: acredita la modalidad
    `spontaneous_use` con evidencia `activity_id="drill:transfer"` y el
    `context_id` del contexto nuevo. `error_type` reutiliza la taxonomía
    observacional de `TRANSFER_ERROR_TYPES`.

    V3.43 (P1-02): `passed` se mantiene como contrato histórico y `lexical_transfer`
    lo explicita; `semantic_fit`/`adequacy` añaden la capa SEPARADA de adecuación
    semántica (proxy determinista, advisory). `semantic_fit` es `None` cuando no
    es determinable (sin POS declarada). Un uso léxicamente correcto pero
    sospechoso mantiene `passed=True`.

    V3.44 (P1-01/P1-02): `adequacy` gana el valor `incorrect`
    (`fit`/`suspect`/`incorrect`/`unknown`). Solo `incorrect` bloquea el clean
    success y guarda `error_type="semantic_mismatch"`; `suspect` es advisory y
    guarda `error_type="semantic_doubt"` (no bloquea). La decisión usa los
    SENTIDOS de la unidad, no la `pos` global.
    """

    word: str
    text: str
    context_id: str = ""
    used_word: bool
    word_count: int
    passed: bool
    error_type: str = ""
    lexical_transfer: bool = False
    semantic_fit: bool | None = None
    adequacy: str = ""
    # V3.46 (P1-03): condición de recuperación aplicada al intento (derivada por
    # el servidor) y si la unidad era obligatoria. En `open_context`
    # (`required_target=False`) no usarla NO es un fallo ni se registra como
    # evidencia: `passed` refleja solo el transfer léxico del texto entregado.
    condition: str = ""
    required_target: bool = True
    # V3.51 (P1-01): semántica explícita del intento. El eje sigue siendo
    # `spontaneous_use`, pero la modalidad que el drill puede EVALUAR es escrita
    # (la actividad se entrega por texto).
    target_skill: str = ""
    assessed_skill: str = ""
    assessment_mode: str = ""
