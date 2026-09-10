"""Repositorio del ledger de evidencia longitudinal (V3.35).

Ledger append-only de evidencia por ítem (`learning_evidence`): complementa
`vocabulary_events` (historia léxica por forma) con el EVENTO y su INTERVALO.
Cada recuperación o producción es una fila con:

- `occurred_at`  — cuándo ocurrió (UTC ISO);
- `target_type` / `target_id` / `surface_form` / `lexical_unit` — a QUÉ ítem se
  refiere (léxico, destreza, objetivo);
- `task` / `activity` — QUÉ se hizo y en qué actividad;
- `success` — el resultado del intento (los fallos también son evidencia);
- `interval_since_last_evidence` — días desde la evidencia ANTERIOR del mismo
  ítem (None en la primera): la cadena `evento_n → intervalo → evento_{n+1}`.
  Es un intervalo de EVIDENCIA (`learning_evidence → learning_evidence`), no el
  hueco desde el ancla de retención FSRS: son conceptos distintos (V3.35.1,
  P1-01; el intervalo de retención vive solo en la decisión, no se persiste);
- `event_role` — evidence / telemetry / informative (ver `services.evidence`).

Sin backfill: el ledger empieza en V3.35 y los contadores agregados de
`vocabulary` conservan el histórico. Señal (D5/E3), nunca puerta de mastery.
"""

from __future__ import annotations

from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user


def last_evidence_at(
    user_id: str, target_type: str, target_id: str
) -> str:
    """Marca ISO de la evidencia más reciente de un ítem ("" si no hay).

    Es el ancla de la cadena longitudinal: el intervalo de un evento nuevo se
    mide desde AQUÍ, no desde la primera exposición del ítem (V3.35).
    """
    with closing(_conn()) as conn:
        row = conn.execute(
            "SELECT occurred_at FROM learning_evidence "
            "WHERE user_id = ? AND target_type = ? AND target_id = ? "
            "ORDER BY occurred_at DESC, id DESC LIMIT 1",
            (user_id, target_type, target_id),
        ).fetchone()
    return row["occurred_at"] if row else ""


def record_evidence(
    user_id: str,
    *,
    target_type: str,
    target_id: str,
    skill: str = "",
    surface_form: str = "",
    lexical_unit: str = "",
    task: str = "",
    activity: str = "",
    activity_id: str = "",
    context_id: str = "",
    success: bool = False,
    support_level: str = "",
    difficulty: float = 0.0,
    response_time_ms: int | None = None,
    error_type: str = "",
    event_role: str = "evidence",
    interval_since_last_evidence: float | None = None,
    occurred_at: str = "",
) -> dict | None:
    """Registra un evento de evidencia longitudinal (append-only).

    Si `interval_since_last_evidence` no se pasa, se DERIVA de la evidencia
    anterior del mismo `(target_type, target_id)` con `services.evidence`
    (None en la primera observación). Devuelve la fila creada o None si el
    usuario no existe. Nunca lanza por datos parciales: el ledger es señal.

    V3.36 (Learning Evidence 2.0) añade las dimensiones del evento:
    `activity_id`/`context_id` (qué actividad concreta y en qué contexto),
    `support_level` (eje copied→spontaneous; `services.evidence`), `difficulty`
    (0 = no declarada), `response_time_ms` (None = no medida) y `error_type`
    (taxonomía del intento). Todas son OBSERVACIONALES: no cambian el scoring.
    """
    if get_user(user_id) is None:
        return None
    # Import local: la capa pura vive en `services` y no debe acoplarse en
    # tiempo de import (misma convención que `repositories.vocabulary`).
    from services.evidence import interval_days

    now = occurred_at or _now()
    interval = interval_since_last_evidence
    if interval is None:
        previous = last_evidence_at(user_id, target_type, target_id)
        interval = interval_days(previous, now) if previous else None
    with closing(_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO learning_evidence "
            "(user_id, occurred_at, skill, target_type, target_id, "
            "surface_form, lexical_unit, task, activity, activity_id, "
            "context_id, success, support_level, difficulty, "
            "response_time_ms, error_type, "
            "interval_since_last_evidence, event_role) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                now,
                skill,
                target_type,
                target_id,
                surface_form or target_id,
                lexical_unit or surface_form or target_id,
                task,
                activity,
                activity_id,
                context_id,
                1 if success else 0,
                support_level,
                float(difficulty or 0.0),
                response_time_ms,
                error_type,
                interval,
                event_role,
            ),
        )
    return {
        "id": cur.lastrowid,
        "user_id": user_id,
        "occurred_at": now,
        "skill": skill,
        "target_type": target_type,
        "target_id": target_id,
        "surface_form": surface_form or target_id,
        "lexical_unit": lexical_unit or surface_form or target_id,
        "task": task,
        "activity": activity,
        "activity_id": activity_id,
        "context_id": context_id,
        "success": bool(success),
        "support_level": support_level,
        "difficulty": float(difficulty or 0.0),
        "response_time_ms": response_time_ms,
        "error_type": error_type,
        "interval_since_last_evidence": interval,
        "event_role": event_role,
    }


