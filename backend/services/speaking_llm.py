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
    # task_achievement 2.0: sub-dimensiones graduadas (P0-1) en lugar de un solo bool.
    "task_completion",
    "task_relevance",
    "task_coverage",
    "task_appropriateness",
    # GrammarEvidence 2.0: desglose por error con severidad (P0-2).
    "grammar_error_details",
    # LexicalEvidence 2.0: riqueza léxica más allá del TTR (P1-2). El scorer
    # determinista combina diversidad/range (deterministas) con estas señales
    # semánticas del LLM (sofisticación, precisión, colocaciones).
    "lexical_sophistication",
    "lexical_precision",
    "collocations",
    # FluencyEvidence 2.0: fluidez más allá de la velocidad (P1-3). `smoothness` y
    # `rhythm` capturan la suavidad/ritmo del discurso, que el scorer combina con
    # la banda de velocidad determinista (speech_rate).
    "smoothness",
    "rhythm",
    # InteractionEvidence 2.0 (P1-4): sub-dimensiones conversacionales que el
    # scorer combina determinísticamente en lugar de una única estimación subjetiva
    # de `interaction`. Siguen siendo evidencia semántica del LLM (hasta tener un
    # conversation engine con señal objetiva de turnos/latencia).
    "turn_completion",
    "follow_up_questions",
    "appropriate_responses",
    "topic_maintenance",
    "clarification_requests",
    "repair",
)

# Severidades de error gramatical reconocidas (GrammarEvidence 2.0). El scorer
# determinista las pondera (minor < major < critical); el LLM solo las declara.
GRAMMAR_SEVERITIES: tuple[str, ...] = ("minor", "major", "critical")

# Taxonomía orientativa de tipos de error gramatical. No es exhaustiva: el parser
# acepta cualquier `type` no vacío y lo normaliza a minúsculas para trazabilidad.
GRAMMAR_ERROR_TYPES: tuple[str, ...] = (
    "verb_tense",
    "article",
    "preposition",
    "word_order",
    "agreement",
    "conditional",
    "subordination",
    "pronoun",
    "auxiliary",
    "other",
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
        "takes turns, responds appropriately and keeps the exchange going.\n"
        '- "task_completion": number between 0.0 and 1.0 — how fully the task '
        "was carried out.\n"
        '- "task_relevance": number between 0.0 and 1.0 — how on-topic and '
        "relevant the answer is.\n"
        '- "task_coverage": number between 0.0 and 1.0 — how much of the task\'s '
        "expected content is covered.\n"
        '- "task_appropriateness": number between 0.0 and 1.0 — how appropriate '
        "the answer is for the task context/register.\n"
        '- "grammar_error_details": array of objects with "type" (string, e.g. '
        '"verb_tense", "article", "preposition", "word_order", "agreement") and '
        '"severity" ("minor", "major" or "critical") — a per-error breakdown of '
        "grammatical mistakes.\n"
        '- "lexical_sophistication": number between 0.0 and 1.0 — how advanced/'
        "precise the vocabulary is (beyond simple everyday words).\n"
        '- "lexical_precision": number between 0.0 and 1.0 — how precisely words '
        "are chosen for the intended meaning.\n"
        '- "collocations": number between 0.0 and 1.0 — how naturally words are '
        "combined into common English collocations.\n"
        '- "smoothness": number between 0.0 and 1.0 — how smooth/continuous the '
        "speech flow is.\n"
        '- "rhythm": number between 0.0 and 1.0 — how natural the stress/rhythm '
        "of the speech is.\n"
        '- "turn_completion": number between 0.0 and 1.0 — how fully the student '
        "completes their conversational turns.\n"
        '- "follow_up_questions": number between 0.0 and 1.0 — how much the '
        "student asks follow-up questions to keep the exchange going.\n"
        '- "appropriate_responses": number between 0.0 and 1.0 — how appropriately '
        "the student responds to what was said.\n"
        '- "topic_maintenance": number between 0.0 and 1.0 — how well the student '
        "stays on topic.\n"
        '- "clarification_requests": number between 0.0 and 1.0 — how appropriately '
        "the student asks for clarification when needed.\n"
        '- "repair": number between 0.0 and 1.0 — how well the student recovers or '
        "rephrases after a communication breakdown or misunderstanding.\n\n"
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


def _parse_grammar_details(data: dict) -> list[dict] | None:
    """Parsea `grammar_error_details` (lista opcional de `{type, severity}`).

    Devuelve una lista canónica de entradas válidas (`type` no vacío y `severity`
    en `GRAMMAR_SEVERITIES`) o `None` si el campo no está presente o no queda
    ninguna entrada válida. Las entradas inválidas se descartan sin invalidar la
    evidencia; el LLM solo declara, el scorer determinista pondera la severidad.
    """
    raw = data.get("grammar_error_details")
    if not isinstance(raw, list):
        return None
    details: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        severity = item.get("severity")
        error_type = item.get("type")
        if severity not in GRAMMAR_SEVERITIES:
            continue
        if not isinstance(error_type, str) or not error_type.strip():
            continue
        details.append({"type": error_type.strip().lower(), "severity": severity})
    return details or None


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
    task_completion = _parse_float_field(data, "task_completion", None)
    task_relevance = _parse_float_field(data, "task_relevance", None)
    task_coverage = _parse_float_field(data, "task_coverage", None)
    task_appropriateness = _parse_float_field(data, "task_appropriateness", None)
    grammar_details = _parse_grammar_details(data)
    lexical_sophistication = _parse_float_field(data, "lexical_sophistication", None)
    lexical_precision = _parse_float_field(data, "lexical_precision", None)
    collocations = _parse_float_field(data, "collocations", None)
    smoothness = _parse_float_field(data, "smoothness", None)
    rhythm = _parse_float_field(data, "rhythm", None)
    turn_completion = _parse_float_field(data, "turn_completion", None)
    follow_up_questions = _parse_float_field(data, "follow_up_questions", None)
    appropriate_responses = _parse_float_field(data, "appropriate_responses", None)
    topic_maintenance = _parse_float_field(data, "topic_maintenance", None)
    clarification_requests = _parse_float_field(data, "clarification_requests", None)
    repair = _parse_float_field(data, "repair", None)

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
    if task_completion is not None:
        result["task_completion"] = task_completion
    if task_relevance is not None:
        result["task_relevance"] = task_relevance
    if task_coverage is not None:
        result["task_coverage"] = task_coverage
    if task_appropriateness is not None:
        result["task_appropriateness"] = task_appropriateness
    if grammar_details is not None:
        result["grammar_error_details"] = grammar_details
    if lexical_sophistication is not None:
        result["lexical_sophistication"] = lexical_sophistication
    if lexical_precision is not None:
        result["lexical_precision"] = lexical_precision
    if collocations is not None:
        result["collocations"] = collocations
    if smoothness is not None:
        result["smoothness"] = smoothness
    if rhythm is not None:
        result["rhythm"] = rhythm
    if turn_completion is not None:
        result["turn_completion"] = turn_completion
    if follow_up_questions is not None:
        result["follow_up_questions"] = follow_up_questions
    if appropriate_responses is not None:
        result["appropriate_responses"] = appropriate_responses
    if topic_maintenance is not None:
        result["topic_maintenance"] = topic_maintenance
    if clarification_requests is not None:
        result["clarification_requests"] = clarification_requests
    if repair is not None:
        result["repair"] = repair
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
