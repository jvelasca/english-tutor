"""Esquemas Pydantic de listening."""
from __future__ import annotations

from pydantic import BaseModel, Field


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
    realized_difficulty: int = 0
    realization: dict[str, dict[str, int | bool]] = Field(default_factory=dict)


class ListeningAnswerRequest(BaseModel):
    question_id: str
    answer_index: int = Field(ge=0)
    response_time_ms: int | None = None
    replay_count: int = Field(default=0, ge=0)


class ListeningAnswerResponse(BaseModel):
    question_id: str
    correct: bool
    correct_index: int
    level: str
    skill: str = ""
    difficulty: int = 1
    realized_difficulty: int = 1


class ListeningLevelOut(BaseModel):
    level: str
    total: int
    mastered: int
    completed: bool


class ListeningStats(BaseModel):
    attempts: int
    correct: int
    accuracy: float | None = None
    level: str
    completed: bool
    levels: list[ListeningLevelOut]


class ListeningSubskillOut(BaseModel):
    skill: str
    attempts: int
    correct: int
    accuracy: float | None = None
    first_pass_accuracy: float | None = None
    avg_response_ms: float | None = None
    avg_replay_count: float
    automaticity: float | None = None
    review_due: bool
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


class ListeningDiagnostic(BaseModel):
    subskills: list[ListeningSubskillOut]
    weak: list[str]
    recommendation: str
    first_pass_accuracy: float | None = None
    automaticity: float | None = None
    by_difficulty: list[ListeningDifficultyOut] = Field(default_factory=list)
    by_topic: list[ListeningTopicOut] = Field(default_factory=list)
    trend: ListeningTrend
    recurrence: ListeningRecurrence
    retention: ListeningRetention
    bank_version: str = ""
    # Resumen de integridad de evidencia: cuántos intentos tienen audio verificado
    # (realización = declaración) y cuántos presentan brecha (metadata no respaldada).
    realization: dict = Field(default_factory=dict)
