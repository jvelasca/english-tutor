"""Banco de preguntas de listening y puntuación determinista (puro)."""
from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError, computed_field

from services.curriculum import LISTENING_BANK_VERSION

LISTENING_SUBSKILLS: tuple[str, ...] = (
    "gist",
    "detail",
    "inference",
    "attitude",
    "vocabulary",
    "numbers",
    "speaker_intention",
    "fast_speech",
    "connected_speech",
    "dictation",
    "shadowing",
    "multiple_speakers",
    "note_taking",
    "prediction",
    "sequencing",
)

# Vector de dificultad de 8 dimensiones. La dificultad escalar `difficulty` (1-6)
# ya NO se almacena: se deriva como la media redondeada de este vector
# (ver `difficulty_from_vector`), de modo que la coherencia media↔difficulty se
# cumple por construcción.
DIFFICULTY_FACTORS: tuple[str, ...] = (
    "speed",
    "vocabulary",
    "accent",
    "syntactic",
    "length",
    "speaker_count",
    "noise",
    "connected_speech",
)


def difficulty_from_vector(vector: dict[str, int]) -> int:
    """Deriva el escalar de dificultad (1..6) como la media redondeada del vector.

    Es la única fuente de verdad de `difficulty`. Usa `round` (redondeo al par de
    Python) y clampa el resultado a [1, 6]. Un vector vacío se trata como dificultad
    mínima."""
    if not vector:
        return 1
    mean = round(sum(vector.values()) / len(vector))
    return max(1, min(6, mean))


# Parámetros de la métrica de automaticidad (fluidez procesal, 0..1).
AUTOMATICITY_REPLAY_PENALTY = 0.2  # resta por cada replay promedio
AUTOMATICITY_LATENCY_THRESHOLD_MS = 2500.0  # latencia a partir de la cual penaliza
AUTOMATICITY_LATENCY_PENALTY = 0.1  # resta por cada 1000 ms sobre el umbral
AUTOMATICITY_LATENCY_CAP = 0.5  # penalización máxima por latencia


def automaticity_from_metrics(
    avg_replay_count: float | None,
    avg_response_ms: float | None,
    *,
    attempts: int,
) -> float | None:
    """Automaticidad (0..1) como señal de fluidez procesal.

    Parte de 1.0 y aplica dos penalizaciones:
    - replays: cada repetición extra indica comprensión no automatizada
      (`AUTOMATICITY_REPLAY_PENALTY` por replay promedio).
    - latencia: responder por encima de `AUTOMATICITY_LATENCY_THRESHOLD_MS` resta de
      forma lineal, con tope `AUTOMATICITY_LATENCY_CAP`.

    Devuelve None cuando no hay intentos (sin señal). No es un score CEFR directo;
    es solo una señal expuesta."""
    if attempts == 0:
        return None
    score = 1.0
    if avg_replay_count is not None:
        score -= AUTOMATICITY_REPLAY_PENALTY * avg_replay_count
    if avg_response_ms is not None:
        over = avg_response_ms - AUTOMATICITY_LATENCY_THRESHOLD_MS
        if over > 0:
            score -= min(
                AUTOMATICITY_LATENCY_CAP,
                over / 1000.0 * AUTOMATICITY_LATENCY_PENALTY,
            )
    return round(max(0.0, min(1.0, score)), 3)


class ListeningAsset(BaseModel):
    """Ítem de listening (esquema versionado del banco de contenido).

    `difficulty` es un campo derivado del `difficulty_vector` (ver
    `difficulty_from_vector`); cualquier clave `"difficulty"` presente en un dict de
    entrada queda ignorada por ser redundante."""

    id: str
    level: str
    skill: str
    difficulty_vector: dict[str, int]
    script: str
    question: str
    options: list[str]
    answer_index: int = Field(ge=0)

    # Metadatos de audio de primer nivel (con defaults seguros para no romper el
    # banco existente, que no los declara).
    audio_id: str = ""
    duration: float = 0.0
    speaker_id: str = ""
    accent: str = "neutral"
    speech_rate: float = 0.0
    transcript: str = ""
    clean_transcript: str = ""
    noise_level: int = Field(default=0, ge=0, le=5)
    repetition_policy: str = "none"

    @computed_field
    @property
    def difficulty(self) -> int:
        return difficulty_from_vector(self.difficulty_vector)


