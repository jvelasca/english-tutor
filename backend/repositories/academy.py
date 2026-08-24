"""Repositorio del estado de la Academy (SQLite): matrícula, mastery, evaluaciones
y certificados. El contenido no vive aquí (JSON en services.curriculum)."""

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


def record_skill_evidence(
    user_id: str, level_id: str, skill: str, score: float
) -> bool:
    """Guarda la mejor puntuación (0..1) de una destreza en un nivel (upsert)."""
    if get_user(user_id) is None:
        return False
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO academy_skill_mastery "
            "(user_id, level_id, skill, score, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, level_id, skill) DO UPDATE SET "
            "score = MAX(score, excluded.score), updated_at = excluded.updated_at",
            (user_id, level_id, skill, score, now),
        )
    return True


def get_skill_mastery(user_id: str, level_id: str) -> dict[str, float]:
    """Mapa destreza → mejor puntuación en un nivel."""
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


def award_certificate(
    user_id: str, level_id: str, level: str, overall: float
) -> dict | None:
    if get_user(user_id) is None:
        return None
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO academy_certificates "
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


def list_certificates(user_id: str) -> list[dict]:
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, user_id, level_id, level, overall, awarded_at "
            "FROM academy_certificates WHERE user_id = ? ORDER BY awarded_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def record_attempt(
    user_id: str, level_id: str, objective_id: str, skill: str, result: str
) -> bool:
    """Registra un intento de actividad ('correct' | 'incorrect')."""
    if get_user(user_id) is None:
        return False
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO academy_activity_attempts "
            "(user_id, level_id, objective_id, skill, result, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, level_id, objective_id, skill, result, now),
        )
    return True


def list_attempts(user_id: str, level_id: str) -> dict[str, dict[str, int]]:
    """Agregado por objetivo: {objective_id: {correct: n, incorrect: n}}."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT objective_id, result, COUNT(*) AS n "
            "FROM academy_activity_attempts "
            "WHERE user_id = ? AND level_id = ? "
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
    """Agregado por destreza: {skill: {correct: n, incorrect: n}}."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT skill, result, COUNT(*) AS n "
            "FROM academy_activity_attempts "
            "WHERE user_id = ? AND level_id = ? "
            "GROUP BY skill, result",
            (user_id, level_id),
        ).fetchall()
    agg: dict[str, dict[str, int]] = {}
    for r in rows:
        entry = agg.setdefault(r["skill"], {"correct": 0, "incorrect": 0})
        key = "correct" if r["result"] == "correct" else "incorrect"
        entry[key] = r["n"]
    return agg
