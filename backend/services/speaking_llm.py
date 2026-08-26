"""Extracción de evidencia de speaking con LLM (llama a Ollama de forma asíncrona).

Este módulo construye el prompt que pide al modelo EXTRAER evidencia estructurada
de una respuesta oral libre (frente a una tarea), y parsea/valida la respuesta JSON.
El LLM extrae; el scorer determinista (`services.speaking`) calcula el score.
"""
from __future__ import annotations

import json
import re

from schemas.chat import ChatMessage
from services import llm

# Campos que el LLM debe devolver como evidencia estructurada (no como nota).
SPEAKING_EVIDENCE_FIELDS: tuple[str, ...] = (
    "task_achieved",
    "grammar_errors",
    "lexical_tokens",
    "coherence",
)

# Campos opcionales de discurso que enriquecen la evidencia sin romper el contrato
# (se parsean con default si el LLM no los devuelve).
SPEAKING_EVIDENCE_OPTIONAL_FIELDS: tuple[str, ...] = (
    "cohesion",
    "discourse_markers",
    "self_corrections",
    "hesitations",
    "repetitions",
    "interaction",
)


def build_speaking_prompt(task: str, heard: str) -> list[dict]:
    """Construye los mensajes (system + user) que piden al modelo extraer evidencia.

    El system prompt deja claro que el modelo es un EXTRACTOR (no un calificador):
    debe devolver solo un objeto JSON, sin texto adicional, con las claves y tipos
    obligatorios de `SPEAKING_EVIDENCE_FIELDS` y los opcionales de
    `SPEAKING_EVIDENCE_OPTIONAL_FIELDS`. El mensaje user lleva la tarea y la
    transcripción etiquetadas con `TASK:` y `STUDENT:`.
    """
    system = (
        "You are an evidence extractor for an English speaking assessment. "
        "You do NOT grade, score, or label the student's level. Your only job is "
        "to read a free spoken answer to a task and extract structured evidence "
        "from it.\n\n"
        "Respond with ONLY a single JSON object and no other text, with these "
        "required keys and types:\n"
        '- "task_achieved": boolean — whether the answer fulfils what the task '
        "asks.\n"
        '- "grammar_errors": integer >= 0 — number of grammatical errors '
        "detected.\n"
        '- "lexical_tokens": array of strings — relevant content words the '
        "student used correctly, in lowercase.\n"
        '- "coherence": number between 0.0 and 1.0 — how coherent/fluent the '
        "discourse is.\n\n"
        "You MAY also include these optional keys (do NOT invent them if you are "
        "unsure; use a sensible default):\n"
        '- "cohesion": number between 0.0 and 1.0 — how well ideas are linked.\n'
        '- "discourse_markers": integer >= 0 — number of linking words (first, '
        "then, because, finally…).\n"
        '- "self_corrections": integer >= 0 — times the student corrected '
        "themselves.\n"
        '- "hesitations": integer >= 0 — filled pauses or false starts.\n'
        '- "repetitions": integer >= 0 — words or phrases repeated.\n'
        '- "interaction": number between 0.0 and 1.0 — how well the student '
        "takes turns, responds appropriately and keeps the exchange going.\n\n"
        "Example of the expected JSON:\n"
        '{"task_achieved": true, "grammar_errors": 1, '
        '"lexical_tokens": ["student", "live"], "coherence": 0.8, '
        '"discourse_markers": 2, "self_corrections": 0, "hesitations": 1, '
        '"repetitions": 0, "interaction": 0.7}\n\n'
        "Do not output any text before or after the JSON. Do not wrap it in "
        "markdown code fences."
    )
    user = f"TASK: {task}\nSTUDENT: {heard}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _extract_json(raw: str) -> object | None:
    """Extrae el primer objeto JSON de `raw`, tolerando fences de markdown y texto
    suelto alrededor. Devuelve el valor decodificado o None si no hay JSON válido."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    return _decode_object(text)


def _decode_object(text: str) -> object | None:
    """Decodifica un objeto JSON del texto: primero con raw_decode (ignora lo que
    venga después del JSON) y, si falla, de la primera '{' a la última '}'."""
    try:
        obj, _ = json.JSONDecoder().raw_decode(text)
        return obj
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def _parse_float_field(data: dict, key: str, default: float | None) -> float | None:
    """Valida un campo opcional 0..1 (o `default` si falta/tipo inválido)."""
    value = data.get(key, default)
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return round(max(0.0, min(1.0, float(value))), 3)


def _parse_count_field(data: dict, key: str, default: int = 0) -> int:
    """Valida un campo opcional entero >= 0 (o `default` si falta/tipo inválido)."""
    value = data.get(key, default)
    # `type(...) is int` (y no isinstance) para rechazar bool; inválido → default.
    if type(value) is not int or value < 0:
        return default
    return value


def parse_speaking_evidence(raw: str) -> dict | None:
    """Parsea y normaliza la salida JSON del LLM en evidencia estructurada.

    Devuelve un dict con las claves de `SPEAKING_EVIDENCE_FIELDS` (obligatorias) y
    las de `SPEAKING_EVIDENCE_OPTIONAL_FIELDS` (con default si faltan), o `None` si
    la salida no se puede extraer o no supera la validación de tipos.
    """
    data = _extract_json(raw)
    if not isinstance(data, dict):
        return None
    if not all(key in data for key in SPEAKING_EVIDENCE_FIELDS):
        return None

    task_achieved = data["task_achieved"]
    if type(task_achieved) is not bool:
        return None

    grammar_errors = data["grammar_errors"]
    # `type(...) is int` (y no isinstance) para rechazar bool, que es subclase de int.
    if type(grammar_errors) is not int or grammar_errors < 0:
        return None

    lexical_raw = data["lexical_tokens"]
    if not isinstance(lexical_raw, list):
        return None
    lexical_tokens: list[str] = []
    for token in lexical_raw:
        if not isinstance(token, str):
            return None
        cleaned = token.strip().lower()
        if cleaned:
            lexical_tokens.append(cleaned)

    coherence = data["coherence"]
    # bool también se rechaza: un booleano no es una puntuación de coherencia válida.
    if isinstance(coherence, bool) or not isinstance(coherence, (int, float)):
        return None
    coherence = round(max(0.0, min(1.0, float(coherence))), 3)

    cohesion = _parse_float_field(data, "cohesion", None)
    discourse_markers = _parse_count_field(data, "discourse_markers", 0)
    self_corrections = _parse_count_field(data, "self_corrections", 0)
    hesitations = _parse_count_field(data, "hesitations", 0)
    repetitions = _parse_count_field(data, "repetitions", 0)
    interaction = _parse_float_field(data, "interaction", None)

    result: dict = {
        "task_achieved": task_achieved,
        "grammar_errors": grammar_errors,
        "lexical_tokens": lexical_tokens,
        "coherence": coherence,
        "discourse_markers": discourse_markers,
        "self_corrections": self_corrections,
        "hesitations": hesitations,
        "repetitions": repetitions,
    }
    if cohesion is not None:
        result["cohesion"] = cohesion
    if interaction is not None:
        result["interaction"] = interaction
    return result


async def extract_speaking_evidence(
    task: str,
    heard: str,
    model: str,
    temperature: float = 0.0,
) -> dict | None:
    """Extrae evidencia de una respuesta oral libre llamando a Ollama.

    Devuelve el dict normalizado de parse_speaking_evidence, o None si el LLM no
    produjo una salida JSON válida."""
    msgs = build_speaking_prompt(task, heard)
    system = msgs[0]["content"]
    user = msgs[1]["content"]
    response = await llm.chat_once(
        messages=[ChatMessage(role="user", content=user)],
        model=model,
        temperature=temperature,
        system_prompt=system,
    )
    return parse_speaking_evidence(response.content)