QUESTION_BANK: list[dict] = [
    {
        "id": "l1",
        "level": "A1",
        "skill": "numbers",
        "difficulty_vector": {
            "speed": 1,
            "vocabulary": 1,
            "accent": 1,
            "syntactic": 1,
            "length": 1,
            "speaker_count": 1,
            "noise": 1,
            "connected_speech": 1,
        },
        "script": "Tom gets up at seven o'clock and has toast for breakfast.",
        "question": "What time does Tom get up?",
        "options": ["At six", "At seven", "At eight", "At nine"],
        "answer_index": 1,
    },
    {
        "id": "l2",
        "level": "A1",
        "skill": "detail",
        "difficulty_vector": {
            "speed": 2,
            "vocabulary": 2,
            "accent": 2,
            "syntactic": 2,
            "length": 2,
            "speaker_count": 1,
            "noise": 1,
            "connected_speech": 1,
        },
        "script": "Maria goes to the supermarket every Saturday morning.",
        "question": "When does Maria go to the supermarket?",
        "options": ["On Sunday", "On Saturday", "On Friday", "On Monday"],
        "answer_index": 1,
    },
    {
        "id": "l3",
        "level": "A1",
        "skill": "detail",
        "difficulty_vector": {
            "speed": 1,
            "vocabulary": 1,
            "accent": 1,
            "syntactic": 1,
            "length": 1,
            "speaker_count": 1,
            "noise": 1,
            "connected_speech": 1,
        },
        "script": "The children are playing football in the park.",
        "question": "What are the children doing?",
        "options": ["Reading", "Swimming", "Playing football", "Sleeping"],
        "answer_index": 2,
    },
    {
        "id": "l4",
        "level": "A2",
        "skill": "detail",
        "difficulty_vector": {
            "speed": 3,
            "vocabulary": 3,
            "accent": 3,
            "syntactic": 3,
            "length": 3,
            "speaker_count": 1,
            "noise": 2,
            "connected_speech": 3,
        },
        "script": "John bought a blue shirt and a pair of black shoes.",
        "question": "What did John buy?",
        "options": [
            "A blue shirt and black shoes",
            "A red jacket",
            "A white hat",
            "A green bag",
        ],
        "answer_index": 0,
    },
    {
        "id": "l5",
        "level": "A2",
        "skill": "inference",
        "difficulty_vector": {
            "speed": 3,
            "vocabulary": 5,
            "accent": 3,
            "syntactic": 4,
            "length": 5,
            "speaker_count": 1,
            "noise": 3,
            "connected_speech": 5,
        },
        "script": "Anna prefers to travel by train because it is cheaper than flying.",
        "question": "Why does Anna prefer the train?",
        "options": [
            "It is faster",
            "It is cheaper",
            "It is more comfortable",
            "It is safer",
        ],
        "answer_index": 1,
    },
    {
        "id": "l6",
        "level": "A2",
        "skill": "numbers",
        "difficulty_vector": {
            "speed": 2,
            "vocabulary": 4,
            "accent": 3,
            "syntactic": 3,
            "length": 3,
            "speaker_count": 1,
            "noise": 2,
            "connected_speech": 3,
        },
        "script": "The meeting will start at half past nine and finish at noon.",
        "question": "How long does the meeting last?",
        "options": [
            "One hour",
            "Two hours and a half",
            "Three hours",
            "Half an hour",
        ],
        "answer_index": 1,
    },
    {
        "id": "l7",
        "level": "B1",
        "skill": "inference",
        "difficulty_vector": {
            "speed": 4,
            "vocabulary": 6,
            "accent": 4,
            "syntactic": 5,
            "length": 6,
            "speaker_count": 1,
            "noise": 5,
            "connected_speech": 6,
        },
        "script": "Despite the heavy rain, the team decided to continue the match.",
        "question": "What did the team decide?",
        "options": ["To stop", "To continue", "To postpone", "To go home"],
        "answer_index": 1,
    },
    {
        "id": "l8",
        "level": "B1",
        "skill": "inference",
        "difficulty_vector": {
            "speed": 6,
            "vocabulary": 6,
            "accent": 6,
            "syntactic": 6,
            "length": 6,
            "speaker_count": 3,
            "noise": 6,
            "connected_speech": 6,
        },
        "script": "If you arrive early, you will have time to review your notes.",
        "question": "What happens if you arrive early?",
        "options": [
            "You miss the review",
            "You have time to review",
            "You must wait",
            "Nothing",
        ],
        "answer_index": 1,
    },
    {
        "id": "l9",
        "level": "A1",
        "skill": "gist",
        "difficulty_vector": {
            "speed": 2,
            "vocabulary": 2,
            "accent": 2,
            "syntactic": 2,
            "length": 2,
            "speaker_count": 1,
            "noise": 1,
            "connected_speech": 1,
        },
        "script": "Sarah and Mike are planning a trip. They talk about tickets and "
        "hotels. They want to visit Paris.",
        "question": "What are they mainly talking about?",
        "options": [
            "Planning a trip",
            "Cooking dinner",
            "Fixing a car",
            "Buying clothes",
        ],
        "answer_index": 0,
    },
    {
        "id": "l10",
        "level": "A2",
        "skill": "gist",
        "difficulty_vector": {
            "speed": 3,
            "vocabulary": 4,
            "accent": 3,
            "syntactic": 5,
            "length": 5,
            "speaker_count": 1,
            "noise": 3,
            "connected_speech": 5,
        },
        "script": "Last weekend was very busy. First, we cleaned the house. Then, "
        "we went shopping and cooked a big dinner for our friends.",
        "question": "What are they mainly talking about?",
        "options": [
            "Their busy weekend",
            "A football match",
            "A problem at work",
            "The weather",
        ],
        "answer_index": 0,
    },
    {
        "id": "l11",
        "level": "A1",
        "skill": "vocabulary",
        "difficulty_vector": {
            "speed": 1,
            "vocabulary": 1,
            "accent": 1,
            "syntactic": 1,
            "length": 1,
            "speaker_count": 1,
            "noise": 1,
            "connected_speech": 1,
        },
        "script": "This restaurant is very cheap. A full meal costs only five euros.",
        "question": "Which word means 'not expensive'?",
        "options": ["Cheap", "Expensive", "Noisy", "Cold"],
        "answer_index": 0,
    },
    {
        "id": "l12",
        "level": "A2",
        "skill": "vocabulary",
        "difficulty_vector": {
            "speed": 2,
            "vocabulary": 4,
            "accent": 2,
            "syntactic": 3,
            "length": 4,
            "speaker_count": 1,
            "noise": 2,
            "connected_speech": 3,
        },
        "script": "She was delighted when she passed the exam. She could not stop "
        "smiling.",
        "question": "Which word means 'very happy'?",
        "options": ["Delighted", "Sad", "Bored", "Afraid"],
        "answer_index": 0,
    },
    {
        "id": "l13",
        "level": "A2",
        "skill": "attitude",
        "difficulty_vector": {
            "speed": 2,
            "vocabulary": 4,
            "accent": 3,
            "syntactic": 4,
            "length": 4,
            "speaker_count": 1,
            "noise": 2,
            "connected_speech": 2,
        },
        "script": "I was looking forward to the concert, but the band arrived late "
        "and only played for thirty minutes.",
        "question": "How does the speaker feel about the concert?",
        "options": ["Disappointed", "Excited", "Relieved", "Grateful"],
        "answer_index": 0,
    },
    {
        "id": "l14",
        "level": "B1",
        "skill": "attitude",
        "difficulty_vector": {
            "speed": 4,
            "vocabulary": 5,
            "accent": 4,
            "syntactic": 5,
            "length": 6,
            "speaker_count": 1,
            "noise": 6,
            "connected_speech": 6,
        },
        "script": "The manager claims the new system will save time, but I doubt it. "
        "We have heard these promises before, and nothing changed.",
        "question": "What is the speaker's attitude toward the manager's claim?",
        "options": ["Skeptical", "Enthusiastic", "Indifferent", "Proud"],
        "answer_index": 0,
    },
    {
        "id": "l15",
        "level": "B1",
        "skill": "speaker_intention",
        "difficulty_vector": {
            "speed": 4,
            "vocabulary": 5,
            "accent": 3,
            "syntactic": 4,
            "length": 4,
            "speaker_count": 1,
            "noise": 3,
            "connected_speech": 5,
        },
        "audio_id": "audio-l15",
        "duration": 7.5,
        "speaker_id": "sp1",
        "accent": "neutral",
        "speech_rate": 140.0,
        "transcript": "I was wondering if you could possibly give me a hand with "
        "the report before Friday.",
        "clean_transcript": "I was wondering if you could possibly give me a hand "
        "with the report before Friday.",
        "noise_level": 1,
        "repetition_policy": "none",
        "script": "I was wondering if you could possibly give me a hand with the "
        "report before Friday.",
        "question": "What does the speaker want?",
        "options": ["Help with a report", "A day off", "A promotion", "A new computer"],
        "answer_index": 0,
    },
    {
        "id": "l16",
        "level": "B2",
        "skill": "fast_speech",
        "difficulty_vector": {
            "speed": 6,
            "vocabulary": 6,
            "accent": 5,
            "syntactic": 6,
            "length": 6,
            "speaker_count": 4,
            "noise": 6,
            "connected_speech": 6,
        },
        "audio_id": "audio-l16",
        "duration": 4.0,
        "speaker_id": "sp1",
        "accent": "neutral",
        "speech_rate": 185.0,
        "transcript": "Gonnago to the store and grab some milk, d'you want anything "
        "else while I'm out?",
        "clean_transcript": "Going to go to the store and grab some milk. Do you want "
        "anything else while I'm out?",
        "noise_level": 3,
        "repetition_policy": "none",
        "script": "Gonnago to the store and grab some milk, d'you want anything else "
        "while I'm out?",
        "question": "What is the speaker going to do?",
        "options": ["Go to the store", "Go to work", "Go to the gym", "Go to bed"],
        "answer_index": 0,
    },
    {
        "id": "l17",
        "level": "B2",
        "skill": "connected_speech",
        "difficulty_vector": {
            "speed": 5,
            "vocabulary": 5,
            "accent": 4,
            "syntactic": 5,
            "length": 5,
            "speaker_count": 2,
            "noise": 5,
            "connected_speech": 6,
        },
        "audio_id": "audio-l17",
        "duration": 3.5,
        "speaker_id": "sp1",
        "accent": "neutral",
        "speech_rate": 170.0,
        "transcript": "Whaddaya think about the idea of meeting up this weekend?",
        "clean_transcript": "What do you think about the idea of meeting up this "
        "weekend?",
        "noise_level": 2,
        "repetition_policy": "none",
        "script": "Whaddaya think about the idea of meeting up this weekend?",
        "question": "What does 'Whaddaya' mean?",
        "options": ["What do you", "What did you", "Where do you", "Who do you"],
        "answer_index": 0,
    },
    {
        "id": "l18",
        "level": "B1",
        "skill": "dictation",
        "difficulty_vector": {
            "speed": 3,
            "vocabulary": 3,
            "accent": 3,
            "syntactic": 3,
            "length": 3,
            "speaker_count": 1,
            "noise": 2,
            "connected_speech": 3,
        },
        "audio_id": "audio-l18",
        "duration": 3.0,
        "speaker_id": "sp1",
        "accent": "neutral",
        "speech_rate": 130.0,
        "transcript": "She said she'd meet us at half past six.",
        "clean_transcript": "She said she would meet us at half past six.",
        "noise_level": 0,
        "repetition_policy": "twice",
        "script": "She said she'd meet us at half past six.",
        "question": "Which time did you hear?",
        "options": [
            "Half past six",
            "Half past seven",
            "Six o'clock",
            "Quarter past six",
        ],
        "answer_index": 0,
    },
    {
        "id": "l19",
        "level": "B1",
        "skill": "shadowing",
        "difficulty_vector": {
            "speed": 4,
            "vocabulary": 4,
            "accent": 3,
            "syntactic": 4,
            "length": 5,
            "speaker_count": 1,
            "noise": 3,
            "connected_speech": 5,
        },
        "audio_id": "audio-l19",
        "duration": 3.0,
        "speaker_id": "sp1",
        "accent": "neutral",
        "speech_rate": 130.0,
        "transcript": "Could you repeat that more slowly, please?",
        "clean_transcript": "Could you repeat that more slowly, please?",
        "noise_level": 0,
        "repetition_policy": "twice",
        "script": "Could you repeat that more slowly, please?",
        "question": "Which sentence matches what you heard?",
        "options": [
            "Could you repeat that more slowly, please?",
            "Could you speak more quietly, please?",
            "Could you repeat that louder, please?",
            "Could you say it again faster, please?",
        ],
        "answer_index": 0,
    },
    {
        "id": "l20",
        "level": "B2",
        "skill": "multiple_speakers",
        "difficulty_vector": {
            "speed": 5,
            "vocabulary": 5,
            "accent": 4,
            "syntactic": 5,
            "length": 5,
            "speaker_count": 4,
            "noise": 4,
            "connected_speech": 5,
        },
        "audio_id": "audio-l20",
        "duration": 5.5,
        "speaker_id": "sp1",
        "accent": "neutral",
        "speech_rate": 155.0,
        "transcript": "Man: 'Are we still on for lunch?' Woman: 'Sure, but I can't "
        "leave before one.'",
        "clean_transcript": "Man: Are we still on for lunch? Woman: Sure, but I can't "
        "leave before one.",
        "noise_level": 2,
        "repetition_policy": "none",
        "script": "Man: 'Are we still on for lunch?' Woman: 'Sure, but I can't leave "
        "before one.'",
        "question": "What do the speakers agree on?",
        "options": [
            "Having lunch after one",
            "Having lunch before one",
            "Skipping lunch",
            "Having dinner instead",
        ],
        "answer_index": 0,
    },
    {
        "id": "l21",
        "level": "B2",
        "skill": "note_taking",
        "difficulty_vector": {
            "speed": 5,
            "vocabulary": 5,
            "accent": 4,
            "syntactic": 5,
            "length": 5,
            "speaker_count": 2,
            "noise": 5,
            "connected_speech": 6,
        },
        "audio_id": "audio-l21",
        "duration": 6.0,
        "speaker_id": "sp1",
        "accent": "neutral",
        "speech_rate": 150.0,
        "transcript": "The museum opens at ten, closes at six, and is free on the "
        "first Sunday of each month.",
        "clean_transcript": "The museum opens at ten, closes at six, and is free on "
        "the first Sunday of each month.",
        "noise_level": 2,
        "repetition_policy": "none",
        "script": "The museum opens at ten, closes at six, and is free on the first "
        "Sunday of each month.",
        "question": "Which note is correct?",
        "options": [
            "Free entry on the first Sunday",
            "Opens at nine",
            "Closed on Sundays",
            "Entry costs ten euros",
        ],
        "answer_index": 0,
    },
    {
        "id": "l22",
        "level": "B1",
        "skill": "prediction",
        "difficulty_vector": {
            "speed": 4,
            "vocabulary": 4,
            "accent": 3,
            "syntactic": 4,
            "length": 5,
            "speaker_count": 1,
            "noise": 3,
            "connected_speech": 5,
        },
        "audio_id": "audio-l22",
        "duration": 3.5,
        "speaker_id": "sp1",
        "accent": "neutral",
        "speech_rate": 140.0,
        "transcript": "The forecast says rain all morning, so we'll probably...",
        "clean_transcript": "The forecast says rain all morning, so we will probably.",
        "noise_level": 1,
        "repetition_policy": "none",
        "script": "The forecast says rain all morning, so we'll probably...",
        "question": "How will the speaker most likely finish?",
        "options": ["stay indoors", "go to the beach", "have a picnic", "go hiking"],
        "answer_index": 0,
    },
    {
        "id": "l23",
        "level": "B1",
        "skill": "sequencing",
        "difficulty_vector": {
            "speed": 3,
            "vocabulary": 3,
            "accent": 2,
            "syntactic": 3,
            "length": 4,
            "speaker_count": 1,
            "noise": 2,
            "connected_speech": 3,
        },
        "audio_id": "audio-l23",
        "duration": 6.5,
        "speaker_id": "sp1",
        "accent": "neutral",
        "speech_rate": 135.0,
        "transcript": "First we boarded the train, then we found our seats, and "
        "finally we ordered lunch.",
        "clean_transcript": "First we boarded the train, then we found our seats, and "
        "finally we ordered lunch.",
        "noise_level": 1,
        "repetition_policy": "none",
        "script": "First we boarded the train, then we found our seats, and finally "
        "we ordered lunch.",
        "question": "What happened right after boarding the train?",
        "options": [
            "They found their seats",
            "They ordered lunch",
            "They bought tickets",
            "They got off",
        ],
        "answer_index": 0,
    },
]


