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
    success: bool = False,
    event_role: str = "evidence",
    interval_since_last_evidence: float | None = None,
    occurred_at: str = "",
) -> dict | None:
    """Registra un evento de evidencia longitudinal (append-only).

    Si `interval_since_last_evidence` no se pasa, se DERIVA de la evidencia
    anterior del mismo `(target_type, target_id)` con `services.evidence`
    (None en la primera observación). Devuelve la fila creada o None si el
    usuario no existe. Nunca lanza por datos parciales: el ledger es señal.
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
            "surface_form, lexical_unit, task, activity, success, "
            "interval_since_last_evidence, event_role) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                1 if success else 0,
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
        "success": bool(success),
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
                    1 if entry.get("success") else 0,
                    interval,
                    entry.get("event_role", "evidence"),
                )
            )
        conn.executemany(
            "INSERT INTO learning_evidence "
            "(user_id, occurred_at, skill, target_type, target_id, "
            "surface_form, lexical_unit, task, activity, success, "
            "interval_since_last_evidence, event_role) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            "surface_form, lexical_unit, task, activity, success, "
            "interval_since_last_evidence, event_role "
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
    Los ítems sin eventos no aparecen: el llamador usa `empty_summary()`.
    """
    with closing(_conn()) as conn:
        rows = conn.execute(
            "SELECT target_id, COUNT(*) AS attempts, "
            "COALESCE(SUM(success), 0) AS successes, "
            "COUNT(DISTINCT CASE WHEN success = 1 "
            "THEN substr(occurred_at, 1, 10) END) AS distinct_success_days "
            "FROM learning_evidence "
            "WHERE user_id = ? AND target_type = ? "
            "GROUP BY target_id",
            (user_id, target_type),
        ).fetchall()
        interval_rows = conn.execute(
            "SELECT target_id, interval_since_last_evidence AS interval "
            "FROM learning_evidence "
            "WHERE user_id = ? AND target_type = ? AND success = 1 "
            "AND interval_since_last_evidence IS NOT NULL "
            "ORDER BY target_id, occurred_at ASC, id ASC",
            (user_id, target_type),
        ).fetchall()
    intervals: dict[str, list[float]] = {}
    for row in interval_rows:
        intervals.setdefault(row["target_id"], []).append(
            round(float(row["interval"]), 4)
        )
    return {
        row["target_id"]: {
            "attempts": int(row["attempts"]),
            "successes": int(row["successes"]),
            "distinct_success_days": int(row["distinct_success_days"]),
            "intervals": intervals.get(row["target_id"], []),
        }
        for row in rows
    }
