"""Repositorio del estado de la Academy (SQLite): matrícula, mastery, evaluaciones
y completitud de niveles. El contenido no vive aquí (JSON en services.curriculum)."""

from __future__ import annotations

import json
from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def enroll(user_id: str, level_id: str, level: str) -> bool:
    """Matricula al usuario en un nivel (upsert). False si el usuario no existe."""
    if get_user(user_id) is None:
        return False
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO academy_enrollments "
            "(user_id, level_id, level, status, enrolled_at, updated_at) "
            "VALUES (?, ?, ?, 'active', ?, ?) "
            "ON CONFLICT(user_id, level_id) DO UPDATE SET "
            "level = excluded.level, updated_at = excluded.updated_at",
            (user_id, level_id, level, now, now),
        )
    return True


def get_enrollment(user_id: str, level_id: str) -> dict | None:
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT user_id, level_id, level, status, enrolled_at, updated_at "
            "FROM academy_enrollments WHERE user_id = ? AND level_id = ?",
            (user_id, level_id),
        ).fetchone()
    return dict(row) if row is not None else None


def list_enrollments(user_id: str) -> list[dict]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT user_id, level_id, level, status, enrolled_at, updated_at "
            "FROM academy_enrollments WHERE user_id = ? ORDER BY enrolled_at ASC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def set_enrollment_status(user_id: str, level_id: str, status: str) -> bool:
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "UPDATE academy_enrollments SET status = ?, updated_at = ? "
            "WHERE user_id = ? AND level_id = ?",
            (status, _now(), user_id, level_id),
        )
    return cur.rowcount > 0


def get_skill_row(user_id: str, level_id: str, skill: str) -> dict | None:
    """Lee el estado completo de mastery de una destreza en un nivel, o None."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT score, recent_score, confidence, streak, attempts, last_seen_at "
            "FROM academy_skill_mastery WHERE user_id = ? AND level_id = ? "
            "AND skill = ?",
            (user_id, level_id, skill),
        ).fetchone()
    return dict(row) if row is not None else None


def apply_skill_evidence(
    user_id: str, level_id: str, skill: str, state: dict
) -> bool:
    """Persiste el estado completo de mastery de una destreza (upsert, sin MAX).

    `state` es el resultado de `services.academy.next_mastery_state`. Guardar la
    fila completa (y no el máximo histórico) permite que el dominio detecte
    deterioro de la destreza."""
    if get_user(user_id) is None:
        return False
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO academy_skill_mastery "
            "(user_id, level_id, skill, score, recent_score, confidence, streak, "
            "attempts, last_seen_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, level_id, skill) DO UPDATE SET "
            "score = excluded.score, recent_score = excluded.recent_score, "
            "confidence = excluded.confidence, streak = excluded.streak, "
            "attempts = excluded.attempts, last_seen_at = excluded.last_seen_at, "
            "updated_at = excluded.updated_at",
            (
                user_id,
                level_id,
                skill,
                state["score"],
                state["recent_score"],
                state["confidence"],
                state["streak"],
                state["attempts"],
                state.get("last_seen_at") or now,
                now,
            ),
        )
    return True


def get_skill_mastery(user_id: str, level_id: str) -> dict[str, float]:
    """Mapa destreza → puntuación de mastery actual en un nivel."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT skill, score FROM academy_skill_mastery "
            "WHERE user_id = ? AND level_id = ?",
            (user_id, level_id),
        ).fetchall()
    return {r["skill"]: r["score"] for r in rows}


def list_skill_mastery(user_id: str) -> list[dict]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT level_id, skill, score, updated_at FROM academy_skill_mastery "
            "WHERE user_id = ? ORDER BY level_id ASC, skill ASC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# --- Mastery por objetivo (fuente de verdad del progreso curricular) -------


