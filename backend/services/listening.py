"""Banco de preguntas de listening y puntuación determinista (puro)."""
from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, Field, ValidationError, computed_field

from services.curriculum import CURRICULUM_DIR, LISTENING_BANK_VERSION
from services.forgetting import days_since
from services.phonetics import composite_score

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

# Dimensiones de resiliencia auditiva (Listening 2.0). Cada dimensión es una
# *condición de escucha* que el audio del ítem realiza y frente a la que medimos
# precisión, de la más cómoda (habla clara) a la más exigente (acentos). Es el
# indicador que responde "¿qué condición de escucha te cuesta más?".
RESILIENCE_DIMENSIONS: tuple[str, ...] = (
    "clear_speech",
    "natural_speech",
    "connected_speech",
    "fast_speech",
    "noise",
    "accents",
)

# Mínimo de intentos requerido en una dimensión para poder nombrarla como la
# debilidad principal de escucha (evita recomendaciones sobre muestras ruidosas).
RESILIENCE_MIN_ATTEMPTS = 3

# Taxonomía de temas del banco de listening. Cada ítem declara un tema canónico
# para poder medir precisión por tema (P4 — listening como competencia).
LISTENING_TOPICS: tuple[str, ...] = (
    "daily_routine",
    "shopping",
    "travel",
    "work",
    "weather",
    "free_time",
    "food",
    "education",
    "sports",
    "functional",
)

# Contextos comunicativos del corpus de listening (Listening 2.0). Completan la
# clasificación del ítem junto a nivel, hablante, acento, velocidad, ruido,
# connected_speech y tipo de tarea. Es el eje del corpus real: la escucha progresa
# de lo más cómodo (conversación clara) a lo más exigente (anuncios, entrevistas).
LISTENING_CONTEXTS: tuple[str, ...] = (
    "conversation",  # diálogo entre dos o más hablantes
    "announcement",  # aviso público (estación, aeropuerto, tienda)
    "message",  # mensaje grabado (buzón de voz)
    "instructions",  # indicaciones paso a paso
    "news",  # noticia o boletín informativo
    "interview",  # entrevista
    "narrative",  # relato/narración
    "presentation",  # exposición/monólogo
)

# Tipos de audio admitidos. Separan la realización real del audio de lo que el
# ítem *declara* en su vector de dificultad. Hoy el banco es `tts` (una única voz
# Piper pre-renderizada); los tipos `recorded`/`mixed`/`synthetic_multispeaker`/
# `real_world` quedan reservados para la biblioteca de audio humano (V1.15+).
AUDIO_TYPES: tuple[str, ...] = (
    "tts",  # voz sintética única, pre-renderizada y cacheada (Piper)
    "recorded",  # grabación humana real (una o varias voces)
    "mixed",  # mezcla de grabado + sintético
    "synthetic_multispeaker",  # varias voces generadas (escenario sintético)
    "real_world",  # audio natural: ruido, solapamiento, acentos, interrupciones
)

# Mapa sub-destreza → factor del vector de dificultad cuya realización auditiva
# respalda (o no) la evidencia de esa sub-destreza. Las sub-destrezas de
# comprensión textual (gist/detail/inference/…) no dependen de un factor de audio
# concreto: lo que se lee es lo que se escucha, así que se consideran realizadas.
SUBSKILL_REALIZATION_FACTOR: dict[str, str] = {
    "fast_speech": "speed",
    "connected_speech": "connected_speech",
    "multiple_speakers": "speaker_count",
    "accents": "accent",
}

# Reducciones fuertes del connected speech: si el texto a sintetizar las contiene
# de forma explícita, la voz Piper las pronuncia tal cual y la dimensión
# `connected_speech` se considera realizada al nivel declarado.
STRONG_REDUCTIONS: tuple[str, ...] = (
    "gonna",
    "wanna",
    "gotta",
    "gimme",
    "lemme",
    "dunno",
    "whaddaya",
    "d'you",
    "d'ya",
    "kinda",
    "sorta",
    "shoulda",
    "woulda",
    "coulda",
    "hafta",
    "usta",
    "ain't",
    "outta",
)

# Contracciones suaves: indican cierta reducción, pero no el connected speech
# natural (linking/reducción vocálica). Se realizan solo de forma parcial.
MILD_CONTRACTIONS: tuple[str, ...] = (
    "she'd", "he'd", "we'd", "they'd", "i'd", "you'd", "it'd",
    "we'll", "she'll", "he'll", "they'll", "i'll", "you'll", "it'll",
    "i'm", "we're", "they're", "you're", "she's", "he's", "it's",
    "can't", "don't", "won't", "isn't", "aren't", "wasn't", "weren't",
    "didn't", "doesn't", "haven't", "hasn't", "hadn't", "wouldn't",
    "couldn't", "shouldn't", "mustn't",
)

