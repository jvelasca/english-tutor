"""Repositorio del perfil de aprendizaje (SQLite)."""
from __future__ import annotations

import json
from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def get_profile(user_id: str) -> dict | None:
    """Devuelve el perfil almacenado o None si no existe.

    V3.52: además de `cefr_level` (compatibilidad) expone `estimated_level` y
    `demonstrated_level` (niveles SEPARADOS de la caché del Student Model).
    """
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT user_id, cefr_level, estimated_level, demonstrated_level, "
            "updated_at FROM learning_profile WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def set_level_state(
    user_id: str,
    *,
    estimated_level: str,
    demonstrated_level: str,
    cefr_level: str | None = None,
) -> dict | None:
    """Persiste (upsert) el estado de nivel del usuario (V3.52).

    `estimated_level` es la banda de práctica continua (lo que históricamente
    guardaba `cefr_level`) y `demonstrated_level` el nivel certificado ("" hasta
    la primera certificación). `cefr_level` se conserva por compatibilidad: si no
    se aporta, toma el valor del estimado. Devuelve None si el usuario no existe.
    """
    if get_user(user_id) is None:
        return None
    legacy = estimated_level if cefr_level is None else cefr_level
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO learning_profile "
            "(user_id, cefr_level, estimated_level, demonstrated_level, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "cefr_level = excluded.cefr_level, "
            "estimated_level = excluded.estimated_level, "
            "demonstrated_level = excluded.demonstrated_level, "
            "updated_at = excluded.updated_at",
            (user_id, legacy, estimated_level, demonstrated_level, now),
        )
    return {
        "user_id": user_id,
        "cefr_level": legacy,
        "estimated_level": estimated_level,
        "demonstrated_level": demonstrated_level,
        "updated_at": now,
    }


def set_cefr(user_id: str, level: str) -> dict | None:
    """Persiste (upsert) el nivel CEFR ESTIMADO del usuario (compatibilidad).

    Wrapper histórico de V3.51: antes escribía solo `cefr_level`, que en realidad
    cachaba el nivel ESTIMADO. En V3.52 delega en `set_level_state` para que la
    caché quede coherente (`cefr_level` y `estimated_level` con el mismo valor)
    sin pisar un `demonstrated_level` ya certificado. Devuelve None si el usuario
    no existe.
    """
    existing = get_profile(user_id) or {}
    demonstrated = str(existing.get("demonstrated_level") or "")
    return set_level_state(
        user_id,
        estimated_level=level,
        demonstrated_level=demonstrated,
        cefr_level=level,
    )


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