LEVEL_ORDER: list[str] = ["A1", "A2", "B1"]


def get_question(question_id: str) -> dict | None:
    """Devuelve la pregunta por id o None si no existe."""
    for q in QUESTION_BANK:
        if q["id"] == question_id:
            return q
    return None


def questions_for_level(level: str) -> list[dict]:
    """Preguntas del banco pertenecientes a un nivel CEFR concreto."""
    return [q for q in QUESTION_BANK if q["level"] == level]


def validate_listening_bank(
    bank: list[dict] | None = None,
    *,
    factors: tuple[str, ...] = DIFFICULTY_FACTORS,
) -> list[str]:
    """Invariantes del banco de listening (devuelve lista de violaciones, vacía = ok).

    Garantiza que todo ítem sea un `ListeningAsset` válido, con id único, sub-destreza
    canónica y un `difficulty_vector` de 8 dimensiones con valores 1..6. La coherencia
    media↔dificultad ya no se valida: se cumple por construcción (`difficulty` se
    deriva del vector)."""
    bank = bank if bank is not None else QUESTION_BANK
    errors: list[str] = []
    seen_ids: set[str] = set()
    for q in bank:
        try:
            asset = ListeningAsset.model_validate(q)
        except ValidationError as exc:
            first = exc.errors()[0]
            errors.append(f"{q.get('id', '?')}: {first['msg']} ({first['loc'][0]})")
            continue
        if asset.id in seen_ids:
            errors.append(f"duplicate id: {asset.id}")
        seen_ids.add(asset.id)
        if asset.skill not in LISTENING_SUBSKILLS:
            errors.append(f"{asset.id}: invalid skill {asset.skill!r}")
        if set(asset.difficulty_vector) != set(factors):
            errors.append(f"{asset.id}: difficulty_vector factors mismatch")
        else:
            for factor, value in asset.difficulty_vector.items():
                if not 1 <= value <= 6:
                    errors.append(
                        f"{asset.id}: difficulty_vector[{factor}] out of range"
                    )
        if not 0 <= asset.answer_index < len(asset.options):
            errors.append(f"{asset.id}: answer_index out of range")
    return errors