def get_objective_row(
    user_id: str, level_id: str, objective_id: str, skill: str
) -> dict | None:
    """Lee el estado completo de mastery de una destreza en un objetivo, o None."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT score, recent_score, confidence, streak, attempts, last_seen_at "
            "FROM academy_objective_mastery WHERE user_id = ? AND level_id = ? "
            "AND objective_id = ? AND skill = ?",
            (user_id, level_id, objective_id, skill),
        ).fetchone()
    return dict(row) if row is not None else None


def apply_objective_evidence(
    user_id: str, level_id: str, objective_id: str, skill: str, state: dict
) -> bool:
    """Persiste el estado completo de mastery de una destreza en un objetivo.

    `state` es el resultado de `services.academy.next_mastery_state`. La clave es
    (user, level, objective, skill): el dominio de una destreza en un objetivo no
    se contagia a otros objetivos que comparten esa misma destreza."""
    if get_user(user_id) is None:
        return False
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO academy_objective_mastery "
            "(user_id, level_id, objective_id, skill, score, recent_score, "
            "confidence, streak, attempts, last_seen_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, level_id, objective_id, skill) DO UPDATE SET "
            "score = excluded.score, recent_score = excluded.recent_score, "
            "confidence = excluded.confidence, streak = excluded.streak, "
            "attempts = excluded.attempts, last_seen_at = excluded.last_seen_at, "
            "updated_at = excluded.updated_at",
            (
                user_id,
                level_id,
                objective_id,
                skill,
                state["score"],
                state["recent_score"],
                state["confidence"],
                state["streak"],
                state["attempts"],
                state.get("last_seen_at") or now,
                now,
            ),
        )
    return True


def get_objective_mastery(
    user_id: str, level_id: str, objective_id: str
) -> dict[str, float]:
    """Mapa destreza → score de mastery para un objetivo concreto."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT skill, score FROM academy_objective_mastery "
            "WHERE user_id = ? AND level_id = ? AND objective_id = ?",
            (user_id, level_id, objective_id),
        ).fetchall()
    return {r["skill"]: r["score"] for r in rows}


def list_objective_mastery(
    user_id: str, level_id: str
) -> dict[str, dict[str, dict]]:
    """Mapa {objective_id: {skill: estado}} para todo un nivel.

    Cada `estado` contiene `score` y `attempts` (y el resto de columnas), que es
    lo que necesita la lógica pura para decidir el dominio por objetivo."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT objective_id, skill, score, recent_score, confidence, streak, "
            "attempts, last_seen_at FROM academy_objective_mastery "
            "WHERE user_id = ? AND level_id = ?",
            (user_id, level_id),
        ).fetchall()
    agg: dict[str, dict[str, dict]] = {}
    for r in rows:
        agg.setdefault(r["objective_id"], {})[r["skill"]] = dict(r)
    return agg


def record_assessment_result(
    user_id: str, assessment_id: str, level_id: str, results: dict, passed: bool
) -> dict | None:
    if get_user(user_id) is None:
        return None
    now = _now()
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO academy_assessment_results "
            "(user_id, assessment_id, level_id, results_json, passed, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                user_id,
                assessment_id,
                level_id,
                json.dumps(results, ensure_ascii=False),
                1 if passed else 0,
                now,
            ),
        )
    return {
        "id": cur.lastrowid,
        "user_id": user_id,
        "assessment_id": assessment_id,
        "level_id": level_id,
        "results": results,
        "passed": passed,
        "created_at": now,
    }


def list_assessment_results(user_id: str) -> list[dict]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, user_id, assessment_id, level_id, results_json, "
            "passed, created_at "
            "FROM academy_assessment_results WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["results"] = json.loads(d.pop("results_json"))
        d["passed"] = bool(d["passed"])
        result.append(d)
    return result


def record_level_completion(
    user_id: str, level_id: str, level: str, overall: float
) -> dict | None:
    if get_user(user_id) is None:
        return None
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO academy_level_completions "
            "(user_id, level_id, level, overall, awarded_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, level_id) DO UPDATE SET "
            "overall = excluded.overall, awarded_at = excluded.awarded_at",
            (user_id, level_id, level, overall, now),
        )
    return {
        "user_id": user_id,
        "level_id": level_id,
        "level": level,
        "overall": overall,
        "awarded_at": now,
    }


def list_level_completions(user_id: str) -> list[dict]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, user_id, level_id, level, overall, awarded_at "
            "FROM academy_level_completions WHERE user_id = ? ORDER BY awarded_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def record_attempt(
    user_id: str,
    level_id: str,
    objective_id: str,
    skill: str,
    result: str,
    event_type: str = "attempt",
) -> bool:
    """Registra un evento de actividad ('correct' | 'incorrect' | 'completed')."""
    if get_user(user_id) is None:
        return False
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO academy_activity_attempts "
            "(user_id, level_id, objective_id, skill, result, event_type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, level_id, objective_id, skill, result, event_type, now),
        )
    return True


def record_lesson_completed(
    user_id: str, level_id: str, objective_id: str
) -> bool:
    """Registra la finalización de una lección (no declara acierto/fallo)."""
    return record_attempt(
        user_id, level_id, objective_id, "", "completed", "lesson_completed"
    )


def list_attempts(user_id: str, level_id: str) -> dict[str, dict[str, int]]:
    """Agregado por objetivo: {objective_id: {correct: n, incorrect: n}}.

    Solo cuenta eventos 'attempt' (los 'lesson_completed' no contaminan)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT objective_id, result, COUNT(*) AS n "
            "FROM academy_activity_attempts "
            "WHERE user_id = ? AND level_id = ? AND event_type = 'attempt' "
            "GROUP BY objective_id, result",
            (user_id, level_id),
        ).fetchall()
    agg: dict[str, dict[str, int]] = {}
    for r in rows:
        entry = agg.setdefault(r["objective_id"], {"correct": 0, "incorrect": 0})
        key = "correct" if r["result"] == "correct" else "incorrect"
        entry[key] = r["n"]
    return agg


