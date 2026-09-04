"""Generador de ítems de listening extra con IA local (V3.6).

Crea ítems de comprensión auditiva MCQ para ampliar una ruta de listening con
práctica adicional generada por el modelo local (Ollama) y voz Piper. Los ítems
generados:

- NUNCA forman parte del banco curado (`QUESTION_BANK`) ni de la puerta de ruta
  / certificación: son práctica voluntaria que el alumno activa en una ruta.
- Son MCQ verificables de forma determinista SIN LLM en el momento de responder:
  la opción correcta debe aparecer **literal** en el script (la frase que se
  oye) y los distractores no, de modo que el `answer_index` correcto se deduce
  por substring y la respuesta se puntúa igual que el banco.
- Se limitan a sub-destrezas de comprensión factual (detail/numbers/vocabulary/
  sequencing/note_taking), que admiten esa verificación literal.

La generación es lenta (modelo local en CPU), por lo que el orquestador corre en
un trabajo en segundo plano (ver `domain.listening.generate_route_extras`) y
este módulo solo contiene las piezas puras: prompt, parseo y validación.
"""
from __future__ import annotations

import json
import re
import unicodedata

from services.listening import (
    DIFFICULTY_FACTORS,
    LISTENING_TOPICS,
    difficulty_from_vector,
)

# Versión del prompt/validador. Un cambio de criterio de validación o de forma
# del ítem debe subir esta versión (los ítems guardan la versión con la que se
# generaron).
GENERATOR_VERSION = "1.0.0"

# Sub-destrezas de comprensión auditiva que admiten verificación literal de la
# opción correcta en el script. Fuera quedan gist/inference/attitude/prediction
# (la respuesta correcta es paráfrasis, no verificable de forma determinista) y
# dictation/shadowing (producción, no MCQ).
GENERATED_SUBSKILLS: tuple[str, ...] = (
    "detail",
    "numbers",
    "vocabulary",
    "sequencing",
    "note_taking",
)

# Perfil por nivel CEFR: (velocidad, vocabulario, sintaxis, longitud) de los
# factores de dificultad que el texto del ítem puede realizar. Los factores de
# audio (acento, ruido, nº de hablantes, connected_speech) se fijan a 1: con la
# voz Piper única del banco no se realizan, y un ítem generado no debe declarar
# una dificultad de audio que su realización no respalda.
_BAND_TEXTUAL: dict[str, tuple[int, int, int, int]] = {
    "A1": (1, 1, 1, 1),
    "A2": (2, 2, 2, 2),
    "B1": (3, 3, 3, 3),
    "B2": (4, 4, 4, 5),
    "C1": (5, 5, 5, 5),
    "C2": (6, 6, 6, 6),
}

# Velocidad (wpm) de referencia de los ítems generados por nivel.
_BAND_SPEECH_RATE: dict[str, int] = {
    "A1": 115,
    "A2": 125,
    "B1": 135,
    "B2": 150,
    "C1": 160,
    "C2": 170,
}

_SYSTEM_PROMPT = (
    "You write short English listening-comprehension questions for a "
    "self-study language app. The learner HEARS the sentence, then reads the "
    "question and chooses ONE of four options. All audio is a single clear "
    "speaker with neutral English at a normal pace; no connected-speech "
    "reductions, no noise.\n"
    "Rules for every item:\n"
    "1. The 'script' is the sentence the learner hears. Keep it between 5 and "
    "45 words, self-contained and natural for the CEFR level.\n"
    "2. The question asks about a fact stated in the script (a detail, a "
    "number/time, a word meaning, an order of events, or a note to take).\n"
    "3. Provide exactly 4 short options. The CORRECT option must appear "
    "word-for-word (as a substring) inside the script. The 3 distractors must "
    "NOT appear anywhere in the script and must be different from each other.\n"
    "4. Reply with ONLY a JSON object, no prose: "
    '{"items":[{"script":"...","question":"...","options":["a","b","c","d"],'
    '"skill":"one of the allowed","topic":"one of the allowed topics"}]}\n'
    "Do not include markdown fences.\n"
)

# Expuesto para que el orquestador (domain.listening_extras) envíe el mismo
# system prompt en cada tanda de generación.
SYSTEM_PROMPT = _SYSTEM_PROMPT

_LEVEL_HINT: dict[str, str] = {
    "A1": "CEFR A1: very frequent everyday words, short simple present sentences.",
    "A2": "CEFR A2: everyday topics, simple past, common phrases, slightly "
    "longer sentences.",
    "B1": "CEFR B1: familiar topics with detail, some abstract ideas, moderate "
    "sentence length.",
    "B2": "CEFR B2: concrete and some abstract topics, richer vocabulary, "
    "idiomatic everyday English.",
    "C1": "CEFR C1: longer, more complex sentences, nuanced vocabulary.",
    "C2": "CEFR C2: sophisticated vocabulary and complex structures.",
}

_TOPIC_HINT: dict[str, str] = {
    "daily_routine": "daily routine",
    "shopping": "shopping",
    "travel": "travel",
    "work": "work",
    "weather": "weather",
    "free_time": "free time",
    "food": "food and restaurants",
    "education": "education",
    "sports": "sports",
    "functional": "everyday practical situations",
}


def build_user_prompt(level: str, skills: list[str], topics: list[str]) -> str:
    """Instrucción de una tanda de generación: pide `len(skills)` ítems.

    Se pide un ítem por (skill, topic) para forzar variedad de tarea y tema en
    la tanda sin depender del azar del modelo.
    """
    pairs = ", ".join(
        f'item {i + 1}: skill "{s}" on topic "{_TOPIC_HINT.get(t, t)}"'
        for i, (s, t) in enumerate(zip(skills, topics))
    )
    allowed_skills = ", ".join(GENERATED_SUBSKILLS)
    allowed_topics = ", ".join(LISTENING_TOPICS)
    return (
        f"{_LEVEL_HINT.get(level, level)}\n"
        f"Generate exactly {len(skills)} items in the order below.\n"
        f"{pairs}.\n"
        f"Allowed 'skill' values: {allowed_skills}.\n"
        f"Allowed 'topic' values (choose the closest for each item): "
        f"{allowed_topics}.\n"
    )