# Umbral de acierto (0..100) para las tareas de producción (dictado/shadowing).
# Un intento de producción se considera `correct` cuando su score compuesto lo
# alcanza o supera.
PRODUCTION_PASS_SCORE = 80


def production_score(reference: str, heard: str) -> dict:
    """Score determinista de una producción frente a una referencia (0..100).

    Delega en `services.phonetics.composite_score` (sin LLM) y devuelve
    `{score, word_accuracy, phonetic_score, phoneme_accuracy_proxy, breakdown}`
    con enteros 0..100 salvo `breakdown` (el dict de `word_alignment`).
    """
    result = composite_score(reference, heard)
    return {
        "score": int(result["score"]),
        "word_accuracy": int(result["word_accuracy"]),
        "phonetic_score": int(result["phonetic_score"]),
        "phoneme_accuracy_proxy": int(result["phoneme_accuracy_proxy"]),
        "breakdown": result["breakdown"],
    }


def production_reference(question: dict) -> str:
    """Referencia contra la que se puntúa una producción del ítem.

    Orden de preferencia: `transcript`, `clean_transcript`, `script`. La referencia
    es la frase que el alumno debe reproducir (dictar o repetir en shadowing).
    """
    return (
        (question.get("transcript") or "").strip()
        or (question.get("clean_transcript") or "").strip()
        or (question.get("script") or "").strip()
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
    topic: str = ""
    # Tipo de audio (ver AUDIO_TYPES). Determina qué dimensiones del vector de
    # dificultad están realmente realizadas en el audio servido.
    audio_type: str = "tts"
    # Contexto comunicativo del ítem (ver LISTENING_CONTEXTS). Completa la
    # clasificación del corpus; vacío en el banco heredado que no lo declara.
    context: str = ""

    @computed_field
    @property
    def difficulty(self) -> int:
        return difficulty_from_vector(self.difficulty_vector)


_LEGACY_BANK: list[dict] = [
    {
        "id": "l1",
        "topic": "daily_routine",
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
        "topic": "shopping",
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
        "topic": "sports",
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
        "topic": "shopping",
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
        "topic": "travel",
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
        "topic": "work",
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
        "topic": "sports",
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
        "topic": "education",
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
        "topic": "travel",
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
        "topic": "daily_routine",
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
        "topic": "food",
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
        "topic": "education",
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
        "topic": "free_time",
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
        "topic": "work",
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
        "topic": "work",
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
        "topic": "shopping",
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
        "topic": "free_time",
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
        "topic": "daily_routine",
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
        "topic": "functional",
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
        "topic": "food",
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
        "topic": "free_time",
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
        "topic": "weather",
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
        "topic": "travel",
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


def _load_corpus_items() -> list[dict]:
    """Carga el corpus de audio humano desde `curriculum/listening_corpus.json`.

    El corpus vive como contenido versionado fuera del código (espejo de la
    convención de `services.curriculum`): el equipo pedagógico lo edita sin tocar
    lógica. Devuelve los ítems en el orden declarado; lanza `FileNotFoundError` si
    falta el archivo (es contenido requerido del banco). Los ítems del corpus
    declaran `audio_id` y, por defecto, son `tts` hasta que el manifest de la
    biblioteca de audio humano respalda su `audio_id` (en ese momento el motor los
    sirve como `recorded`).
    """
    path = CURRICULUM_DIR / "listening_corpus.json"
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["items"]


# Banco completo: el banco heredado TTS (l1..l23) seguido del corpus de audio
# humano (c001..cNNN). El orden importa para la progresión CEFR: el banco heredado
# define la secuencia original y el corpus la amplía por nivel.
QUESTION_BANK: list[dict] = _LEGACY_BANK + _load_corpus_items()


LEVEL_ORDER: list[str] = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Velocidad de referencia (wpm) de la voz Piper por defecto. `length_scale_for_rate`
# la usa para mapear `speech_rate` (wpm) de un ítem a `length_scale` de Piper.
DEFAULT_SPEECH_RATE = 140.0

# Límites de `length_scale` para no deformar la voz (0.6 ≈ 1.67× más rápido,
# 1.6 ≈ 0.625× más lento). Fuera de este rango el audio se degrada de forma audible.
LENGTH_SCALE_MIN = 0.6
LENGTH_SCALE_MAX = 1.6

# Escalera de variantes de audio (P1.9): el mismo contenido a distinta velocidad.
# `normal` es la realización actual del ítem (preserva digest/cache); `slow`/`fast`
# aplican un factor de velocidad sobre la tasa declarada (o la de referencia).
AUDIO_VARIANTS: tuple[str, ...] = ("slow", "normal", "fast")

# Factor multiplicador de wpm por variante. La velocidad es la única dimensión
# realizable hoy de forma determinista con una única voz Piper (no acento/ruido).
VARIANT_SPEED_FACTORS: dict[str, float] = {
    "slow": 0.75,
    "normal": 1.0,
    "fast": 1.25,
}


def length_scale_for_rate(speech_rate: float) -> float:
    """Mapea `speech_rate` (wpm) a `length_scale` de Piper (determinista).

    Más wpm ⇒ menor `length_scale` (más rápido). `speech_rate <= 0` (sin metadatos)
    devuelve 1.0 (velocidad por defecto). El resultado se clampa a
    `[LENGTH_SCALE_MIN, LENGTH_SCALE_MAX]`.
    """
    if not speech_rate or speech_rate <= 0:
        return 1.0
    scale = DEFAULT_SPEECH_RATE / speech_rate
    return round(max(LENGTH_SCALE_MIN, min(LENGTH_SCALE_MAX, scale)), 3)


def variant_speech_rate(question: dict, variant: str = "normal") -> float:
    """Velocidad (wpm) del ítem para una variante de la escalera.

    - `normal` devuelve la tasa declarada (`speech_rate`), o `0.0` si no se
      declara, preservando el comportamiento actual.
    - `slow`/`fast` aplican `VARIANT_SPEED_FACTORS` sobre la tasa declarada; si el
      ítem no declara tasa, usan `DEFAULT_SPEECH_RATE` como base.

    `variant` debe pertenecer a `AUDIO_VARIANTS`; cualquier otro valor se trata
    como `normal` (comportamiento seguro y determinista).
    """
    base = question.get("speech_rate") or 0.0
    if variant == "normal" or variant not in VARIANT_SPEED_FACTORS:
        return base
    effective = base if base > 0 else DEFAULT_SPEECH_RATE
    return round(effective * VARIANT_SPEED_FACTORS[variant], 1)


def variant_length_scale(question: dict, variant: str = "normal") -> float:
    """`length_scale` de Piper para una variante; `normal` = `length_scale_for_rate`.

    Para `variant == "normal"` devuelve exactamente lo que devuelve
    `length_scale_for_rate(speech_rate)` hoy, para no invalidar el cache existente.
    """
    return length_scale_for_rate(variant_speech_rate(question, variant))


def audio_variants(question: dict) -> list[dict]:
    """Lista de variantes de la escalera `{variant, speech_rate, label}`.

    Orden fijo slow → normal → fast, con `label` legible en inglés ("Slow",
    "Normal", "Fast"). `speech_rate` es la tasa wpm efectiva de cada variante.
    """
    labels = {"slow": "Slow", "normal": "Normal", "fast": "Fast"}
    return [
        {
            "variant": variant,
            "speech_rate": variant_speech_rate(question, variant),
            "label": labels[variant],
        }
        for variant in AUDIO_VARIANTS
    ]


def audio_text(question: dict) -> str:
    """Texto a sintetizar para un ítem: `transcript` si existe, si no `script`.

    `transcript` es la transcripción exacta del audio de referencia; `script` es el
    texto legible que se muestra. Ambos coinciden en los ítems que declaran audio;
    `script` es el fallback para el banco heredado que aún no tiene `transcript`.
    """
    return (question.get("transcript") or "").strip() or (
        question.get("script") or ""
    ).strip()


def spoken_text(question: dict) -> str:
    """Texto que realmente se sintetiza, respetando `repetition_policy="twice"`."""
    text = audio_text(question)
    if question.get("repetition_policy") == "twice":
        text = f"{text}. {text}"
    return text


def _connected_speech_realized(question: dict) -> int:
    """Nivel de `connected_speech` realmente presente en una voz Piper única.

    Piper lee el texto literalmente: si el texto escribe la reducción ("Gonnago",
    "Whaddaya", "d'you") la pronuncia y el connected speech se realiza al nivel
    declarado; si solo hay contracciones suaves ("she'd", "we'll") se realiza de
    forma parcial; si el texto está en ortografía estándar no hay reducción
    audible, por lo que la realización es mínima (1).
    """
    declared = int(question.get("difficulty_vector", {}).get("connected_speech", 1))
    text = audio_text(question).lower()
    if any(marker in text for marker in STRONG_REDUCTIONS):
        return declared
    if any(marker in text for marker in MILD_CONTRACTIONS):
        return min(declared, 2)
    return 1


def realized_vector(question: dict) -> dict[str, int]:
    """Vector de dificultad *realmente realizado* por el audio del ítem.

    Es el ancla de la integridad de evidencia (P0): el vector `difficulty_vector`
    es lo que el ítem *declara*; `realized_vector` es lo que el audio *realiza*.
    Para una voz Piper única (`audio_type="tts"`):

    - `vocabulary`/`syntactic`/`length`: se realizan siempre (el texto se lee).
    - `speed`: se realiza solo si el ítem fija `speech_rate` (mapeado a
      `length_scale`); sin él, la velocidad es la del modelo (1).
    - `accent`/`speaker_count`/`noise`: NO se realizan (una única voz neutra,
      sin ruido ni hablantes adicionales), así que quedan en 1.
    - `connected_speech`: se realiza según `_connected_speech_realized`.

    Para el resto de `AUDIO_TYPES` (grabado/real) se confía en la realización
    declarada, que en su caso la audita el proceso de grabación.
    """
    declared = question.get("difficulty_vector", {})
    audio_type = question.get("audio_type") or "tts"
    if audio_type != "tts":
        return {factor: int(declared.get(factor, 1)) for factor in DIFFICULTY_FACTORS}
    realized: dict[str, int] = {}
    for factor in DIFFICULTY_FACTORS:
        value = int(declared.get(factor, 1))
        if factor == "speed":
            realized[factor] = value if (question.get("speech_rate") or 0) > 0 else 1
        elif factor in ("accent", "speaker_count", "noise"):
            realized[factor] = 1
        elif factor == "connected_speech":
            realized[factor] = _connected_speech_realized(question)
        else:  # vocabulary, syntactic, length
            realized[factor] = value
    return realized


def realization_status(question: dict) -> dict[str, dict[str, int | bool]]:
    """Estado de realización por factor: `declared` / `realized` / `verified`.

    `verified` es True cuando la realización alcanza o supera lo declarado (es
    decir, el audio respalda la dificultad declarada). Un factor con
    `realized < declared` es una brecha de evidencia: el Student Model no debe
    usarlo como evidencia fuerte.
    """
    declared = question.get("difficulty_vector", {})
    realized = realized_vector(question)
    status: dict[str, dict[str, int | bool]] = {}
    for factor in DIFFICULTY_FACTORS:
        d = int(declared.get(factor, 1))
        r = int(realized.get(factor, 1))
        status[factor] = {"declared": d, "realized": r, "verified": r >= d}
    return status


def realized_difficulty(question: dict) -> int:
    """Dificultad escalar derivada del vector *realizado* (no del declarado)."""
    return difficulty_from_vector(realized_vector(question))


def realization_gap_factors(question: dict) -> list[str]:
    """Factores donde el audio realiza menos de lo declarado (evidencia debilitada)."""
    declared = question.get("difficulty_vector", {})
    realized = realized_vector(question)
    return [
        factor
        for factor in DIFFICULTY_FACTORS
        if int(realized.get(factor, 1)) < int(declared.get(factor, 1))
    ]


def subskill_realization_gap(question: dict, subskill: str) -> bool:
    """True si el audio no realiza el factor que respalda la sub-destreza.

    Para sub-destrezas sin factor de audio asociado (comprensión textual), no hay
    brecha: lo que se lee es lo que se escucha.
    """
    factor = SUBSKILL_REALIZATION_FACTOR.get(subskill)
    if factor is None:
        return False
    declared = int(question.get("difficulty_vector", {}).get(factor, 1))
    realized = int(realized_vector(question).get(factor, 1))
    return realized < declared


def audio_digest(question: dict, variant: str = "normal") -> str:
    """Hash determinista del contenido a sintetizar (texto + velocidad + repetición).

    Se usa como parte de la clave de cache para que un cambio en el script, la
    velocidad, la política de repetición (o la voz, que vive en el directorio)
    invalide el WAV antiguo en lugar de seguir sirviéndolo.

    `variant` selecciona la variante de velocidad de la escalera. **Invariante de
    cache:** para `variant == "normal"` el payload es idéntico al histórico (mismo
    orden de campos, `length_scale` derivado de `speech_rate`), de modo que no se
    invalida el audio ya pre-renderizado.
    """
    payload = "|".join(
        [
            spoken_text(question),
            str(variant_length_scale(question, variant)),
            question.get("repetition_policy", "none"),
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


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
        if asset.topic not in LISTENING_TOPICS:
            errors.append(f"{asset.id}: invalid topic {asset.topic!r}")
        if asset.audio_type not in AUDIO_TYPES:
            errors.append(f"{asset.id}: invalid audio_type {asset.audio_type!r}")
        if asset.context and asset.context not in LISTENING_CONTEXTS:
            errors.append(f"{asset.id}: invalid context {asset.context!r}")
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


def review_next_question(level: str, attempts_rows: list[dict]) -> dict:
    """Siguiente frase de un nivel para repaso (rotación LRU).

    Devuelve la frase del nivel cuyo último intento registrado es más antiguo
    (o cualquier frase aún no intentada). Como cada respuesta registra una fila
    nueva, el repaso recorre las frases del nivel sin repetir hasta completar
    una vuelta completa. `attempts_rows` llega ordenado por id ASC.
    """
    candidates = questions_for_level(level)
    if not candidates:
        raise ValueError(f"nivel sin frases en el banco: {level}")
    candidate_ids = {q["id"] for q in candidates}
    last_index: dict[str, int] = {}
    for i, row in enumerate(attempts_rows):
        qid = row.get("question_id")
        if qid in candidate_ids:
            last_index[qid] = i
    # Nunca intentadas primero (son las menos practicadas); entre las demás, la
    # de intento más antiguo primero (LRU). Tras responder, la frase pasa al
    # final y no se repite hasta completar la vuelta.
    pool = sorted(
        candidates,
        key=lambda q: (q["id"] in last_index, last_index.get(q["id"], -1)),
    )
    return pool[0]


def _realizes_subskill(question: dict, subskill: str) -> bool:
    """True si el audio del ítem realiza el factor que respalda la sub-destreza.

    Evita servir como práctica de `multiple_speakers` un audio de una sola voz
    (metadata declarada pero no realizada): el selector no debe entrenar una
    sub-destreza con evidencia auditiva que no la respalda.
    """
    return not subskill_realization_gap(question, subskill)


def pick_next_question(
    seen_ids: set[str],
    correct_ids: set[str] | None = None,
    *,
    weak_subskills: list[str] | None = None,
) -> dict:
    """Siguiente pregunta: prioriza la sub-destreza más débil dentro del nivel actual.

    Respeta la progresión por nivel CEFR (no salta a un nivel superior aunque la
    sub-destreza débil pertenezca a él) y, cuando se le pasan `weak_subskills`
    (procedentes del diagnóstico del Student Model), prioriza —dentro del nivel de
    trabajo— las preguntas de esas sub-destrezas cuya realización auditiva es
    válida. Sin sub-destrezas débiles, conserva el comportamiento anterior:
    primero no vistas y luego falladas, avanzando de nivel al dominarlo.
    """
    correct_ids = correct_ids or set()
    working = questions_for_level(current_level(correct_ids))
    weak = [s for s in (weak_subskills or []) if s in LISTENING_SUBSKILLS]

    def _unseen_not_correct(q: dict) -> bool:
        return q["id"] not in seen_ids and q["id"] not in correct_ids

    def _not_correct(q: dict) -> bool:
        return q["id"] not in correct_ids

    # 1. Sub-destrezas débiles del nivel de trabajo (realización válida): primero
    #    no vistas, luego falladas para reintento.
    weak_qs = [
        q for q in working if q["skill"] in weak and _realizes_subskill(q, q["skill"])
    ]
    for q in weak_qs:
        if _unseen_not_correct(q):
            return q
    for q in weak_qs:
        if _not_correct(q):
            return q

    # 2. Progresión estándar dentro del nivel: no vistas y luego falladas.
    for q in working:
        if _unseen_not_correct(q):
            return q
    for q in working:
        if _not_correct(q):
            return q

    # 3. Nivel completado o sin preguntas: rota sobre el banco restante.
    for q in QUESTION_BANK:
        if _not_correct(q):
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


TREND_WINDOW = 10


def accuracy_by_difficulty(rows: list[dict]) -> list[dict]:
    """Precisión agrupada por dificultad escalar (1..6).

    Devuelve una lista `{difficulty, attempts, correct, accuracy}` ordenada por
    dificultad ascendente. Omite filas sin dificultad (vistas agregadas)."""
    groups: dict[int, list[dict]] = {}
    for row in rows:
        difficulty = row.get("difficulty")
        if difficulty is None:
            continue
        groups.setdefault(int(difficulty), []).append(row)
    return [
        {
            "difficulty": difficulty,
            "attempts": len(group),
            "correct": sum(1 for r in group if r.get("correct")),
            "accuracy": _accuracy(group),
        }
        for difficulty, group in sorted(groups.items())
    ]


def accuracy_by_topic(rows: list[dict]) -> list[dict]:
    """Precisión agrupada por tema canónico.

    Devuelve una lista `{topic, attempts, correct, accuracy}` ordenada
    alfabéticamente. Omite filas sin tema (intentos legacy previos a P4)."""
    groups: dict[str, list[dict]] = {}
    for row in rows:
        topic = row.get("topic") or ""
        if not topic:
            continue
        groups.setdefault(topic, []).append(row)
    return [
        {
            "topic": topic,
            "attempts": len(group),
            "correct": sum(1 for r in group if r.get("correct")),
            "accuracy": _accuracy(group),
        }
        for topic, group in sorted(groups.items())
    ]


def recent_trend(rows: list[dict], window: int = TREND_WINDOW) -> dict:
    """Tendencia reciente: precisión de los últimos `window` intentos vs. la previa.

    Las filas llegan en orden cronológico (id ASC). Devuelve
    `{recent_accuracy, prior_accuracy, delta, direction}` con `direction` en
    `{"up", "down", "flat", "n/a"}`."""
    if not rows:
        return {
            "recent_accuracy": None,
            "prior_accuracy": None,
            "delta": None,
            "direction": "n/a",
        }
    if len(rows) <= window:
        return {
            "recent_accuracy": _accuracy(rows),
            "prior_accuracy": None,
            "delta": None,
            "direction": "n/a",
        }
    recent = _accuracy(rows[-window:])
    prior = _accuracy(rows[:-window])
    delta = (
        round(recent - prior, 1)
        if recent is not None and prior is not None
        else None
    )
    if delta is None:
        direction = "n/a"
    elif delta > 0:
        direction = "up"
    elif delta < 0:
        direction = "down"
    else:
        direction = "flat"
    return {
        "recent_accuracy": recent,
        "prior_accuracy": prior,
        "delta": delta,
        "direction": direction,
    }


def recurrence_stats(rows: list[dict]) -> dict:
    """Reincidencia: reintentos de la misma pregunta y recuperación.

    `retried` = preguntas con más de un intento; `recovered` = preguntas falladas
    al menos una vez y luego acertadas; `retry_rate = retried/questions_seen`;
    `recovery_rate = recovered/retried` (`None` si el denominador es 0)."""
    by_question: dict[str, list[dict]] = {}
    for row in rows:
        question_id = row.get("question_id")
        if question_id is None:
            continue
        by_question.setdefault(question_id, []).append(row)
    questions_seen = len(by_question)
    retried = sum(1 for attempts in by_question.values() if len(attempts) > 1)
    recovered = sum(
        1
        for attempts in by_question.values()
        if any(not r.get("correct") for r in attempts)
        and any(r.get("correct") for r in attempts)
    )
    return {
        "questions_seen": questions_seen,
        "retried": retried,
        "recovered": recovered,
        "retry_rate": round(retried / questions_seen, 3) if questions_seen else None,
        "recovery_rate": round(recovered / retried, 3) if retried else None,
    }


RETENTION_BUCKETS: tuple[str, ...] = ("0-2", "2-7", "7-30", "30+")


def delayed_retention(attempt_rows: list[dict], now: str = "") -> dict:
    """Retención retardada: precisión inmediata (Day 0) vs. re-exposiciones (≥2 días).

    Agrupa los intentos por `question_id`. La primera exposición de cada pregunta
    (la fila más antigua por `created_at`) es el baseline *inmediato* (Day 0); el
    resto son re-exposiciones (*delayed*).

    - `immediate_accuracy`: % de acierto en las primeras exposiciones (`None` sin
      datos).
    - `delayed_accuracy`: % de acierto en las re-exposiciones con **≥ 2 días**
      desde su primera exposición (`None` sin datos).
    - `retention_rate`: `delayed_accuracy / immediate_accuracy` redondeado a 3
      decimales, o `None` si falta alguna precisión o `immediate_accuracy == 0`.
    - `by_bucket`: re-exposiciones agrupadas por días desde su primera exposición
      (solo re-exposiciones; se excluye la primera de cada pregunta y las filas sin
      `created_at`):
        - `"0-2"`  → `0 <= days < 2`
        - `"2-7"`  → `2 <= days < 7`
        - `"7-30"` → `7 <= days < 30`
        - `"30+"`  → `days >= 30`
    - `total_questions`: nº de preguntas distintas con al menos una exposición.

    `now` es el instante de referencia (ISO). Por defecto (`""`) usa el máximo
    `created_at` de las filas. Las re-exposiciones posteriores a `now` se ignoran
    (aún no han ocurrido desde esa referencia).
    """
    by_question: dict[str, list[dict]] = {}
    for row in attempt_rows:
        question_id = row.get("question_id")
        if question_id is None:
            continue
        by_question.setdefault(question_id, []).append(row)

    if not by_question:
        return {
            "total_questions": 0,
            "immediate_accuracy": None,
            "delayed_accuracy": None,
            "retention_rate": None,
            "by_bucket": [],
        }

    created_ats = [r.get("created_at") for r in attempt_rows if r.get("created_at")]
    effective_now = now or (max(created_ats) if created_ats else "")

    immediate_rows: list[dict] = []
    delayed_rows: list[dict] = []
    buckets: dict[str, list[dict]] = {bucket: [] for bucket in RETENTION_BUCKETS}

    for rows in by_question.values():
        ordered = sorted(
            rows,
            key=lambda r: (r.get("created_at") is None, r.get("created_at") or ""),
        )
        first = ordered[0]
        immediate_rows.append(first)
        first_created = first.get("created_at")
        if not first_created:
            continue
        for r in ordered[1:]:
            re_created = r.get("created_at")
            if not re_created:
                continue
            if effective_now and days_since(effective_now, re_created) > 0:
                continue  # re-exposición posterior a la referencia
            days = days_since(first_created, re_created)
            if days >= 30:
                buckets["30+"].append(r)
            elif days >= 7:
                buckets["7-30"].append(r)
            elif days >= 2:
                buckets["2-7"].append(r)
            else:
                buckets["0-2"].append(r)
            if days >= 2:
                delayed_rows.append(r)

    immediate_accuracy = _accuracy(immediate_rows)
    delayed_accuracy = _accuracy(delayed_rows)

    if immediate_accuracy in (None, 0) or delayed_accuracy is None:
        retention_rate = None
    else:
        retention_rate = round(delayed_accuracy / immediate_accuracy, 3)

    by_bucket = [
        {
            "bucket": bucket,
            "attempts": len(buckets[bucket]),
            "correct": sum(1 for r in buckets[bucket] if r.get("correct")),
            "accuracy": _accuracy(buckets[bucket]),
        }
        for bucket in RETENTION_BUCKETS
        if buckets[bucket]
    ]

    return {
        "total_questions": len(by_question),
        "immediate_accuracy": immediate_accuracy,
        "delayed_accuracy": delayed_accuracy,
        "retention_rate": retention_rate,
        "by_bucket": by_bucket,
    }


def resilience_dimensions(question: dict) -> list[str]:
    """Dimensiones de resiliencia que el audio *realizado* del ítem ejercita.

    Se apoya en `realized_vector` (no en el vector declarado) para ser honesta: una
    voz TTS neutra no realiza ruido ni acentos, de modo que esos ítems no aportan
    evidencia a esas dimensiones. Un ítem puede pertenecer a varias dimensiones
    (p. ej. rápido + conectado + ruidoso). Devuelve la lista en orden canónico.
    """
    realized = realized_vector(question)
    speed = int(realized.get("speed", 1))
    noise = int(realized.get("noise", 1))
    connected = int(realized.get("connected_speech", 1))
    accent = int(realized.get("accent", 1))
    speakers = int(realized.get("speaker_count", 1))

    dims: list[str] = []
    if speed <= 2 and noise <= 1 and connected <= 1 and speakers == 1:
        dims.append("clear_speech")
    if 3 <= speed <= 4 and noise <= 2:
        dims.append("natural_speech")
    if connected >= 4:
        dims.append("connected_speech")
    if speed >= 5:
        dims.append("fast_speech")
    if noise >= 3:
        dims.append("noise")
    if accent >= 4:
        dims.append("accents")
    return dims


def listening_resilience(attempt_rows: list[dict]) -> dict:
    """Indicador de resiliencia auditiva: precisión por condición de escucha.

    Agrupa los intentos según las dimensiones de resiliencia que el audio de cada
    ítem *realiza* y calcula la precisión (0..100) de cada una. Devuelve:
    - `dimensions`: lista `{dimension, attempts, correct, accuracy}` en orden
      canónico, con `accuracy=None` si no hay evidencia en esa dimensión.
    - `main_weakness`: la dimensión con menor precisión entre las que alcanzan
      `RESILIENCE_MIN_ATTEMPTS`, o None si ninguna lo alcanza.
    - `recommendation`: texto corto ("Your main weakness is …") o un estado neutral.
    """
    by_dim: dict[str, list[dict]] = {d: [] for d in RESILIENCE_DIMENSIONS}
    for row in attempt_rows:
        question = get_question(row.get("question_id"))
        if question is None:
            continue
        for dim in resilience_dimensions(question):
            by_dim[dim].append(row)

    dimensions: list[dict] = []
    for dim in RESILIENCE_DIMENSIONS:
        rows = by_dim[dim]
        dimensions.append(
            {
                "dimension": dim,
                "attempts": len(rows),
                "correct": sum(1 for r in rows if r.get("correct")),
                "accuracy": _accuracy(rows),
            }
        )

    main_weakness: str | None = None
    lowest_accuracy: float | None = None
    for entry in dimensions:
        accuracy = entry["accuracy"]
        if entry["attempts"] < RESILIENCE_MIN_ATTEMPTS or accuracy is None:
            continue
        if lowest_accuracy is None or accuracy < lowest_accuracy:
            lowest_accuracy = accuracy
            main_weakness = entry["dimension"]

    if main_weakness is None:
        recommendation = (
            "Not enough evidence yet to identify a listening weakness."
        )
    else:
        label = main_weakness.replace("_", " ")
        recommendation = f"Your main weakness is understanding {label}."

    return {
        "dimensions": dimensions,
        "main_weakness": main_weakness,
        "recommendation": recommendation,
    }


def listening_diagnostic(attempt_rows: list[dict], now: str = "") -> dict:
    """Perfil de sub-destrezas de listening y recomendación (vista derivada).

    `attempt_rows` son las filas de `listening_attempts` del usuario (con `skill`,
    `difficulty`, `response_time_ms`, `replay_count`, `correct`, `created_at`).
    Devuelve un dict con `subskills` (lista de {skill, attempts, correct, accuracy,
    first_pass_accuracy, avg_response_ms, avg_replay_count, automaticity,
    review_due}, ordenadas por LISTENING_SUBSKILLS y luego alfabético), `weak`
    (skills con `review_due` True), `recommendation` (texto corto),
    `first_pass_accuracy` global, `automaticity` global, `retention` (ver
    `delayed_retention`) y `bank_version`.

    `now` (ISO, opcional) es el instante de referencia para la retención; por
    defecto se deriva del máximo `created_at` de las filas."""
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
        # Brecha de realización: True si la evidencia de esta sub-destreza proviene
        # de al menos un ítem cuyo audio no realiza el factor que la respalda (p. ej.
        # multiple_speakers servido con una única voz Piper). Esa evidencia no debe
        # contarse como dominio real de la sub-destreza.
        questions = [
            get_question(r.get("question_id"))
            for r in rows
            if r.get("question_id") is not None
        ]
        questions = [q for q in questions if q is not None]
        realization_gap = any(subskill_realization_gap(q, skill) for q in questions)
        # Evidencia continua de producción (score 0..1 persistido): media en 0..100
        # sobre las filas con `score` no nulo, o None si no hay tareas de producción.
        prod_scores = [r["score"] * 100 for r in rows if r.get("score") is not None]
        mean_score = (
            round(sum(prod_scores) / len(prod_scores), 1) if prod_scores else None
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
                "mean_score": mean_score,
                "realization_gap": realization_gap,
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

    # Resumen de integridad de evidencia: cuántos intentos tienen audio cuya
    # realización respalda lo declarado (verified) frente a los que presentan brecha
    # (metadata no respaldada por el audio servido). El Student Model no debe tratar
    # los intentos con brecha como evidencia fuerte de dominio.
    attempt_questions = [
        get_question(r.get("question_id"))
        for r in attempt_rows
        if r.get("question_id") is not None
    ]
    attempt_questions = [q for q in attempt_questions if q is not None]
    verified = sum(1 for q in attempt_questions if not realization_gap_factors(q))
    realization_summary = {
        "attempts": len(attempt_questions),
        "verified": verified,
        "gap": len(attempt_questions) - verified,
    }

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
        "by_difficulty": accuracy_by_difficulty(attempt_rows),
        "by_topic": accuracy_by_topic(attempt_rows),
        "trend": recent_trend(attempt_rows),
        "recurrence": recurrence_stats(attempt_rows),
        "retention": delayed_retention(attempt_rows, now),
        "bank_version": LISTENING_BANK_VERSION,
        "realization": realization_summary,
        "resilience": listening_resilience(attempt_rows),
    }
