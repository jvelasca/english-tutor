"""Esquemas Pydantic de listening."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ListeningAudioVariant(BaseModel):
    """Una variante de velocidad de la escalera de audio (P1.9)."""

    variant: str
    speech_rate: float
    label: str


class ListeningQuestion(BaseModel):
    id: str
    level: str
    skill: str
    difficulty: int
    difficulty_vector: dict[str, int] = Field(default_factory=dict)
    script: str
    question: str
    options: list[str]
    # Metadatos de audio de primer nivel (defaults seguros para el banco heredado).
    audio_id: str = ""
    duration: float = 0.0
    speaker_id: str = ""
    accent: str = "neutral"
    speech_rate: float = 0.0
    transcript: str = ""
    clean_transcript: str = ""
    noise_level: int = 0
    repetition_policy: str = "none"
    topic: str = ""
    # True si este ítem tiene audio de referencia reproducible (transcript/script no
    # vacío y el sintetizador Piper disponible). El frontend usa esto para decidir
    # entre reproducir el audio TTS pre-renderizado o degradar al TTS en vivo.
    audio_ready: bool = False
    # Modelo de realización (V1.14): tipo de audio y separación entre la dificultad
    # declarada y la realmente realizada por el audio servido.
    audio_type: str = "tts"
    # Contexto comunicativo del ítem (ver LISTENING_CONTEXTS); vacío en el banco
    # heredado que no lo declara.
    context: str = ""
    realized_difficulty: int = 0
    realization: dict[str, dict[str, int | bool]] = Field(default_factory=dict)
    # Capa cognitiva de la taxonomía de listening (F-C1, V3.26): recognition /
    # comprehension / inference, derivada de `skill`; None en tareas de producción.
    layer: str | None = None
    # Escalera de variantes de velocidad (P1.9): lista ordenada slow/normal/fast y
    # la variante servida por defecto (siempre "normal", que preserva el cache).
    variants: list[ListeningAudioVariant] = Field(default_factory=list)
    default_variant: str = "normal"
    # Micro-flujo por ítem (V3.27, Listening Engine 4.0): `flow` es la secuencia de
    # pasos pedagógicos [{stage, task, transcript_state_inicial, allow_skip}] y
    # `transcript_policy` el contrato de revelado (ver services/listening_flow.py).
    # Vacíos para consumidores antiguos que no piden el micro-flujo.
    flow: list[dict] = Field(default_factory=list)
    transcript_policy: dict = Field(default_factory=dict)
    # Timings gruesos de frase (V3.28, Bloque D): lista
    # [{index, start, end, text, sync: "coarse_heuristic"}]. Heurísticos (reparto
    # proporcional de `duration` por peso textual de cada frase), NUNCA alineación
    # acústica; presentes solo cuando el ítem tiene micro-flow y declara `duration`.
    sentence_timings: list[dict] = Field(default_factory=list)
    # Timings por palabra (V3.29, Fase 3): lista [{index, text, start, end,
    # sentence}] generada OFFLINE por el motor `word_alignment_proxy` sobre el WAV
    # de la voz default y variante `normal` (sidecar `{wav}.words.json`). Es señal
    # ASR (`sync: "asr_word_proxy"` en el sidecar), nunca verdad acústica; si el
    # sidecar no existe o la cobertura del ASR es baja, la lista es vacía y el
    # frontend degrada al sync de frase. `sentence` es el índice de la frase de
    # `sentence_timings` que contiene la palabra (`-1` sin frases/duration).
    word_timings: list[dict] = Field(default_factory=list)
    # ítem derivado bottom-up (V3.28, Bloque C): `derived` marca que el contenido
    # se derivó determinísticamente del corpus (no entra en el gate); `derived_from`
    # es el id del ítem padre cuyo audio reutiliza; `task_type` identifica la tarea
    # derivada (cloze/partial_dictation/segmentation). Opcionales y retrocompatibles:
    # los ítems del banco no los declaran.
    derived: bool = False
    derived_from: str = ""
    task_type: str = ""


class ListeningAnswerRequest(BaseModel):
    question_id: str
    answer_index: int = Field(ge=0)
    response_time_ms: int | None = None
    replay_count: int = Field(default=0, ge=0)
    # Evidencia ampliada (V3.27, Fase 1): metadatos de apoyo del intento. `layer`
    # es informativo: el backend lo recalcula del skill (fuente de verdad). Los
    # demás campos describen con qué apoyo se respondió.
    layer: str = ""
    speed_used: str = "normal"
    stage: str = ""
    transcript_used: str = ""
    segments_replayed: int = Field(default=0, ge=0)


class ListeningAnswerResponse(BaseModel):
    question_id: str
    correct: bool
    correct_index: int
    level: str
    skill: str = ""
    difficulty: int = 1
    realized_difficulty: int = 1


class ListeningProductionRequest(BaseModel):
    """Cuerpo de una tarea de producción (dictado/shadowing)."""

    question_id: str
    transcript: str
    # Evidencia ampliada (V3.27, Fase 1): fase del micro-flujo y apoyo usado.
    stage: str = ""
    transcript_used: str = ""
    speed_used: str = "normal"
    # Señales auxiliares del Shadowing 2.0 (V3.28, Bloque E): informativas,
    # opcionales y calculadas por el cliente desde el audio grabado. Se persisten
    # en el intento pero SIN peso de mastery (el scoring determinista del
    # shadowing sigue siendo la comparación del texto oído con la referencia).
    shadowing_duration_ms: int | None = None
    shadowing_speech_rate: float | None = None


class ListeningProductionResult(BaseModel):
    """Resultado de una tarea de producción, con scoring determinista (0..100)."""

    question_id: str
    task_type: str
    correct: bool
    score: int
    word_accuracy: int
    phonetic_score: int
    phoneme_accuracy_proxy: int
    breakdown: dict
    reference: str
    level: str
    skill: str


class ListeningGate(BaseModel):
    """Puerta de ruta de un nivel de listening: qué exige la evidencia para
    declarar la ruta superada y qué valores alcanza hoy.

    `passed` es cierto solo si `blockers` está vacío. Los `*_required` codifican
    los umbrales pedagógicos (cobertura, precisión, variedad y checkpoint);
    el resto de campos son los valores alcanzados con la evidencia actual."""

    passed: bool = False
    total: int = 0
    mastered: int = 0
    coverage_pct: float = 0.0
    coverage_required_pct: float = 80.0
    accuracy: float | None = None
    accuracy_required: float = 70.0
    topics: int = 0
    topics_required: int = 0
    subskills: int = 0
    subskills_required: int = 0
    checkpoint: int = 0
    checkpoint_required: int = 0
    blockers: list[str] = Field(default_factory=list)


class ListeningRouteRetention(BaseModel):
    """Resumen de retención retardada estable de una ruta (Constitución §6.3).

    `retention_rate` es delayed/immediate (None sin datos); `stable` exige ratio ≥
    `ROUTE_RETENTION_STABLE_RATIO` y al menos una re-exposición ≥ 7 días."""

    retention_rate: float | None = None
    stable: bool = False
    long_delayed_exposures: int = 0


class ListeningLevelOut(BaseModel):
    level: str
    total: int
    mastered: int
    completed: bool
    coverage_pct: float | None = None
    accuracy: float | None = None
    # Estado de la puerta de ruta (None en respuestas de versiones antiguas).
    gate: ListeningGate | None = None
    # Estado pedagógico de la ruta (Constitución §2.1): not_started /
    # developing / functional / demonstrated; y resumen de su retención.
    state: str = "not_started"
    retention: ListeningRouteRetention | None = None
    # Práctica extra generada (V3.6): `total`/`mastered` incluyen los ítems
    # extra activados; `base_total`/`base_mastered` son el banco curado oficial
    # (el único que decide la puerta y el estado). `extras` es el nº de ítems
    # generados activados y `extras_mastered` los ya acertados.
    base_total: int = 0
    base_mastered: int = 0
    extras: int = 0
    extras_mastered: int = 0


class ListeningItemOut(BaseModel):
    """Una frase del pool de una ruta con su estado para un usuario (panel)."""

    question_id: str
    level: str
    script: str
    topic: str = ""
    skill: str = ""
    layer: str | None = None
    difficulty: int = 1
    attempts: int = 0
    state: str
    # "base" = banco curado oficial; "generated" = práctica extra generada.
    source: str = "base"


class ListeningLevelItemsOut(BaseModel):
    """Estado por frase de un nivel CEFR + resumen de contadores."""

    level: str
    total: int
    mastered: int
    failed: int
    unseen: int
    completed: bool
    items: list[ListeningItemOut]
    # Puerta de ruta del nivel: `completed` la refleja y `gate` permite al panel
    # explicar por qué dominar frases aún no certifica la ruta.
    gate: ListeningGate | None = None


class ListeningStats(BaseModel):
    attempts: int
    correct: int
    accuracy: float | None = None
    level: str
    completed: bool
    levels: list[ListeningLevelOut]


class ListeningSubskillOut(BaseModel):
    skill: str
    # Capa cognitiva de la taxonomía de listening (F-C1, V3.26); None en tareas
    # de producción (dictation/shadowing).
    layer: str | None = None
    attempts: int
    correct: int
    accuracy: float | None = None
    first_pass_accuracy: float | None = None
    avg_response_ms: float | None = None
    avg_replay_count: float
    automaticity: float | None = None
    review_due: bool
    # Media (0..100) del score continuo de las tareas de producción (dictado/
    # shadowing) de esta sub-destreza, o None si no hay evidencia de producción.
    mean_score: float | None = None
    # True si la evidencia de esta sub-destreza proviene de ítems cuyo audio no
    # realiza el factor que la respalda (p. ej. multiple_speakers con una sola voz).
    realization_gap: bool = False


class ListeningDifficultyOut(BaseModel):
    difficulty: int
    attempts: int
    correct: int
    accuracy: float | None = None


class ListeningTopicOut(BaseModel):
    topic: str
    attempts: int
    correct: int
    accuracy: float | None = None


class ListeningLayerOut(BaseModel):
    """Precisión agregada de una capa cognitiva de la taxonomía (F-C1, V3.26).

    Una entrada por capa (recognition/comprehension/inference), siempre presente
    en el diagnóstico aunque la capa no tenga evidencia (la UI puede explicar que
    falta practicarla)."""

    layer: str
    attempts: int
    correct: int
    accuracy: float | None = None


class ListeningTrend(BaseModel):
    recent_accuracy: float | None = None
    prior_accuracy: float | None = None
    delta: float | None = None
    direction: str


class ListeningRecurrence(BaseModel):
    questions_seen: int
    retried: int
    recovered: int
    retry_rate: float | None = None
    recovery_rate: float | None = None


class ListeningRetentionBucket(BaseModel):
    bucket: str
    attempts: int
    correct: int
    accuracy: float | None = None


class ListeningRetention(BaseModel):
    total_questions: int
    immediate_accuracy: float | None = None
    delayed_accuracy: float | None = None
    retention_rate: float | None = None
    by_bucket: list[ListeningRetentionBucket] = Field(default_factory=list)


class ListeningRealizationSummary(BaseModel):
    attempts: int
    verified: int
    gap: int


class ListeningResilienceDimension(BaseModel):
    dimension: str
    attempts: int
    correct: int
    accuracy: float | None = None


class ListeningResilience(BaseModel):
    dimensions: list[ListeningResilienceDimension] = Field(default_factory=list)
    main_weakness: str | None = None
    recommendation: str = ""


# --- Práctica extra generada (V3.6) ------------------------------------------


class ListeningAddExtrasRequest(BaseModel):
    """Cuerpo del POST que pide añadir `count` ítems extra a una ruta."""

    count: int = Field(default=10, ge=1, le=100)


class ListeningExtrasJobOut(BaseModel):
    """Estado de un trabajo de generación en segundo plano.

    `status` ∈ {running, done, error}. Mientras corre, el frontend hace polling;
    al terminar, `added` son los ids activados en la ruta del usuario.
    """

    job_id: str
    status: str = "running"
    level: str = ""
    requested: int = 0
    added: list[str] = Field(default_factory=list)
    error: str = ""


class ListeningRouteExtrasOut(BaseModel):
    """Ítems extra activados en una ruta (V3.6)."""

    level: str
    total: int = 0
    question_ids: list[str] = Field(default_factory=list)


class ListeningDiagnostic(BaseModel):
    subskills: list[ListeningSubskillOut]
    weak: list[str]
    recommendation: str
    first_pass_accuracy: float | None = None
    automaticity: float | None = None
    by_difficulty: list[ListeningDifficultyOut] = Field(default_factory=list)
    by_topic: list[ListeningTopicOut] = Field(default_factory=list)
    # Precisión por capa cognitiva de la taxonomía (F-C1, V3.26): una entrada por
    # capa en orden recognition → comprehension → inference, siempre presente.
    by_layer: list[ListeningLayerOut] = Field(default_factory=list)
    trend: ListeningTrend
    recurrence: ListeningRecurrence
    retention: ListeningRetention
    bank_version: str = ""
    # Resumen de integridad de evidencia: cuántos intentos tienen audio verificado
    # (realización = declaración) y cuántos presentan brecha (metadata no respaldada).
    realization: dict = Field(default_factory=dict)
    # Indicador de resiliencia auditiva (Listening 2.0): precisión por condición de
    # escucha (clara → natural → conectada → rápida → ruido → acentos).
    resilience: ListeningResilience = Field(default_factory=ListeningResilience)
    # Perfil auditivo (V3.27, Listening Engine 4.0): capa objetivo e intervención
    # recomendada (casos A-D de la especificación). Vacío si el diagnóstico previo
    # no lleva `profile` (retrocompatible).
    profile: dict = Field(default_factory=dict)
