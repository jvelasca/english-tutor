"""Extracción de evidencia de writing con LLM (llama a Ollama de forma asíncrona).

Este módulo construye el prompt que pide al modelo EXTRAER evidencia estructurada
de una producción escrita libre (frente a una tarea), y parsea/valida la respuesta
JSON. El LLM extrae; el scorer determinista (`services.writing`) calcula el score.
"""
from __future__ import annotations

import json
import re

from schemas.chat import ChatMessage
from services import llm

# Campos que el LLM debe devolver como evidencia estructurada (no como nota).
WRITING_EVIDENCE_FIELDS: tuple[str, ...] = (
    "task_completed",
    "grammar_errors",
    "lexical_tokens",
    "organization",
    "coherence",
    "register",
)


def build_writing_prompt(task: str, text: str) -> list[dict]:
    """Construye los mensajes (system + user) que piden al modelo extraer evidencia.

    El system prompt deja claro que el modelo es un EXTRACTOR (no un calificador):
    debe devolver solo un objeto JSON, sin texto adicional, con exactamente las claves
    y tipos de `WRITING_EVIDENCE_FIELDS`. El mensaje user lleva la tarea y el texto
    etiquetados con `TASK:` y `STUDENT:`.
    """
    system = (
        "You are an evidence extractor for an English writing assessment. "
        "You do NOT grade, score, or label the student's level. Your only job is "
        "to read a written answer to a task and extract structured evidence "
        "from it.\n\n"
        "Respond with ONLY a single JSON object and no other text, with exactly "
        "these keys and types:\n"
        '- "task_completed": boolean — whether the answer fulfils what the task '
        "asks.\n"
        '- "grammar_errors": integer >= 0 — number of grammatical errors '
        "detected.\n"
        '- "lexical_tokens": array of strings — relevant content words the '
        "student used correctly, in lowercase.\n"
        '- "organization": number between 0.0 and 1.0 — how clear the structure '
        "and logical order are.\n"
        '- "coherence": number between 0.0 and 1.0 — how coherent the discourse '
        "is.\n"
        '- "register": number between 0.0 and 1.0 — how appropriate the style/'
        "register is for the task.\n\n"
        "Example of the expected JSON:\n"
        '{"task_completed": true, "grammar_errors": 1, '
        '"lexical_tokens": ["student", "live"], "organization": 0.8, '
        '"coherence": 0.8, "register": 0.7}\n\n'
        "Do not output any text before or after the JSON. Do not wrap it in "
        "markdown code fences."
    )
    user = f"TASK: {task}\nSTUDENT: {text}"
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


def parse_writing_evidence(raw: str) -> dict | None:
    """Parsea y normaliza la salida JSON del LLM en evidencia estructurada.

    Devuelve un dict con exactamente las claves de `WRITING_EVIDENCE_FIELDS`, o
    `None` si la salida no se puede extraer o no supera la validación de tipos.
    """
    data = _extract_json(raw)
    if not isinstance(data, dict):
        return None
    if not all(key in data for key in WRITING_EVIDENCE_FIELDS):
        return None

    task_completed = data["task_completed"]
    if type(task_completed) is not bool:
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

    # organization/coherence/register: bool se rechaza (no es una puntuación válida).
    organization = data["organization"]
    if isinstance(organization, bool) or not isinstance(organization, (int, float)):
        return None
    organization = round(max(0.0, min(1.0, float(organization))), 3)

    coherence = data["coherence"]
    if isinstance(coherence, bool) or not isinstance(coherence, (int, float)):
        return None
    coherence = round(max(0.0, min(1.0, float(coherence))), 3)

    register = data["register"]
    if isinstance(register, bool) or not isinstance(register, (int, float)):
        return None
    register = round(max(0.0, min(1.0, float(register))), 3)

    return {
        "task_completed": task_completed,
        "grammar_errors": grammar_errors,
        "lexical_tokens": lexical_tokens,
        "organization": organization,
        "coherence": coherence,
        "register": register,
    }


async def extract_writing_evidence(
    task: str,
    text: str,
    model: str,
    temperature: float = 0.0,
) -> dict | None:
    """Extrae evidencia de una producción escrita libre llamando a Ollama.

    Devuelve el dict normalizado de parse_writing_evidence, o None si el LLM no
    produjo una salida JSON válida."""
    msgs = build_writing_prompt(task, text)
    system = msgs[0]["content"]
    user = msgs[1]["content"]
    response = await llm.chat_once(
        messages=[ChatMessage(role="user", content=user)],
        model=model,
        temperature=temperature,
        system_prompt=system,
    )
    return parse_writing_evidence(response.content)
