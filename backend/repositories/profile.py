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
    V3.53: expone `observed_level` y `observed_capacity` (capacidad observada
    serializada; la parsea el drill con `services.difficulty.parse_vector`).
    V3.54: expone `observed_skill_capacity` (capacidad por skill × dimensión en
    JSON; la normaliza `services.learner_skill.normalize_skill_capacity`).
    V3.62: expone `skill_state` (estado unificado {modalidad: {competencia:
    entry}} en JSON; lo normaliza `services.skill_state.normalize_skill_state`).
    V3.63: expone `skill_state_source` (el sello de frescura de esa caché; `""`
    en las cachés legacy, que por eso nunca se reportan frescas).
    """
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT user_id, cefr_level, estimated_level, demonstrated_level, "
            "observed_level, observed_capacity, observed_skill_capacity, "
            "skill_state, skill_state_source, updated_at "
            "FROM learning_profile WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def set_level_state(
    user_id: str,
    *,
    estimated_level: str,
    demonstrated_level: str,
    cefr_level: str | None = None,
    observed_level: str = "",
    observed_capacity: str = "",
    observed_skill_capacity: str = "",
) -> dict | None:
    """Persiste (upsert) el estado de nivel del usuario (V3.52 → V3.53).

    `estimated_level` es la banda de práctica continua (lo que históricamente
    guardaba `cefr_level`) y `demonstrated_level` el nivel certificado ("" hasta
    la primera certificación). `cefr_level` se conserva por compatibilidad: si no
    se aporta, toma el valor del estimado. V3.53 añade `observed_level` (nivel
    equivalente de la capacidad observada) y `observed_capacity` (vector
    serializado por dimensión; `""` = sin muestra). V3.54 añade
    `observed_skill_capacity` (por skill × dimensión, JSON). Devuelve None si el
    usuario no existe.
    """
    if get_user(user_id) is None:
        return None
    legacy = estimated_level if cefr_level is None else cefr_level
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO learning_profile "
            "(user_id, cefr_level, estimated_level, demonstrated_level, "
            "observed_level, observed_capacity, observed_skill_capacity, "
            "updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "cefr_level = excluded.cefr_level, "
            "estimated_level = excluded.estimated_level, "
            "demonstrated_level = excluded.demonstrated_level, "
            "observed_level = excluded.observed_level, "
            "observed_capacity = excluded.observed_capacity, "
            "observed_skill_capacity = excluded.observed_skill_capacity, "
            "updated_at = excluded.updated_at",
            (
                user_id,
                legacy,
                estimated_level,
                demonstrated_level,
                observed_level,
                observed_capacity,
                observed_skill_capacity,
                now,
            ),
        )
    return {
        "user_id": user_id,
        "cefr_level": legacy,
        "estimated_level": estimated_level,
        "demonstrated_level": demonstrated_level,
        "observed_level": observed_level,
        "observed_capacity": observed_capacity,
        "observed_skill_capacity": observed_skill_capacity,
        "updated_at": now,
    }


def set_skill_state(
    user_id: str, skill_state: str, source: str = ""
) -> dict | None:
    """Persiste SOLO las columnas aditivas `skill_state`/`skill_state_source`.

    Escritor DEDICADO: el estado unificado por modalidad × competencia se calcula
    en `domain.profile` en cada refresco del perfil y se cachea aquí como JSON
    determinista (`sort_keys=True`). No toca ninguna otra columna (ni
    `observed_skill_capacity`, que sigue siendo la fuente de verdad del drill) y
    no altera la firma del escritor caliente `set_level_state`. Devuelve None si
    el usuario no existe.

    V3.63 (P2-18): `source` es el SELLO de frescura — la huella de las cuatro
    fuentes (`repositories.evidence.evidence_fingerprint`) en el momento de
    escribir la caché. Es OPCIONAL con default `""` para no romper llamadores: una
    caché sin sello (o con sello `""`) NUNCA se reporta como fresca
    (`skill_state_is_fresh`), que es la degradación honesta.
    """
    if get_user(user_id) is None:
        return None
    now = _now()
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO learning_profile "
            "(user_id, updated_at, skill_state, skill_state_source) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "skill_state = excluded.skill_state, "
            "skill_state_source = excluded.skill_state_source, "
            "updated_at = excluded.updated_at",
            (user_id, now, skill_state, str(source or "")),
        )
    return {
        "user_id": user_id,
        "skill_state": skill_state,
        "skill_state_source": str(source or ""),
        "updated_at": now,
    }


def skill_state_is_fresh(user_id: str) -> bool:
    """¿La caché de `skill_state` describe TODAVÍA las cuatro fuentes? (V3.63).

    Compara el sello guardado con `evidence_fingerprint(user_id)`. Devuelve
    `False` cuando no hay caché, cuando la caché está VACÍA, cuando no tiene sello
    (legacy de V3.62) o cuando el sello ya no coincide. Invariante: una caché vieja
    NUNCA se reporta como fresca. Esta función solo RESPONDE; recomputar la caché
    cuando está vieja es responsabilidad del llamador (V3.64).
    """
    from repositories.evidence import evidence_fingerprint

    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT skill_state, skill_state_source FROM learning_profile "
            "WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return False
    cached = str(row["skill_state"] or "").strip()
    source = str(row["skill_state_source"] or "").strip()
    if not cached or not source:
        return False
    return source == evidence_fingerprint(user_id)


def set_cefr(user_id: str, level: str) -> dict | None:
    """Persiste (upsert) el nivel CEFR ESTIMADO del usuario (compatibilidad).

    Wrapper histórico de V3.51: antes escribía solo `cefr_level`, que en realidad
    cachaba el nivel ESTIMADO. En V3.52 delega en `set_level_state` para que la
    caché quede coherente (`cefr_level` y `estimated_level` con el mismo valor)
    sin pisar un `demonstrated_level` ya certificado. V3.53 conserva también el
    estado OBSERVADO cacheado. Devuelve None si el usuario no existe.
    """
    existing = get_profile(user_id) or {}
    demonstrated = str(existing.get("demonstrated_level") or "")
    return set_level_state(
        user_id,
        estimated_level=level,
        demonstrated_level=demonstrated,
        cefr_level=level,
        observed_level=str(existing.get("observed_level") or ""),
        observed_capacity=str(existing.get("observed_capacity") or ""),
        observed_skill_capacity=str(
            existing.get("observed_skill_capacity") or ""
        ),
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
