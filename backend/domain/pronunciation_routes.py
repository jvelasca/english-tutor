"""Dominio de las rutas de pronunciation (V3.9).

Orquesta las APIs de práctica read-aloud por nivel CEFR basada en frases modelo:
siguiente frase por bucket (all/failed/mastered), estado del nivel, intentos
(transcripción Whisper en el router + `score_pronunciation` determinista +
persistencia) y estadísticas con puerta de ruta honesta.

La ruta mide práctica: el estado por nivel es `not_started` / `developing` /
`functional`. Demostrar el nivel es del Speaking Assessment y la evidencia formal
(vía `services.speaking.speaking_level`); este dominio nunca emite `demonstrated`.
"""
from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from repositories import pronunciation_routes as pron_repo
from services.fluency import compute_fluency
from services.listening import difficulty_from_vector
from services.pronunciation import score_pronunciation
from services.pronunciation_routes import (
    LEVEL_ORDER,
    current_level,
    get_phrase,
    level_items as motor_level_items,
    phrases_for_level,
    review_next_phrase,
    route_competence,
    route_gate,
)


def _phrase_public(phrase: dict) -> dict:
    """Forma pública de una frase: texto + tema + dificultad."""
    return {
        "id": phrase["id"],
        "level": phrase.get("level", ""),
        "script": phrase.get("script", ""),
        "topic": phrase.get("topic", ""),
        "difficulty": difficulty_from_vector(phrase.get("difficulty_vector", {})),
        "difficulty_vector": phrase.get("difficulty_vector", {}),
    }


async def next_phrase(
    user_id: str, level: str | None = None, mode: str = "all"
) -> dict:
    """Siguiente frase del pool de una ruta (nueva/failed/mastered).

    Sin `level`, elige el nivel por cobertura del banco oficial. Lanza
    `ValueError("pronunciation.no_failed")` si no queda nada en el bucket pedido.
    """
    attempts_rows = await run_in_threadpool(pron_repo.list_attempts, user_id)
    if level is None:
        passed = await run_in_threadpool(pron_repo.passed_phrase_ids, user_id)
        level = current_level(passed)
    only_failed = mode == "failed"
    only_mastered = mode == "mastered"
    phrase = review_next_phrase(
        level,
        attempts_rows,
        only_failed=only_failed,
        only_mastered=only_mastered,
    )
    return _phrase_public(phrase)


async def phrases_for_level_out(user_id: str, level: str) -> dict:
    """Estado por frase de un nivel + contadores (para el panel del nivel)."""
    attempts_rows = await run_in_threadpool(pron_repo.list_attempts, user_id)
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
    user_id: str,
    phrase_id: str,
    heard: str,
    duration_seconds: float | None = None,
) -> dict | None:
    """Puntúa una lectura en voz alta (determinista) y persiste el intento.

    Compara la transcripción (`heard`) con la frase esperada del banco mediante
    `score_pronunciation` (composite fonético sin LLM) y `compute_fluency`.
    `passed = ok` (score >= 80). None si la frase no existe.
    """
    phrase = get_phrase(phrase_id)
    if phrase is None:
        return None
    script = phrase.get("script", "")
    result = score_pronunciation(script, heard)
    fluency = compute_fluency(heard, duration_seconds)
    passed = bool(result["ok"])
    topic = phrase.get("topic", "")
    difficulty = difficulty_from_vector(phrase.get("difficulty_vector", {}))
    await run_in_threadpool(
        pron_repo.record_attempt,
        user_id,
        phrase_id,
        phrase.get("level", ""),
        int(result["score"]),
        passed,
        difficulty,
        topic,
    )
    return {
        "phrase_id": phrase_id,
        "level": phrase.get("level", ""),
        "script": script,
        "heard": result["heard"],
        "score": int(result["score"]),
        "grade": result["level"],
        "passed": passed,
        "word_accuracy": int(result["word_accuracy"]),
        "phonetic_score": int(result["phonetic_score"]),
        "phoneme_accuracy_proxy": int(result["phoneme_accuracy_proxy"]),
        "prosody_proxy": int(result["prosody_proxy"]),
        "pronunciation_source": result["pronunciation_source"],
        "breakdown": result["breakdown"],
        "phoneme_breakdown": result["phoneme_breakdown"],
        "fluency": fluency,
        "topic": topic,
        "difficulty": difficulty,
    }


async def get_stats(user_id: str) -> dict:
    """Progreso del mapa de rutas de pronunciation (niveles + puertas honestas)."""
    attempts_rows = await run_in_threadpool(pron_repo.list_attempts, user_id)
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
    # Nivel actual: primer nivel oficial sin dominar; si todos, el último.
    passed_official: set[str] = set()
    for row in attempts_rows:
        pid = row.get("phrase_id")
        base = get_phrase(pid) if pid else None
        if base is not None and row.get("passed"):
            passed_official.add(pid)
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


def is_valid_level(level: str) -> bool:
    return level in LEVEL_ORDER