def list_skill_attempts(user_id: str, level_id: str) -> dict[str, dict[str, int]]:
    """Agregado por destreza: {skill: {correct: n, incorrect: n}} (solo 'attempt')."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT skill, result, COUNT(*) AS n "
            "FROM academy_activity_attempts "
            "WHERE user_id = ? AND level_id = ? AND event_type = 'attempt' "
            "GROUP BY skill, result",
            (user_id, level_id),
        ).fetchall()
    agg: dict[str, dict[str, int]] = {}
    for r in rows:
        entry = agg.setdefault(r["skill"], {"correct": 0, "incorrect": 0})
        key = "correct" if r["result"] == "correct" else "incorrect"
        entry[key] = r["n"]
    return agg


def record_evidence(
    user_id: str,
    level_id: str,
    objective_id: str,
    skill: str,
    item_id: str,
    item_type: str = "mcq",
    difficulty: int = 1,
    source: str = "objective_assessment",
    result: float = 0.0,
    curriculum_version: str = "",
    assessment_version: str = "",
) -> bool:
    """Registra una evidencia de respuesta por ítem (reproducible y versionada)."""
    if get_user(user_id) is None:
        return False
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO academy_evidence "
            "(user_id, level_id, objective_id, skill, item_id, item_type, "
            "difficulty, source, result, curriculum_version, assessment_version, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id, level_id, objective_id, skill, item_id, item_type,
                difficulty, source, result, curriculum_version, assessment_version, now,
            ),
        )
    return True


def list_evidence(user_id: str, level_id: str | None = None) -> list[dict]:
    with closing(_conn()) as conn:
        if level_id is not None:
            rows = conn.execute(
                "SELECT id, user_id, level_id, objective_id, skill, item_id, "
                "item_type, difficulty, source, result, curriculum_version, "
                "assessment_version, created_at FROM academy_evidence "
                "WHERE user_id = ? AND level_id = ? ORDER BY id ASC",
                (user_id, level_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, user_id, level_id, objective_id, skill, item_id, "
                "item_type, difficulty, source, result, curriculum_version, "
                "assessment_version, created_at FROM academy_evidence "
                "WHERE user_id = ? ORDER BY id ASC",
                (user_id,),
            ).fetchall()
    return [dict(r) for r in rows]


def create_placement_session(
    user_id: str,
    placement_version: str,
    items: list[dict],
) -> dict | None:
    """Crea una sesión de placement trazable. None si el usuario no existe."""
    if get_user(user_id) is None:
        return None
    now = _now()
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO placement_sessions "
            "(user_id, started_at, placement_version, items_json) "
            "VALUES (?, ?, ?, ?)",
            (user_id, now, placement_version, json.dumps(items, ensure_ascii=False)),
        )
    return get_placement_session(cur.lastrowid)


def update_placement_session(
    session_id: int,
    *,
    answers: dict[str, int] | None = None,
    theta_trace: list[dict] | None = None,
    final_result: dict | None = None,
) -> dict | None:
    """Actualiza la traza de una sesión (respuestas, θ, resultado final)."""
    with closing(_conn()) as conn, conn:
        if answers is not None:
            conn.execute(
                "UPDATE placement_sessions SET answers_json = ? WHERE id = ?",
                (json.dumps(answers, ensure_ascii=False), session_id),
            )
        if theta_trace is not None:
            conn.execute(
                "UPDATE placement_sessions SET theta_trace_json = ? WHERE id = ?",
                (json.dumps(theta_trace, ensure_ascii=False), session_id),
            )
        if final_result is not None:
            conn.execute(
                "UPDATE placement_sessions "
                "SET final_result_json = ?, completed_at = ? WHERE id = ?",
                (json.dumps(final_result, ensure_ascii=False), _now(), session_id),
            )
    return get_placement_session(session_id)


def get_placement_session(session_id: int) -> dict | None:
    """Lee una sesión de placement con sus columnas JSON ya parseadas."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id, user_id, started_at, completed_at, placement_version, "
            "items_json, answers_json, theta_trace_json, final_result_json "
            "FROM placement_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["items"] = json.loads(d.pop("items_json"))
    d["answers"] = json.loads(d.pop("answers_json"))
    d["theta_trace"] = json.loads(d.pop("theta_trace_json"))
    d["final_result"] = (
        json.loads(d.pop("final_result_json")) if d.get("final_result_json") else None
    )
    return d


