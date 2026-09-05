"""Dominio de las rutas de vocabulary (V3.11).

Orquesta las APIs de práctica MC determinista por nivel CEFR basada en los checks
de vocabulary del currículo oficial (`objectives[].checks` con skill
"vocabulary"): siguiente pregunta por bucket (all/failed/mastered), estado del
nivel e intentos (un POST /attempt con la opción elegida se puntúa al instante:
acierto ⇒ superado). El motor puro compartido con Grammar vive en
`services.quiz_routes` (parametrizado por skill); aquí solo se ata a vocabulary y
a su tabla de intentos.

La ruta mide práctica: el estado por nivel es `not_started` / `developing` /
`functional`. Demostrar el nivel es de los exámenes/escalera formales del curso;
este dominio nunca emite `demonstrated`.
"""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import vocabulary_routes as vocab_repo
from services import quiz_routes as engine

SKILL = "vocabulary"


def is_valid_level(level: str) -> bool:
    return level in engine.LEVEL_ORDER


def _question_public(check: dict) -> dict:
    """Forma pública de un check: NUNCA incluye `correct_index`."""
    return {
        "check_id": check["check_id"],
        "level": check.get("level", ""),
        "topic": check.get("topic", ""),
        "prompt": check.get("prompt", ""),
        "options": check.get("options", []),
    }


async def next_question(
    user_id: str, level: str | None = None, mode: str = "all"
) -> dict:
    """Siguiente check del banco de una ruta (nuevo/failed/mastered).

    Sin `level`, elige el nivel por cobertura del banco oficial. Lanza
    `ValueError("vocabulary.no_failed")` si no queda nada en el bucket pedido.
    """
    attempts_rows = await run_in_threadpool(vocab_repo.list_attempts, user_id)
    if level is None:
        passed = await run_in_threadpool(vocab_repo.passed_check_ids, user_id)
        level = engine.current_level(SKILL, passed)
    only_failed = mode == "failed"
    only_mastered = mode == "mastered"
    check = engine.review_next_question(
        SKILL,
        level,
        attempts_rows,
        only_failed=only_failed,
        only_mastered=only_mastered,
    )
    return _question_public(check)


async def items_for_level_out(user_id: str, level: str) -> dict:
    """Estado por check de un nivel + contadores (para el panel del nivel)."""
    attempts_rows = await run_in_threadpool(vocab_repo.list_attempts, user_id)
    items = engine.level_items(SKILL, level, attempts_rows)
    gate = engine.route_gate(SKILL, level, attempts_rows)
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
    user_id: str, check_id: str, selected_index: int
) -> dict | None:
    """Puntúa una respuesta MC (determinista) y persiste el intento.

    `passed = selected_index == correct_index` y `score` es 100.0/0.0. Lanza
    `ValueError("vocabulary.bad_option")` si `selected_index` está fuera de rango
    de las opciones del check. None si el check no existe.
    """
    check = engine.get_check(SKILL, check_id)
    if check is None:
        return None
    options = check.get("options", [])
    if not 0 <= selected_index < len(options):
        raise ValueError("vocabulary.bad_option")
    correct = bool(selected_index == check.get("correct_index", -1))
    score = 100.0 if correct else 0.0
    passed = correct
    topic = check.get("topic", "")
    await run_in_threadpool(
        vocab_repo.record_attempt,
        user_id,
        check_id,
        check.get("level", ""),
        score,
        passed,
        topic,
    )
    return {
        "check_id": check_id,
        "level": check.get("level", ""),
        "topic": topic,
        "prompt": check.get("prompt", ""),
        "options": options,
        "correct_index": int(check.get("correct_index", -1)),
        "selected_index": selected_index,
        "passed": passed,
        "score": score,
    }


async def get_stats(user_id: str) -> dict:
    """Progreso del mapa de rutas de vocabulary (niveles + puertas honestas)."""
    attempts_rows = await run_in_threadpool(vocab_repo.list_attempts, user_id)
    passed_rows = [r for r in attempts_rows if r.get("passed")]
    accuracy = (
        round(len(passed_rows) / len(attempts_rows) * 100, 1)
        if attempts_rows
        else None
    )
    levels: list[dict] = []
    for level in engine.LEVEL_ORDER:
        gate = engine.route_gate(SKILL, level, attempts_rows)
        items = engine.level_items(SKILL, level, attempts_rows)
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
                        for c in engine.route_competence(SKILL, attempts_rows)
                        if c["level"] == level
                    ),
                    "not_started",
                ),
            }
        )
    passed_official: set[str] = set()
    for row in attempts_rows:
        cid = row.get("check_id")
        if cid and engine.get_check(SKILL, cid) is not None and row.get("passed"):
            passed_official.add(cid)
    level = engine.current_level(SKILL, passed_official)
    completed = all(g["gate"]["passed"] for g in levels if g["total"] > 0)
    return {
        "attempts": len(attempts_rows),
        "passed": len(passed_rows),
        "accuracy": accuracy,
        "level": level,
        "completed": completed,
        "levels": levels,
    }
