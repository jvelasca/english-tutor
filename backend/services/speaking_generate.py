"""Generador de tarjetas de micro-conversación extra de speaking con IA local (V3.8).

Crea tarjetas de intercambio (micro-conversaciones guiadas) para ampliar una ruta
de speaking con práctica adicional generada por el modelo local (Ollama). Cada
tarjeta tiene `setup` (situación), `you` (rol del alumno), `app_line` (línea del
interlocutor) y `model_response` (respuesta modelo), igual que el banco curado.
Las tarjetas generadas:

- NUNCA forman parte del banco curado (`SPEAKING_CORPUS`) ni de la puerta de
  ruta / certificación: son práctica voluntaria que el alumno activa en una ruta.
- Se evalúan igual que el banco (respuesta abierta con LLM + scorer), sin coste
  extra de diseño.
- Se limitan a intercambios breves, naturales y producibles por el nivel; la
  validación es determinista (longitudes, topic permitido por nivel).

La generación es lenta (modelo local en CPU), por lo que el orquestador corre en
un trabajo en segundo plano (ver `domain.speaking_routes`); este módulo solo
contiene las piezas puras: prompt, parseo y validación.
"""
from __future__ import annotations

import json
import re
import unicodedata

from services.speaking_routes import topics_for_level

# Versión del prompt/validador. Un cambio de criterio o de forma de la tarjeta debe
# subir esta versión (las tarjetas guardan la versión con la que se generaron).
GENERATOR_VERSION = "2.0.0"

# Perfil textual por nivel: (lexical, grammar, length, discourse) del vector de
# dificultad que el texto puede realizar de forma honesta.
_BAND_TEXTUAL: dict[str, tuple[int, int, int, int]] = {
    "A1": (1, 1, 1, 1),
    "A2": (2, 2, 2, 2),
    "B1": (3, 3, 3, 3),
    "B2": (4, 4, 4, 5),
    "C1": (5, 5, 5, 5),
    "C2": (6, 6, 6, 6),
}

# Rango de palabras por nivel para la línea del interlocutor (app_line) y para
# la respuesta modelo. Bandas progresivas: responden más largo cuanto más alto
# es el nivel (misma lógica que el corpus curado).
_BAND_APP_LINE: dict[str, tuple[int, int]] = {
    "A1": (3, 10),
    "A2": (4, 12),
    "B1": (5, 14),
    "B2": (6, 16),
    "C1": (7, 18),
    "C2": (8, 20),
}
_BAND_MODEL: dict[str, tuple[int, int]] = {
    "A1": (4, 10),
    "A2": (6, 14),
    "B1": (9, 18),
    "B2": (12, 22),
    "C1": (14, 26),
    "C2": (16, 34),
}

_SYSTEM_PROMPT = (
    "You write short guided micro-conversation cards for a self-study speaking "
    "app. The learner sees a situation and a role, HEARS one line spoken by an "
    "interlocutor (the app), and answers by SPEAKING with their own words. Later "
    "the app reveals a model response. Each card is a single exchange, NOT a "
    "script and NOT a question with options.\n"
    "Rules for every item:\n"
    '1. "setup": one short sentence describing the situation (who and where).\n'
    '2. "you": one short instruction telling the learner what to say or do in '
    "their answer.\n"
    '3. "app_line": the exact line the interlocutor says to invite the answer '
    "(a question, comment or invitation). It must sound natural when spoken.\n"
    '4. "model_response": a natural model answer the learner COULD say in one '
    "turn. Use vocabulary, grammar and sentence length appropriate to the CEFR "
    "level of the item; avoid rare words, slang or complex subordinate clauses "
    "beyond the level. Prefer first-person, everyday or work situations.\n"
    '5. Reply with ONLY a JSON object, no prose: {"items":[{"setup":"...",'
    '"you":"...","app_line":"...","model_response":"...","topic":"one of the '
    'allowed topics"}]}\n'
    "Do not include markdown fences.\n"
)

SYSTEM_PROMPT = _SYSTEM_PROMPT

_LEVEL_HINT: dict[str, str] = {
    "A1": "CEFR A1: very frequent everyday words, short simple present sentences, "
    "answers of 4-10 words.",
    "A2": "CEFR A2: everyday topics, simple past, common phrases, answers of "
    "6-14 words.",
    "B1": "CEFR B1: familiar topics with some detail, moderate sentence length, "
    "answers of 9-18 words.",
    "B2": "CEFR B2: concrete and some abstract topics, richer vocabulary, "
    "answers of 12-22 words.",
    "C1": "CEFR C1: longer, more complex and nuanced answers, 14-26 words.",
    "C2": "CEFR C2: sophisticated vocabulary and complex structures, answers of "
    "16-34 words.",
}