def _norm(text: str) -> str:
    """Normaliza para comparaciones de substring: minúsculas, sin puntuación.

    Reduce espacios y guiones y elimina signos de puntuación/apóstrofos para que
    "o'clock" no rompa la búsqueda de la opción en el script.
    """
    text = unicodedata.normalize("NFKD", text).lower()
    text = re.sub(r"[\W_]+", " ", text)  # \W ya no incluye '_' con re.UNICODE? se quita aparte
    text = text.replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def canonical_script(script: str) -> str:
    """Forma canónica de un script para deduplicar contenido entre tandas."""
    return _norm(script)


def _contains_option(script: str, option: str) -> bool:
    """True si la opción (normalizada) aparece literal en el script (normalizado).

    Requiere que la opción no sea una palabra suelta genérica (p. ej. "a") para
    evitar coincidencias triviales: debe tener al menos 3 caracteres.
    """
    opt = _norm(option)
    if len(opt) < 3:
        return False
    return opt in _norm(script)


def parse_content(content: str) -> list[dict]:
    """Convierte la respuesta del modelo en una lista de ítems crudos.

    Acepta un objeto `{"items": [...]}` o un único objeto de ítem, tolerando
    cercos de markdown y texto alrededor. Devuelve la lista de dicts crudos.
    """
    text = content.strip()
    # Quita cercos de markdown ```json ... ``` si los hubiera.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("la respuesta del modelo no contiene JSON")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("JSON inválido") from exc
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [d for d in data["items"] if isinstance(d, dict)]
    if isinstance(data, dict):
        return [data]
    raise ValueError("JSON sin ítems")


def compose_item(
    level: str,
    raw: dict,
    *,
    item_id: str | None = None,
) -> dict | None:
    """Valida un ítem crudo del modelo y devuelve su payload final, o None.

    La validación es determinista y NO se fía del `answer_index` del modelo: la
    opción correcta es la única cuya forma normalizada aparece literal en el
    script. Si no hay exactamente una, el ítem se descarta (None).

    Devuelve el dict del ítem con las mismas claves que el banco curado
    (script, question, options, answer_index, skill, topic, context,
    difficulty_vector, metadatos de audio TTS…).
    """
    script = (raw.get("script") or "").strip()
    question = (raw.get("question") or "").strip()
    options = raw.get("options")
    skill = (raw.get("skill") or "").strip()
    topic = (raw.get("topic") or "").strip()
    if not script or not question:
        return None
    if not isinstance(options, list) or len(options) != 4:
        return None
    options = [str(o).strip() for o in options]
    if any(not o for o in options) or len(set(options)) != 4:
        return None
    if skill not in GENERATED_SUBSKILLS:
        return None
    if topic not in LISTENING_TOPICS:
        return None
    word_count = len(_norm(script).split())
    if not 5 <= word_count <= 45:
        return None

    contained = [
        i for i, opt in enumerate(options) if _contains_option(script, opt)
    ]
    if len(contained) != 1:
        return None
    answer_index = contained[0]

    if level not in _BAND_TEXTUAL:
        return None
    speed, vocabulary, syntactic, length = _BAND_TEXTUAL[level]
    # Los factores textuales del vector; los de audio (realizables solo por la
    # voz humana) se dejan en 1 para que la realización respalde lo declarado.
    difficulty_vector = {
        "speed": speed,
        "vocabulary": vocabulary,
        "accent": 1,
        "syntactic": syntactic,
        "length": length,
        "speaker_count": 1,
        "noise": 1,
        "connected_speech": 1,
    }
    # Reordena según DIFFICULTY_FACTORS por limpieza (validate_listening_bank
    # exige el mismo conjunto, no el orden).
    difficulty_vector = {
        k: difficulty_vector[k]
        for k in DIFFICULTY_FACTORS
        if k in difficulty_vector
    }
    speech_rate = _BAND_SPEECH_RATE[level]
    duration = round(word_count / speech_rate * 60 + 0.6, 1)

    payload = {
        "id": item_id,
        "level": level,
        "skill": skill,
        "topic": topic,
        "context": "conversation",
        "difficulty_vector": difficulty_vector,
        "script": script,
        "clean_transcript": script,
        "transcript": script,
        "question": question,
        "options": options,
        "answer_index": answer_index,
        # Metadatos de audio: voz Piper única, clara y sin ruido.
        "audio_type": "tts",
        "speech_rate": float(speech_rate),
        "duration": duration,
        "accent": "neutral",
        "noise_level": 0,
        "speaker_count": 1,
        "repetition_policy": "none",
        "audio_id": "",
        "speaker_id": "",
    }
    if item_id is None:
        payload.pop("id", None)
    return payload


def validate_payload_shape(payload: dict) -> bool:
    """Invariantes mínimas del payload ya compuesto (espejo del banco).

    Sirve de red de seguridad adicional antes de persistir: la dificultad
    escalar derivada debe estar en [1..6] y el `answer_index` dentro de las
    opciones.
    """
    if not payload.get("id"):
        return False
    if not (1 <= difficulty_from_vector(payload["difficulty_vector"]) <= 6):
        return False
    options = payload.get("options") or []
    if not (0 <= payload.get("answer_index", -1) < len(options)):
        return False
    return True