def record_evidence_bulk(
    user_id: str, entries: list[dict], *, occurred_at: str = ""
) -> int:
    """Registra varios eventos de evidencia en UNA transacción (V3.35).

    Pensado para el volcado de producción (varias palabras por mensaje): resuelve
    la evidencia anterior de cada ítem en una sola pasada y calcula el intervalo
    de cada evento. Devuelve el nº de filas insertadas (0 si el usuario no
    existe o no hay entradas). Cada entrada admite `target_type`, `target_id`,
    `skill`, `surface_form`, `lexical_unit`, `task`, `activity`, `success`,
    `event_role` y `occurred_at` (por entrada; si falta, el `occurred_at` del
    lote o `_now()`).

    V3.35.1 (P2-02): el contrato del ledger se blinda contra lotes degenerados:

    - DEDUPE: dos entradas idénticas del mismo evento
      (`target_type`, `target_id`, `task`, `activity`, `occurred_at`) insertan
      UNA sola fila (el ledger es un histórico de eventos, no un contador);
    - CADENA SECUENCIAL: `previous` se actualiza en memoria tras cada fila, de
      modo que dos eventos DISTINTOS del mismo target dentro del lote encadenan
      su intervalo (el segundo mide desde el primero, no desde la BD); el lote
      se procesa en orden cronológico para que la cadena sea correcta.
    """
    if not entries or get_user(user_id) is None:
        return 0
    # Import local (misma convención que el resto del repositorio).
    from services.evidence import interval_days

    now = occurred_at or _now()
    # Normaliza + deduplica conservando el primer evento de cada clave; ordena
    # cronológicamente para encadenar los intervalos del lote (V3.35.1, P2-02).
    normalized: list[dict] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for entry in entries:
        target_type = entry.get("target_type", "")
        target_id = entry.get("target_id", "")
        at = entry.get("occurred_at") or now
        key = (
            target_type,
            target_id,
            entry.get("task", ""),
            entry.get("activity", ""),
            at,
        )
        if key in seen:
            continue
        seen.add(key)
        normalized.append({**entry, "_occurred_at": at})
    normalized.sort(key=lambda e: e["_occurred_at"])
    with closing(_conn()) as conn, conn:
        previous: dict[tuple[str, str], str] = {}
        for target_type, target_id in {
            (e.get("target_type", ""), e.get("target_id", ""))
            for e in normalized
        }:
            row = conn.execute(
                "SELECT occurred_at FROM learning_evidence "
                "WHERE user_id = ? AND target_type = ? AND target_id = ? "
                "ORDER BY occurred_at DESC, id DESC LIMIT 1",
                (user_id, target_type, target_id),
            ).fetchone()
            if row:
                previous[(target_type, target_id)] = row["occurred_at"]
        rows = []
        for entry in normalized:
            target_type = entry.get("target_type", "")
            target_id = entry.get("target_id", "")
            surface = entry.get("surface_form") or target_id
            at = entry["_occurred_at"]
            prev = previous.get((target_type, target_id), "")
            interval = interval_days(prev, at) if prev else None
            # Encadena en memoria: el siguiente evento del mismo target mide
            # desde este, no desde la BD (V3.35.1, P2-02).
            previous[(target_type, target_id)] = at
            rows.append(
                (
                    user_id,
                    at,
                    entry.get("skill", ""),
                    target_type,
                    target_id,
                    surface,
                    entry.get("lexical_unit") or surface,
                    entry.get("task", ""),
                    entry.get("activity", ""),
                    entry.get("activity_id", ""),
                    entry.get("context_id", ""),
                    1 if entry.get("success") else 0,
                    entry.get("support_level", ""),
                    float(entry.get("difficulty") or 0.0),
                    entry.get("response_time_ms"),
                    entry.get("error_type", ""),
                    interval,
                    entry.get("event_role", "evidence"),
                )
            )
        conn.executemany(
            "INSERT INTO learning_evidence "
            "(user_id, occurred_at, skill, target_type, target_id, "
            "surface_form, lexical_unit, task, activity, activity_id, "
            "context_id, success, support_level, difficulty, "
            "response_time_ms, error_type, "
            "interval_since_last_evidence, event_role) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def list_evidence(
    user_id: str,
    target_id: str | None = None,
    *,
    target_type: str | None = None,
    event_role: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """Evidencia longitudinal del usuario (más reciente primero).

    Filtros opcionales por `target_id` (forma/ítem) y `target_type` (léxico,
    destreza, objetivo). Orden determinista por `(occurred_at, id)` descendente.
    """
    clauses = ["user_id = ?"]
    params: list[object] = [user_id]
    if target_id:
        clauses.append("target_id = ?")
        params.append(target_id)
    if target_type:
        clauses.append("target_type = ?")
        params.append(target_type)
    if event_role:
        clauses.append("event_role = ?")
        params.append(event_role)
    params.extend([limit, offset])
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT id, user_id, occurred_at, skill, target_type, target_id, "
            "surface_form, lexical_unit, task, activity, activity_id, "
            "context_id, success, support_level, difficulty, response_time_ms, "
            "error_type, interval_since_last_evidence, event_role "
            "FROM learning_evidence "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY occurred_at DESC, id DESC "
            "LIMIT ? OFFSET ?",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def summarize_by_target(
    user_id: str, *, target_type: str = "lexicon"
) -> dict[str, dict]:
    """Resumen longitudinal por `target_id` desde el ledger (V3.35).

    Agrega en SQL los contadores (`attempts`, `successes`, días distintos con
    éxito) y recoge los intervalos de los eventos con éxito EN ORDEN
    CRONOLÓGICO (`occurred_at`, `id`), sin límite de filas ni N+1 consultas.
    Mismo contrato que `services.evidence.summarize_evidence` (V3.35.1, P1-02:
    la secuencia real no se reordena por valor del intervalo).

    V3.36 (Learning Evidence 2.0) añade al contrato `success_rate`,
    `independent_successes`, `support_levels`, `error_types` y
    `mean_response_time_ms` con las mismas reglas que la versión pura (la
    paridad la fija un test): el agregado no puede introducir un segundo
    dialecto del resumen.

    V3.37 (cues graduados) añade `independent_success_days` (días naturales
    distintos con éxito sin apoyo: lo que `is_automatic` exige que esté
    espaciado) y `recall_rungs` (histograma de ÉXITOS de recall por peldaño,
    leído del `activity_id` `drill:recall:<peldaño>`). Misma paridad pura↔SQL.

    V3.37.1 (política de consolidación y regresión) añade
    `recall_rung_days` (días distintos con éxito por peldaño: lo que exige
    `next_recall_rung` para dar el peldaño por superado) y
    `recall_rung_failures` (fallos por peldaño: lo que lee la regresión).
    Los tres histogramas comparten el mismo vocabulario de peldaño.

    V3.38 (P1-03 de la auditoría de V3.37.0) añade la segmentación por
    MODALIDAD: `skill_successes`/`skill_success_days` y
    `skill_independent_successes`/`skill_independent_days`, agrupados por
    `LOWER(skill)` y restringidos a los valores canónicos de `LEXICAL_SKILLS`
    (solo ÉXITOS, como la versión pura). Es la base de `automatic_skills`.

    Los ítems sin eventos no aparecen: el llamador usa `empty_summary()`.
    """
    # Import local (misma convención que el resto del repositorio): la capa pura
    # es la única fuente de verdad de los niveles de apoyo independientes y del
    # vocabulario del peldaño.
    from services.evidence import (
        INDEPENDENT_SUPPORT_LEVELS,
        LEXICAL_SKILLS,
        RECALL_RUNG_EVIDENCE,
        recall_rung_from_activity,
    )

    independent = sorted(INDEPENDENT_SUPPORT_LEVELS)
    placeholders = ", ".join("?" for _ in independent)
    skills = tuple(LEXICAL_SKILLS)
    skill_placeholders = ", ".join("?" for _ in skills)
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT target_id, COUNT(*) AS attempts, "
            "COALESCE(SUM(success), 0) AS successes, "
            "COUNT(DISTINCT CASE WHEN success = 1 "
            "THEN substr(occurred_at, 1, 10) END) AS distinct_success_days, "
            "COALESCE(SUM(CASE WHEN success = 1 "
            f"AND support_level IN ({placeholders}) THEN 1 ELSE 0 END), 0) "
            "AS independent_successes, "
            "COUNT(DISTINCT CASE WHEN success = 1 "
            f"AND support_level IN ({placeholders}) "
            "THEN NULLIF(substr(occurred_at, 1, 10), '') END) "
            "AS independent_success_days, "
            "AVG(response_time_ms) AS mean_latency "
            "FROM learning_evidence "
            "WHERE user_id = ? AND target_type = ? "
            "GROUP BY target_id",
            (*independent, *independent, user_id, target_type),
        ).fetchall()
        interval_rows = conn.execute(
            "SELECT target_id, interval_since_last_evidence AS interval "
            "FROM learning_evidence "
            "WHERE user_id = ? AND target_type = ? AND success = 1 "
            "AND interval_since_last_evidence IS NOT NULL "
            "ORDER BY target_id, occurred_at ASC, id ASC",
            (user_id, target_type),
        ).fetchall()
        support_rows = conn.execute(
            "SELECT target_id, support_level, COUNT(*) AS total "
            "FROM learning_evidence "
            "WHERE user_id = ? AND target_type = ? AND support_level <> '' "
            "GROUP BY target_id, support_level",
            (user_id, target_type),
        ).fetchall()
        error_rows = conn.execute(
            "SELECT target_id, error_type, COUNT(*) AS total "
            "FROM learning_evidence "
            "WHERE user_id = ? AND target_type = ? AND error_type <> '' "
            "GROUP BY target_id, error_type",
            (user_id, target_type),
        ).fetchall()
        rung_rows = conn.execute(
            "SELECT target_id, activity_id, COUNT(*) AS total "
            "FROM learning_evidence "
            "WHERE user_id = ? AND target_type = ? AND success = 1 "
            "AND activity_id LIKE ? "
            "GROUP BY target_id, activity_id",
            (user_id, target_type, f"{RECALL_RUNG_EVIDENCE}%"),
        ).fetchall()
        # V3.37.1: días distintos con éxito por peldaño (lo que exige la
        # consolidación) y fallos por peldaño (lo que lee la regresión). El
        # `NULLIF` sobre el día vacío replica el 0 de la versión pura (paridad).
        rung_day_rows = conn.execute(
            "SELECT target_id, activity_id, "
            "COUNT(DISTINCT NULLIF(substr(occurred_at, 1, 10), '')) AS days "
            "FROM learning_evidence "
            "WHERE user_id = ? AND target_type = ? AND success = 1 "
            "AND activity_id LIKE ? "
            "GROUP BY target_id, activity_id",
            (user_id, target_type, f"{RECALL_RUNG_EVIDENCE}%"),
        ).fetchall()
        rung_failure_rows = conn.execute(
            "SELECT target_id, activity_id, COUNT(*) AS total "
            "FROM learning_evidence "
            "WHERE user_id = ? AND target_type = ? AND success = 0 "
            "AND activity_id LIKE ? "
            "GROUP BY target_id, activity_id",
            (user_id, target_type, f"{RECALL_RUNG_EVIDENCE}%"),
        ).fetchall()
        # V3.38 (P1-03): histogramas por MODALIDAD. Se agrupan SOLO los éxitos
        # (`success = 1`), igual que la versión pura, que crea la clave en el
        # éxito: una modalidad con únicamente fallos no aparece en ninguno de
        # los dos. El `NULLIF` del día vacío replica el 0 de la versión pura.
        skill_rows = conn.execute(
            "SELECT target_id, LOWER(skill) AS skill, COUNT(*) AS successes, "
            "COUNT(DISTINCT NULLIF(substr(occurred_at, 1, 10), '')) AS days, "
            "COALESCE(SUM(CASE WHEN support_level IN "
            f"({placeholders}) THEN 1 ELSE 0 END), 0) AS independent_successes, "
            "COUNT(DISTINCT CASE WHEN support_level IN "
            f"({placeholders}) THEN NULLIF(substr(occurred_at, 1, 10), '') "
            "END) AS independent_days "
            "FROM learning_evidence "
            "WHERE user_id = ? AND target_type = ? AND success = 1 "
            f"AND LOWER(skill) IN ({skill_placeholders}) "
            "GROUP BY target_id, LOWER(skill)",
            (*independent, *independent, user_id, target_type, *skills),
        ).fetchall()
    intervals: dict[str, list[float]] = {}
    for row in interval_rows:
        intervals.setdefault(row["target_id"], []).append(
            round(float(row["interval"]), 4)
        )
    support_levels: dict[str, dict[str, int]] = {}
    for row in support_rows:
        support_levels.setdefault(row["target_id"], {})[row["support_level"]] = int(
            row["total"]
        )
    error_types: dict[str, dict[str, int]] = {}
    for row in error_rows:
        error_types.setdefault(row["target_id"], {})[row["error_type"]] = int(
            row["total"]
        )
    recall_rungs: dict[str, dict[str, int]] = {}
    for row in rung_rows:
        rung = recall_rung_from_activity(row["activity_id"])
        if not rung:
            continue
        bucket = recall_rungs.setdefault(row["target_id"], {})
        bucket[rung] = bucket.get(rung, 0) + int(row["total"])
    recall_rung_days: dict[str, dict[str, int]] = {}
    for row in rung_day_rows:
        rung = recall_rung_from_activity(row["activity_id"])
        if not rung:
            continue
        recall_rung_days.setdefault(row["target_id"], {})[rung] = int(row["days"])
    recall_rung_failures: dict[str, dict[str, int]] = {}
    for row in rung_failure_rows:
        rung = recall_rung_from_activity(row["activity_id"])
        if not rung:
            continue
        bucket = recall_rung_failures.setdefault(row["target_id"], {})
        bucket[rung] = bucket.get(rung, 0) + int(row["total"])
    skill_successes: dict[str, dict[str, int]] = {}
    skill_success_days: dict[str, dict[str, int]] = {}
    skill_independent_successes: dict[str, dict[str, int]] = {}
    skill_independent_days: dict[str, dict[str, int]] = {}
    for row in skill_rows:
        target = row["target_id"]
        skill = row["skill"]
        skill_successes.setdefault(target, {})[skill] = int(row["successes"])
        skill_success_days.setdefault(target, {})[skill] = int(row["days"])
        skill_independent_successes.setdefault(target, {})[skill] = int(
            row["independent_successes"]
        )
        skill_independent_days.setdefault(target, {})[skill] = int(
            row["independent_days"]
        )
    return {
        row["target_id"]: {
            "attempts": int(row["attempts"]),
            "successes": int(row["successes"]),
            "success_rate": (
                round(int(row["successes"]) / int(row["attempts"]), 4)
                if int(row["attempts"])
                else 0.0
            ),
            "distinct_success_days": int(row["distinct_success_days"]),
            "intervals": intervals.get(row["target_id"], []),
            "independent_successes": int(row["independent_successes"]),
            "independent_success_days": int(row["independent_success_days"]),
            "support_levels": support_levels.get(row["target_id"], {}),
            "error_types": error_types.get(row["target_id"], {}),
            "recall_rungs": recall_rungs.get(row["target_id"], {}),
            "recall_rung_days": recall_rung_days.get(row["target_id"], {}),
            "recall_rung_failures": recall_rung_failures.get(row["target_id"], {}),
            "skill_successes": skill_successes.get(row["target_id"], {}),
            "skill_success_days": skill_success_days.get(row["target_id"], {}),
            "skill_independent_successes": skill_independent_successes.get(
                row["target_id"], {}
            ),
            "skill_independent_days": skill_independent_days.get(
                row["target_id"], {}
            ),
            "mean_response_time_ms": (
                round(float(row["mean_latency"]), 1)
                if row["mean_latency"] is not None
                else None
            ),
        }
        for row in rows
    }
