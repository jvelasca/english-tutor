"""Repositorio del perfil de aprendizaje (SQLite)."""
from __future__ import annotations

import json
from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def get_profile(user_id: str) -> dict | None:
    """Devuelve el perfil almacenado o None si no existe."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT user_id, cefr_level, updated_at FROM learning_profile "
            "WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def set_cefr(user_id: str, level: str) -> dict | None:
    """Persiste (upsert) el nivel CEFR del usuario. Devuelve None si el usuario
    no existe."""
    if get_user(user_id) is None:
        return None
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO learning_profile (user_id, cefr_level, updated_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "cefr_level = excluded.cefr_level, updated_at = excluded.updated_at",
            (user_id, level, now),
        )
    return {"user_id": user_id, "cefr_level": level, "updated_at": now}


def record_cefr_snapshot(
    user_id: str,
    *,
    level: str,
    numeric: float,
    confidence: float,
    instrument_version: str,
    curriculum_version: str,
    skills: list[dict],
) -> dict | None:
    """Persiste un snapshot inmutable de evaluación CEFR (histórico reproducible).

    Guarda el nivel, el nivel continuo, la confianza, las versiones del instrumento
    y del currículo, y el desglose por destreza (`skills`). Devuelve None si el
    usuario no existe."""
    if get_user(user_id) is None:
        return None
    now = _now()
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO cefr_assessment_snapshots "
            "(user_id, level, numeric, confidence, instrument_version, "
            "curriculum_version, skills_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                level,
                numeric,
                confidence,
                instrument_version,
                curriculum_version,
                json.dumps(skills, ensure_ascii=False),
                now,
            ),
        )
    return {
        "id": cur.lastrowid,
        "user_id": user_id,
        "level": level,
        "numeric": numeric,
        "confidence": confidence,
        "instrument_version": instrument_version,
        "curriculum_version": curriculum_version,
        "skills": skills,
        "created_at": now,
    }


def list_cefr_history(user_id: str) -> list[dict]:
    """Devuelve el histórico de snapshots CEFR del usuario (más antiguo primero)."""
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, user_id, level, numeric, confidence, instrument_version, "
            "curriculum_version, skills_json, created_at "
            "FROM cefr_assessment_snapshots WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["skills"] = json.loads(d.pop("skills_json"))
        result.append(d)
    return result


def last_cefr_snapshot(user_id: str) -> dict | None:
    """Último snapshot CEFR del usuario, o None si no hay ninguno."""
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT id, user_id, level, numeric, confidence, instrument_version, "
            "curriculum_version, skills_json, created_at "
            "FROM cefr_assessment_snapshots WHERE user_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["skills"] = json.loads(d.pop("skills_json"))
    return d
