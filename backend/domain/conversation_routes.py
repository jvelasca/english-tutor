"""Dominio de las rutas de conversation (V3.10).

Orquesta las APIs de conversación guiada por nivel CEFR basada en mini-diálogos
multi-turno: siguiente diálogo por bucket (all/failed/mastered), estado del
nivel e intentos de conversación terminada (el transcripto completo de la
conversación real con `conversation_id` se evalúa con el pipeline de evidencia
oral existente —`extract_speaking_evidence` + `scores_from_evidence` con
`task_type="conversation"`— fusionado con la señal objetiva de interacción de
los turnos persistidos).

La ruta mide práctica: el estado por nivel es `not_started` / `developing` /
`functional`. Demostrar el nivel es del Speaking Assessment y la evidencia formal
(vía `services.speaking.speaking_level`); este dominio nunca emite `demonstrated`.
"""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from domain.speaking_routes import EvidenceExtractionError  # transitorio (503)
from repositories import conversation_routes as conversation_repo
from repositories import conversations as conversations_repo
from services import speaking_llm
from services.conversation_routes import (
    CONV_MIN_STUDENT_TURNS,
    CONV_MIN_STUDENT_WORDS,
    CONVERSATION_PASS_THRESHOLD,
    LEVEL_ORDER,
    current_level,
    dialogues_for_level,
    get_dialogue,
    level_items as motor_level_items,
    review_next_dialogue,
    route_competence,
    route_gate,
)
from services.interaction import interaction_evidence
from services.speaking import scores_from_evidence
from services.translate import pick_model

# Roles de mensaje que cuentan como turno del alumno (la BD guarda "user").
_STUDENT_ROLES = frozenset({"student", "user"})


def is_valid_level(level: str) -> bool:
    return level in LEVEL_ORDER


def _dialogue_task(dialogue: dict) -> str:
    """Instrucción de evaluación de una conversación guiada.

    El extractor de evidencia recibe la tarea que el alumno debía cumplir (la
    situación, su rol, el rol del tutor, la línea con la que arrancó la
    conversación y las metas comunicativas). El transcripto del alumno que se
    evalúa es `heard`; no hay respuesta modelo (conversación abierta).
    """
    parts = []
    if dialogue.get("context"):
        parts.append(f"Scenario: {dialogue['context']}")
    if dialogue.get("student_role"):
        parts.append(f"Your role: {dialogue['student_role']}")
    if dialogue.get("tutor_role"):
        parts.append(f"The other speaker plays: {dialogue['tutor_role']}")
    if dialogue.get("opening_line"):
        parts.append(f'The other speaker opens with: "{dialogue["opening_line"]}"')
    goals = dialogue.get("communicative_goals") or []
    if goals:
        parts.append("Communicative goals you must achieve:")
        for goal in goals:
            parts.append(f"- {goal}")
    parts.append(
        "Keep a natural, fluent conversation in English until the goals are met."
    )
    return "\n".join(parts)


def _dialogue_public(dialogue: dict) -> dict:
    """Forma pública de un diálogo: todo lo que el alumno necesita para conversar."""
    return {
        "id": dialogue["id"],
        "level": dialogue.get("level", ""),
        "topic": dialogue.get("topic", ""),
        "context": dialogue.get("context", ""),
        "student_role": dialogue.get("student_role", ""),
        "tutor_role": dialogue.get("tutor_role", ""),
        "opening_line": dialogue.get("opening_line", ""),
        "communicative_goals": dialogue.get("communicative_goals", []),
    }


async def _student_turns(conversation_id: str, user_id: str) -> list[dict] | None:
    """Turnos del alumno de una conversación persistida (mensajes con contenido).

    Devuelve `None` si la conversación no existe o no pertenece al usuario.
    """
    conv = await run_in_threadpool(
        conversations_repo.get_conversation, conversation_id, user_id
    )
    if conv is None:
        return None
    return [
        m
        for m in conv.get("messages", [])
        if (m.get("role") or "").lower() in _STUDENT_ROLES and (m.get("content") or "").strip()
    ]


async def _student_speech_seconds(conversation_id: str, user_id: str) -> float | None:
    """Segundos de habla del alumno si la telemetría de turnos los observa."""
    turns = await run_in_threadpool(
        conversations_repo.get_turns, conversation_id, user_id
    )
    if not turns:
        return None
    total_ms = 0
    for turn in turns:
        if (turn.get("role") or "").lower() in _STUDENT_ROLES and turn.get(
            "duration_ms"
        ):
            total_ms += int(turn["duration_ms"])
    return round(total_ms / 1000, 1) if total_ms else None


async def _inject_interaction_objective(
    evidence: dict, conversation_id: str, user_id: str
) -> None:
    """Fusiona la señal objetiva de interacción (turnos persistidos) en la evidencia.

    Es el mismo criterio que `domain.academy._inject_interaction_objective`: solo
    cuando `interaction_evidence` observa `turn_balance` o `turn_duration` se
    asigna `evidence["interaction_objective"]` para que el scorer determinista la
    combine con la señal semántica del LLM.
    """
    turns = await run_in_threadpool(
        conversations_repo.get_turns, conversation_id, user_id
    )
    if not turns:
        return
    objective = interaction_evidence(turns)
    if (
        objective["turn_balance"] is not None
        or objective["turn_duration"] is not None
    ):
        evidence["interaction_objective"] = objective


# --- Progreso y sesión de práctica --------------------------------------------