def build_user_prompt(
    level: str, topics: list[str], allowed: list[str] | None = None
) -> str:
    """Instrucción de una tanda de generación: pide `len(topics)` tarjetas.

    Una tarjeta por topic para forzar variedad temática sin depender del azar.
    `allowed` limita los valores válidos de 'topic' a los temas reales del nivel.
    """
    numbered = "\n".join(
        f"{i + 1}. micro-conversation card about \"{t.replace('_', ' ')}\""
        for i, t in enumerate(topics)
    )
    allowed_topics = allowed if allowed is not None else list(topics_for_level(level))
    allowed_text = ", ".join(t.replace("_", " ") for t in allowed_topics)
    return (
        f"{_LEVEL_HINT.get(level, level)}\n"
        f"Generate exactly {len(topics)} micro-conversation cards in the order "
        f"below.\n"
        f"{numbered}.\n"
        f"Allowed 'topic' values (choose the closest for each card): "
        f"{allowed_text}.\n"
    )


def _norm(text: str) -> str:
    """Normaliza para comparaciones de substring/deduplicación."""
    text = unicodedata.normalize("NFKD", text).lower()
    text = re.sub(r"[\W_]+", " ", text)
    text = text.replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def canonical_card(payload: dict, level: str | None = None) -> str:
    """Forma canónica de una tarjeta para deduplicar contenido entre tandas.

    Identifica el intercambio por su línea del interlocutor + respuesta modelo
    normalizadas; dos tarjetas que planteen el mismo turno cuentan como una.
    """
    line = _norm(payload.get("app_line") or "")
    answer = _norm(payload.get("model_response") or "")
    key = f"{line} | {answer}".strip(" |")
    return _norm(key) or _norm(payload.get("setup") or "")


def parse_content(content: str) -> list[dict]:
    """Convierte la respuesta del modelo en una lista de tarjetas crudas.

    Acepta `{"items": [...]}` o un único objeto, tolerando cercos de markdown.
    """
    text = content.strip()
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
    raise ValueError("JSON sin tarjetas")


def compose_item(
    level: str,
    raw: dict,
    *,
    item_id: str | None = None,
) -> dict | None:
    """Valida una tarjeta cruda del modelo y devuelve su payload final, o None.

    Validación determinista: setup/you/app_line/model_response no vacíos y dentro
    de las longitudes del nivel, topic permitido en el nivel y nivel conocido.
    Devuelve el dict con las mismas claves que el banco curado (id, level, topic,
    setup, you, app_line, model_response, difficulty_vector).
    """
    setup = (raw.get("setup") or "").strip()
    you = (raw.get("you") or "").strip()
    app_line = (raw.get("app_line") or "").strip()
    model_response = (raw.get("model_response") or "").strip()
    topic = (raw.get("topic") or "").strip()
    if not (setup and you and app_line and model_response):
        return None
    if level not in _BAND_TEXTUAL:
        return None
    if topic not in topics_for_level(level):
        return None
    app_min, app_max = _BAND_APP_LINE[level]
    model_min, model_max = _BAND_MODEL[level]
    app_words = len(_norm(app_line).split())
    model_words = len(_norm(model_response).split())
    setup_words = len(_norm(setup).split())
    you_words = len(_norm(you).split())
    if not app_min <= app_words <= app_max:
        return None
    if not model_min <= model_words <= model_max:
        return None
    if not 2 <= setup_words <= 20:
        return None
    if not 2 <= you_words <= 18:
        return None
    lexical, grammar, length, discourse = _BAND_TEXTUAL[level]
    payload = {
        "id": item_id,
        "level": level,
        "topic": topic,
        "setup": setup,
        "you": you,
        "app_line": app_line,
        "model_response": model_response,
        "difficulty_vector": {
            "lexical": lexical,
            "grammar": grammar,
            "length": length,
            "discourse": discourse,
        },
    }
    if item_id is None:
        payload.pop("id", None)
    return payload


def validate_payload_shape(payload: dict) -> bool:
    """Invariantes mínimas del payload ya compuesto (red de seguridad)."""
    if not payload.get("id"):
        return False
    level = payload.get("level") or ""
    if level not in _BAND_MODEL:
        return False
    if payload.get("topic") not in topics_for_level(level):
        return False
    app_min, app_max = _BAND_APP_LINE[level]
    model_min, model_max = _BAND_MODEL[level]
    if not app_min <= len(_norm(payload.get("app_line") or "").split()) <= app_max:
        return False
    if not model_min <= len(_norm(payload.get("model_response") or "").split()) <= model_max:
        return False
    for field in ("setup", "you", "app_line", "model_response"):
        if not (payload.get(field) or "").strip():
            return False
    return True