def level_status(correct_question_ids: set[str]) -> list[dict]:
    """Progreso por nivel CEFR.

    Un nivel se considera completado cuando el usuario ha respondido
    correctamente (al menos una vez) todas sus preguntas. Devuelve una lista con
    `{level, total, mastered, completed}` en orden CEFR."""
    status = []
    for level in LEVEL_ORDER:
        questions = questions_for_level(level)
        total = len(questions)
        mastered = sum(1 for q in questions if q["id"] in correct_question_ids)
        status.append(
            {
                "level": level,
                "total": total,
                "mastered": mastered,
                "completed": total > 0 and mastered == total,
            }
        )
    return status


def current_level(correct_question_ids: set[str]) -> str:
    """Nivel CEFR en el que el usuario está trabajando.

    Es el primer nivel aún no completado; si todos están completados, devuelve el
    último nivel para permitir seguir practicando sin quedarse atascado."""
    for level in LEVEL_ORDER:
        questions = questions_for_level(level)
        if not questions:
            continue
        mastered = sum(1 for q in questions if q["id"] in correct_question_ids)
        if mastered < len(questions):
            return level
    return LEVEL_ORDER[-1]


def pick_next_question(
    seen_ids: set[str], correct_ids: set[str] | None = None
) -> dict:
    """Siguiente pregunta respetando la progresión por nivel CEFR.

    Prioriza, dentro del nivel actual, las preguntas aún no dominadas (respondidas
    correctamente): primero las no vistas y luego las vistas pero falladas, para
    reintentarlas. Al dominar un nivel se avanza al siguiente; al completar todos,
    rota sobre el banco para seguir practicando en lugar de quedarse atascado."""
    correct_ids = correct_ids or set()
    questions = questions_for_level(current_level(correct_ids))

    for q in questions:
        if q["id"] not in seen_ids and q["id"] not in correct_ids:
            return q
    for q in questions:
        if q["id"] not in correct_ids:
            return q

    # Nivel completado o sin preguntas: nunca se repite la misma pregunta en bucle.
    for q in QUESTION_BANK:
        if q["id"] not in correct_ids:
            return q
    return QUESTION_BANK[0]