async def next_dialogue(
    user_id: str, level: str | None = None, mode: str = "all"
) -> dict:
    """Siguiente diálogo del banco de una ruta (nuevo/failed/mastered).

    Sin `level`, elige el nivel por cobertura del banco oficial. Lanza
    `ValueError("conversation.no_failed")` si no queda nada en el bucket pedido.
    """
    attempts_rows = await run_in_threadpool(conversation_repo.list_attempts, user_id)
    if level is None:
        passed = await run_in_threadpool(
            conversation_repo.passed_dialogue_ids, user_id
        )
        level = current_level(passed)
    only_failed = mode == "failed"
    only_mastered = mode == "mastered"
    dialogue = review_next_dialogue(
        level,
        attempts_rows,
        only_failed=only_failed,
        only_mastered=only_mastered,
    )
    return _dialogue_public(dialogue)


async def dialogues_for_level_out(user_id: str, level: str) -> dict:
    """Estado por diálogo de un nivel + contadores (para el panel del nivel)."""
    attempts_rows = await run_in_threadpool(conversation_repo.list_attempts, user_id)
    items = motor_level_items(level, attempts_rows)
    gate = route_gate(level, attempts_rows)
    counts = {"mastered": 0, "failed": 0, "unseen": 0}
    for item in items:
        counts[item["state"]] = counts.get(item["state"], 0) + 1
    return {
        "level": level,
        "total": len(items),
        "mastered": counts.get("mastered", 0),
        "failed": counts.get("failed", 0),
        "unseen": counts.get("unseen", 0),
        "completed": gate["passed"],
        "items": items,
        "gate": gate,
    }


async def submit_attempt(
    user_id: str, dialogue_id: str, conversation_id: str
) -> dict | None:
    """Puntúa una conversación guiada terminada y persiste el intento.

    El transcripto se recupera SIEMPRE de la conversación persistida (los turnos
    del alumno) y se evalúa como respuesta abierta multi-turno: el LLM local
    extrae la evidencia sobre la tarea del diálogo y el scorer determinista
    calcula criterios y overall (`task_type="conversation"`) fusionando la señal
    objetiva de interacción. Si el extractor no produce evidencia válida se lanza
    `EvidenceExtractionError` (transitorio). None si el diálogo no existe o la
    conversación no es del usuario; `ValueError("conversation.too_short")` si el
    alumno apenas conversó (mínimo de turnos/palabras no alcanzado).
    """
    dialogue = get_dialogue(dialogue_id)
    if dialogue is None:
        return None
    turns = await _student_turns(conversation_id, user_id)
    if turns is None:
        return None
    heard = "\n".join(m["content"].strip() for m in turns).strip()
    word_count = len(heard.split())
    if len(turns) < CONV_MIN_STUDENT_TURNS or word_count < CONV_MIN_STUDENT_WORDS:
        raise ValueError("conversation.too_short")

    model = await pick_model(None)
    task = _dialogue_task(dialogue)
    evidence = await speaking_llm.extract_speaking_evidence(task, heard, model)
    if evidence is None:
        raise EvidenceExtractionError(
            "el extractor de evidencia no devolvió una salida válida"
        )

    await _inject_interaction_objective(evidence, conversation_id, user_id)

    duration_seconds = await _student_speech_seconds(conversation_id, user_id)
    scored = scores_from_evidence(
        evidence, heard, duration_seconds, task_type="conversation"
    )
    overall = float(scored["overall"])
    passed = overall >= CONVERSATION_PASS_THRESHOLD
    topic = dialogue.get("topic", "")
    await run_in_threadpool(
        conversation_repo.record_attempt,
        user_id,
        dialogue_id,
        dialogue.get("level", ""),
        overall,
        passed,
        scored["criteria"],
        topic,
    )
    return {
        "dialogue_id": dialogue_id,
        "level": dialogue.get("level", ""),
        "opening_line": dialogue.get("opening_line", ""),
        "heard": heard,
        "overall": overall,
        "passed": passed,
        "criteria": scored["criteria"],
        "observed": scored["observed"],
        "interaction_quality": scored.get("interaction_quality", {}),
        "topic": topic,
        "communicative_goals": dialogue.get("communicative_goals", []),
    }


async def get_stats(user_id: str) -> dict:
    """Progreso del mapa de rutas de conversation (niveles + puertas honestas)."""
    attempts_rows = await run_in_threadpool(conversation_repo.list_attempts, user_id)
    passed_rows = [r for r in attempts_rows if r.get("passed")]
    accuracy = (
        round(len(passed_rows) / len(attempts_rows) * 100, 1)
        if attempts_rows
        else None
    )
    levels: list[dict] = []
    for level in LEVEL_ORDER:
        gate = route_gate(level, attempts_rows)
        items = motor_level_items(level, attempts_rows)
        mastered = sum(1 for i in items if i["state"] == "mastered")
        levels.append(
            {
                "level": level,
                "total": len(items),
                "mastered": mastered,
                "completed": gate["passed"],
                "coverage_pct": gate["coverage_pct"],
                "accuracy": gate["accuracy"],
                "gate": gate,
                "state": next(
                    (
                        c["state"]
                        for c in route_competence(attempts_rows)
                        if c["level"] == level
                    ),
                    "not_started",
                ),
            }
        )
    passed_official: set[str] = set()
    for row in attempts_rows:
        did = row.get("dialogue_id")
        if did and get_dialogue(did) is not None and row.get("passed"):
            passed_official.add(did)
    level = current_level(passed_official)
    completed = all(g["gate"]["passed"] for g in levels if g["total"] > 0)
    return {
        "attempts": len(attempts_rows),
        "passed": len(passed_rows),
        "accuracy": accuracy,
        "level": level,
        "completed": completed,
        "levels": levels,
    }