def list_placement_sessions(user_id: str) -> list[dict]:
    """Sesiones de placement de un usuario, más reciente primero (parseadas)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id FROM placement_sessions WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
    sessions = [get_placement_session(r["id"]) for r in rows]
    return [s for s in sessions if s is not None]


# --- Calibración observacional de ítems de placement (V1.7) ---------------


def record_placement_response(item_id: str, correct: bool) -> dict | None:
    """Registra una respuesta observada a un ítem de placement (calibración).

    Incrementa los contadores poblacionales `responses`/`correct` y recalcula
    `correct_rate` (= correct/responses) y `sample_size` (= responses). Las
    columnas de estimación IRT (`estimated_difficulty`, `standard_error`,
    `discrimination`) permanecen NULL hasta que un proceso de calibración las
    rellene con `set_placement_calibration_estimates`. Es un contador global (no
    por usuario): la dificultad de un ítem no depende de quién responde.
    """
    with closing(_conn()) as conn, conn:
        row = conn.execute(
            "SELECT responses, correct FROM placement_item_calibration "
            "WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        responses = (row["responses"] if row else 0) + 1
        correct_count = (row["correct"] if row else 0) + (1 if correct else 0)
        correct_rate = correct_count / responses
        conn.execute(
            "INSERT INTO placement_item_calibration "
            "(item_id, responses, correct, correct_rate, sample_size) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(item_id) DO UPDATE SET "
            "responses = excluded.responses, correct = excluded.correct, "
            "correct_rate = excluded.correct_rate, sample_size = excluded.sample_size",
            (item_id, responses, correct_count, correct_rate, responses),
        )
    return get_placement_calibration(item_id)


def get_placement_calibration(item_id: str) -> dict | None:
    """Lee la fila de calibración de un ítem, o None si aún no tiene respuestas."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT item_id, responses, correct, correct_rate, sample_size, "
            "estimated_difficulty, standard_error, discrimination "
            "FROM placement_item_calibration WHERE item_id = ?",
            (item_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def list_placement_calibration() -> list[dict]:
    """Calibración de todos los ítems de placement (solo los que tienen respuestas)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT item_id, responses, correct, correct_rate, sample_size, "
            "estimated_difficulty, standard_error, discrimination "
            "FROM placement_item_calibration ORDER BY item_id ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def set_placement_calibration_estimates(
    item_id: str,
    estimated_difficulty: float,
    standard_error: float,
    discrimination: float,
) -> bool:
    """Escribe las estimaciones IRT de un ítem (calibración posterior). False si
    el ítem no tiene fila de calibración todavía."""
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "UPDATE placement_item_calibration SET "
            "estimated_difficulty = ?, standard_error = ?, discrimination = ? "
            "WHERE item_id = ?",
            (estimated_difficulty, standard_error, discrimination, item_id),
        )
    return cur.rowcount > 0


# --- Objetivo personal de aprendizaje -------------------------------------


def get_goal(user_id: str) -> dict | None:
    """Objetivo personal del usuario (tipo, minutos/día, días/semana y meta CEFR),
    o None si aún no lo ha configurado."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT goal_type, minutes_per_day, days_per_week, target_level "
            "FROM learning_goal WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def upsert_goal(
    user_id: str,
    goal_type: str,
    minutes_per_day: int,
    days_per_week: int,
    target_level: str,
) -> bool:
    """Crea o actualiza el objetivo personal del usuario. False si no existe."""
    if get_user(user_id) is None:
        return False
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO learning_goal "
            "(user_id, goal_type, minutes_per_day, days_per_week, target_level, "
            "updated_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "goal_type = excluded.goal_type, "
            "minutes_per_day = excluded.minutes_per_day, "
            "days_per_week = excluded.days_per_week, "
            "target_level = excluded.target_level, "
            "updated_at = excluded.updated_at",
            (user_id, goal_type, minutes_per_day, days_per_week, target_level, now),
        )
    return True


# --- Sesión diaria (Session Engine): pasos completados --------------------


def mark_session_step(user_id: str, step_key: str, completed_on: str) -> bool:
    """Marca un paso de la sesión como completado hoy. False si no existe el usuario.

    La clave es (user_id, step_key): remarcar el mismo paso en un día posterior
    actualiza `completed_on`, así el filtro "hoy" se autolimpia sin acumular filas."""
    if get_user(user_id) is None:
        return False
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO session_completions "
            "(user_id, step_key, completed_on, completed_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, step_key) DO UPDATE SET "
            "completed_on = excluded.completed_on, "
            "completed_at = excluded.completed_at",
            (user_id, step_key, completed_on, now),
        )
    return True


def list_session_steps(user_id: str, completed_on: str) -> set[str]:
    """Claves de los pasos de sesión completados en una fecha concreta."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT step_key FROM session_completions "
            "WHERE user_id = ? AND completed_on = ?",
            (user_id, completed_on),
        ).fetchall()
    return {r["step_key"] for r in rows}