def score_answer(answer_index: int, correct_index: int) -> bool:
    """True si el índice elegido coincide con el correcto."""
    return answer_index == correct_index


def _first_pass_rows(rows: list[dict]) -> list[dict]:
    """Primera exposición de cada pregunta (la fila más antigua por question_id).

    Las filas llegan ordenadas por id ASC, por lo que la primera aparición de cada
    `question_id` es su primer intento."""
    first_by_question: dict = {}
    for row in rows:
        question_id = row.get("question_id")
        if question_id is None:
            continue
        first_by_question.setdefault(question_id, row)
    return list(first_by_question.values())


def _accuracy(rows: list[dict]) -> float | None:
    if not rows:
        return None
    correct = sum(1 for r in rows if r.get("correct"))
    return round(correct / len(rows) * 100, 1)


def listening_diagnostic(attempt_rows: list[dict]) -> dict:
    """Perfil de sub-destrezas de listening y recomendación (vista derivada).

    `attempt_rows` son las filas de `listening_attempts` del usuario (con `skill`,
    `difficulty`, `response_time_ms`, `replay_count`, `correct`). Devuelve un dict
    con `subskills` (lista de {skill, attempts, correct, accuracy, first_pass_accuracy,
    avg_response_ms, avg_replay_count, automaticity, review_due}, ordenadas por
    LISTENING_SUBSKILLS y luego alfabético), `weak` (skills con `review_due` True),
    `recommendation` (texto corto), `first_pass_accuracy` global, `automaticity`
    global y `bank_version`."""
    groups: dict[str, list[dict]] = {}
    for row in attempt_rows:
        skill = row.get("skill") or ""
        groups.setdefault(skill, []).append(row)

    def _stats(rows: list[dict]) -> dict:
        attempts = len(rows)
        correct = sum(1 for r in rows if r.get("correct"))
        accuracy = round(correct / attempts * 100, 1) if attempts else None
        rts = [
            r.get("response_time_ms")
            for r in rows
            if r.get("response_time_ms") is not None
        ]
        avg_response_ms = round(sum(rts) / len(rts), 0) if rts else None
        replays = [r.get("replay_count") or 0 for r in rows]
        avg_replay_count = round(sum(replays) / len(replays), 2) if replays else 0.0
        return {
            "attempts": attempts,
            "correct": correct,
            "accuracy": accuracy,
            "avg_response_ms": avg_response_ms,
            "avg_replay_count": avg_replay_count,
        }

    known = list(LISTENING_SUBSKILLS)
    extras = sorted(set(groups) - set(known))
    ordered_skills = known + extras

    subskills: list[dict] = []
    for skill in ordered_skills:
        rows = groups.get(skill, [])
        stats = _stats(rows)
        attempts = stats["attempts"]
        accuracy = stats["accuracy"]
        # Una sub-destreza está "débil" si no se ha practicado, si su precisión es
        # baja con muestras suficientes, si depende de repeticiones para acertar
        # (comprensión no consolidada) o si responde con lentitud.
        review_due = attempts == 0 or (
            attempts >= 3 and accuracy is not None and accuracy < 70
        ) or (
            attempts >= 2 and stats["avg_replay_count"] >= 1.0
        ) or (
            stats["avg_response_ms"] is not None and stats["avg_response_ms"] >= 4000
        )
        subskills.append(
            {
                "skill": skill,
                "attempts": attempts,
                "correct": stats["correct"],
                "accuracy": accuracy,
                "first_pass_accuracy": _accuracy(_first_pass_rows(rows)),
                "avg_response_ms": stats["avg_response_ms"],
                "avg_replay_count": stats["avg_replay_count"],
                "automaticity": automaticity_from_metrics(
                    stats["avg_replay_count"],
                    stats["avg_response_ms"],
                    attempts=attempts,
                ),
                "review_due": review_due,
            }
        )

    def _rank(skill: str) -> int:
        if skill in known:
            return known.index(skill)
        return len(known) + extras.index(skill)

    def _acc(skill: str) -> float | None:
        for s in subskills:
            if s["skill"] == skill:
                return s["accuracy"]
        return None

    weak = [s["skill"] for s in subskills if s["review_due"]]
    weak.sort(
        key=lambda sk: (
            _acc(sk) is None,
            _acc(sk) if _acc(sk) is not None else 0.0,
            _rank(sk),
        )
    )

    if not weak:
        recommendation = "All listening sub-skills look strong."
    else:
        recommendation = "Focus on: " + ", ".join(weak)

    global_stats = _stats(attempt_rows)
    return {
        "subskills": subskills,
        "weak": weak,
        "recommendation": recommendation,
        "first_pass_accuracy": _accuracy(_first_pass_rows(attempt_rows)),
        "automaticity": automaticity_from_metrics(
            global_stats["avg_replay_count"],
            global_stats["avg_response_ms"],
            attempts=global_stats["attempts"],
        ),
        "bank_version": LISTENING_BANK_VERSION,
    }
