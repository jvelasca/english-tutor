"""Repositorio del registro de DECISIONES (Decision Provenance, V3.66 → V3.67).

La decisión de tarea del Planner 3.0 deja de ser efímera: cada carta servida en
la cola de repaso léxico se registra como una fila con la evidencia y la política
que gobernaron su `p_success`. Es el PROVENANCE que V3.65 dejó pendiente (P3).

V3.67 (P1-02, cierre del ciclo decision → outcome → evidencia) transforma el
registro de append-only a **idempotente por `decision_id` determinista** y le da
CICLO DE VIDA:

    computed → served → started → completed/abandoned

- `record_decision` hace **upsert** (`INSERT ... ON CONFLICT(decision_id) DO
  UPDATE`): GET→GET→GET de la MISMA decisión no duplica filas (V3.66 con
  `uuid4` creaba una fila por GET).
- `decision_id` es un **hash estable** de `(user_id, target_id, task_signature,
  decision_start_fingerprint, policy_version)`, no un uuid aleatorio.
- `mark_served` / `mark_started` / `mark_completed(decision_id, outcome)`
  transicionan el estado; `mark_completed` guarda el resultado del intento, que
  habilita la calibración "¿el Planner acertó?" (sin ML, solo descriptiva).

Nunca lanza hacia el llamador (el escritor es best-effort desde la cola).
"""

from __future__ import annotations

import hashlib
import json
from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user

# Versión DECLARADA de la política de resolución de `p_success` (V3.67).
# `task_empirical` → `target_empirical` → `skill_empirical` → `margin`.
DECISION_POLICY_VERSION = "v3.67.0"

# Estados del ciclo de vida (V3.67, P1-02). `computed` es el default de las filas
# legacy y de las recién insertadas antes del primer `served`.
_DECISION_STATUSES = (
    "computed",
    "served",
    "started",
    "completed",
    "abandoned",
)

# Separador de los componentes del hash de identidad: no aparece en los valores
# de negocio (IDs, firmas y huellas usan hex/base64 seguros).
_ID_SEPARATOR = "\x1f"


def build_decision_id(
    user_id: str,
    *,
    target_id: str = "",
    task_signature: str = "",
    decision_start_fingerprint: str = "",
) -> str:
    """`decision_id` determinista (V3.67, P1-02): hash estable de la identidad.

    La MISMA decisión (mismo alumno, mismo ítem, misma firma de tarea y mismo
    snapshot de inicio) produce el MISMO id, de modo que el upsert de
    `record_decision` hace idempotente el ciclo GET→GET→GET. Puro y nunca lanza.
    """
    raw = _ID_SEPARATOR.join(
        (
            str(user_id or ""),
            str(target_id or ""),
            str(task_signature or ""),
            str(decision_start_fingerprint or ""),
            DECISION_POLICY_VERSION,
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def record_decision(
    user_id: str,
    *,
    target_id: str = "",
    task_signature: str = "",
    context_id: str = "",
    context_instance: str = "",
    served_load: object = None,
    support_level: str = "",
    assessment_mode: str = "",
    decision_start_fingerprint: str = "",
    state_fingerprint: str = "",
    selected_skill: str = "",
    selected_activity: str = "",
    selected_reason: str = "",
    p_success: float | None = None,
    p_success_source: str = "",
    expected_learning_value: float | None = None,
    candidates: list | None = None,
    drivers: dict | None = None,
) -> dict | None:
    """Registra UNA decisión de tarea servida (upsert idempotente; best-effort).

    `candidates` son las alternativas puntuadas (`decision.alternatives`) y
    `drivers` los drivers proyectados del eje elegido. Ambos se serializan como
    JSON determinista. `served_load` es la carga servida (vector de dificultad)
    serializada como JSON. Devuelve la fila resumida o `None` si el usuario no
    existe.

    V3.67 (P1-02): el `decision_id` es determinista y la escritura es UPSERT:
    re-servir la MISMA decisión actualiza los campos de la tarea y conserva el
    `id`/`created_at` originales, sin duplicar fila.
    """
    if get_user(user_id) is None:
        return None
    now = _now()
    target_id = str(target_id or "")
    decision_id = build_decision_id(
        user_id,
        target_id=target_id,
        task_signature=str(task_signature or ""),
        decision_start_fingerprint=str(decision_start_fingerprint or ""),
    )
    candidates_json = json.dumps(
        candidates if isinstance(candidates, list) else [],
        ensure_ascii=False,
        sort_keys=True,
    )
    drivers_json = json.dumps(
        drivers if isinstance(drivers, dict) else {},
        ensure_ascii=False,
        sort_keys=True,
    )
    served_load_json = json.dumps(
        served_load if isinstance(served_load, dict) else {},
        ensure_ascii=False,
        sort_keys=True,
    )
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO decision_records "
            "(user_id, decision_id, created_at, target_id, task_signature, "
            "context_id, context_instance, served_load_json, support_level, "
            "assessment_mode, decision_status, decision_start_fingerprint, "
            "state_fingerprint, policy_version, selected_skill, "
            "selected_activity, selected_reason, p_success, p_success_source, "
            "expected_learning_value, candidates_json, drivers_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'computed', ?, ?, ?, ?, ?, "
            "?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(decision_id) DO UPDATE SET "
            "target_id = excluded.target_id, "
            "task_signature = excluded.task_signature, "
            "context_id = excluded.context_id, "
            "context_instance = excluded.context_instance, "
            "served_load_json = excluded.served_load_json, "
            "support_level = excluded.support_level, "
            "assessment_mode = excluded.assessment_mode, "
            "decision_start_fingerprint = excluded.decision_start_fingerprint, "
            "state_fingerprint = excluded.state_fingerprint, "
            "selected_skill = excluded.selected_skill, "
            "selected_activity = excluded.selected_activity, "
            "selected_reason = excluded.selected_reason, "
            "p_success = excluded.p_success, "
            "p_success_source = excluded.p_success_source, "
            "expected_learning_value = excluded.expected_learning_value, "
            "candidates_json = excluded.candidates_json, "
            "drivers_json = excluded.drivers_json",
            (
                user_id,
                decision_id,
                now,
                target_id,
                str(task_signature or ""),
                str(context_id or ""),
                str(context_instance or ""),
                served_load_json,
                str(support_level or ""),
                str(assessment_mode or ""),
                str(decision_start_fingerprint or ""),
                str(state_fingerprint or ""),
                DECISION_POLICY_VERSION,
                str(selected_skill or ""),
                str(selected_activity or ""),
                str(selected_reason or ""),
                p_success,
                str(p_success_source or ""),
                expected_learning_value,
                candidates_json,
                drivers_json,
            ),
        )
    return {
        "decision_id": decision_id,
        "user_id": user_id,
        "target_id": target_id,
        "task_signature": str(task_signature or ""),
        "created_at": now,
        "policy_version": DECISION_POLICY_VERSION,
    }


def _transition(
    decision_id: str,
    *,
    status: str,
    timestamp_field: str,
    extra: tuple[str, str] | None = None,
) -> bool:
    """Transición de estado de UNA decisión (V3.67, P1-02; pura en el I/O).

    Marca `decision_status` y sella `timestamp_field` con `_now()` SOLO si la
    fila existe. `extra` permite añadir `(columna, valor)` (p. ej. `outcome` en
    `completed`). Devuelve `True` si se actualizó una fila, `False` si no.
    """
    now = _now()
    assignments = [f"{timestamp_field} = ?", "decision_status = ?"]
    params: list = [now, status]
    if extra is not None:
        column, value = extra
        assignments.append(f"{column} = ?")
        params.append(value)
    params.append(decision_id)
    with closing(_conn()) as conn, conn:
        cursor = conn.execute(
            f"UPDATE decision_records SET {', '.join(assignments)} "
            "WHERE decision_id = ?",
            params,
        )
        return cursor.rowcount > 0


def mark_served(decision_id: str) -> bool:
    """Marca una decisión como SERVIDA (el cliente recibió la carta)."""
    return _transition(decision_id, status="served", timestamp_field="served_at")


def mark_started(decision_id: str) -> bool:
    """Marca una decisión como INICIADA (el alumno empezó el peldaño)."""
    return _transition(decision_id, status="started", timestamp_field="started_at")


def mark_completed(decision_id: str, outcome: str = "") -> bool:
    """Marca una decisión como COMPLETADA y guarda el `outcome` del intento.

    `outcome` es el resultado del intento (`success`/`failure`/`abandoned`...),
    la pieza que cierra el ciclo decision → outcome → evidencia para la
    calibración descriptiva del Bloque D.
    """
    return _transition(
        decision_id,
        status="completed",
        timestamp_field="completed_at",
        extra=("outcome", str(outcome or "")),
    )


def mark_abandoned(decision_id: str) -> bool:
    """Marca una decisión como ABANDONADA (servida pero nunca completada)."""
    return _transition(
        decision_id,
        status="abandoned",
        timestamp_field="completed_at",
    )


# ---------------------------------------------------------------------------
# Lectura y analítica (V3.67, P3-11 / P3-12): SOLO LECTURA. Responde "¿qué
# recomendó el Planner, con qué `p_success`, y — una vez `completed` — si
# acertó?", para validar SIN ML si el Planner heurístico predice.
# ---------------------------------------------------------------------------

_DECISION_SELECT = (
    "id, user_id, decision_id, created_at, target_id, task_signature, "
    "context_id, context_instance, served_load_json, support_level, "
    "assessment_mode, decision_status, served_at, started_at, completed_at, "
    "outcome, provenance_status, decision_start_fingerprint, state_fingerprint, "
    "policy_version, selected_skill, selected_activity, selected_reason, "
    "p_success, p_success_source, expected_learning_value, candidates_json, "
    "drivers_json"
)


def _row_to_decision(row) -> dict:
    """Fila SQLite → payload legible (JSON determinista de los campos blob)."""
    served_load = {}
    try:
        served_load = json.loads(row["served_load_json"] or "{}")
    except (ValueError, TypeError):
        served_load = {}
    return {
        "decision_id": row["decision_id"],
        "created_at": row["created_at"],
        "target_id": row["target_id"],
        "task_signature": row["task_signature"],
        "context_id": row["context_id"],
        "context_instance": row["context_instance"],
        "served_load": served_load,
        "support_level": row["support_level"],
        "assessment_mode": row["assessment_mode"],
        "decision_status": row["decision_status"],
        "served_at": row["served_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "outcome": row["outcome"],
        "provenance_status": row["provenance_status"],
        "decision_start_fingerprint": row["decision_start_fingerprint"],
        "state_fingerprint": row["state_fingerprint"],
        "policy_version": row["policy_version"],
        "selected_skill": row["selected_skill"],
        "selected_activity": row["selected_activity"],
        "selected_reason": row["selected_reason"],
        "p_success": row["p_success"],
        "p_success_source": row["p_success_source"],
        "expected_learning_value": row["expected_learning_value"],
    }


def list_decisions(
    user_id: str,
    *,
    status: str = "",
    target_id: str = "",
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Decisiones del alumno, más reciente primero (V3.67, P3-11; solo lectura).

    Filtros opcionales por `status` (estado del ciclo de vida) y `target_id`.
    Nunca lanza: ante un fallo devuelve `[]`.
    """
    clauses = ["user_id = ?"]
    params: list = [user_id]
    if status:
        clauses.append("decision_status = ?")
        params.append(status)
    if target_id:
        clauses.append("target_id = ?")
        params.append(target_id)
    clauses.append("1=1")
    params.extend([limit, offset])
    try:
        with closing(_conn()) as conn, conn:
            rows = conn.execute(
                f"SELECT {_DECISION_SELECT} FROM decision_records "
                f"WHERE {' AND '.join(clauses)} "
                "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
        return [_row_to_decision(row) for row in rows]
    except Exception:  # noqa: BLE001 — la lectura nunca rompe la cola
        return []


# Bandas de calibración (P3-12): 0.2 de ancho. El informe compara la `p_success`
# PREDICHA (heurística del Planner) con la tasa de acierto OBSERVADA (`outcome`
# `ok` sobre las filas `completed`). Sin ML: solo descriptivo.
_CALIBRATION_BANDS = (0.2, 0.4, 0.6, 0.8, 1.0)


def calibration_report(user_id: str) -> dict:
    """Informe de calibración predicted vs observed (V3.67, P3-12; solo lectura).

    Sobre las filas `completed` del alumno, agrupa por banda de `p_success`
    (ancho 0.2) y devuelve, por banda, cuántas decisiones cayeron, la tasa de
    acierto OBSERVADA (`outcome == "ok"`) y la diferencia media predicho −
    observado. `completed_count` totaliza las filas con resultado. Nunca lanza:
    ante un fallo devuelve el informe vacío.
    """
    empty: dict = {
        "completed_count": 0,
        "bands": [],
        "calibration_error": None,
    }
    try:
        with closing(_conn()) as conn, conn:
            rows = conn.execute(
                f"SELECT {_DECISION_SELECT} FROM decision_records "
                "WHERE user_id = ? AND decision_status = 'completed'",
                (user_id,),
            ).fetchall()
    except Exception:  # noqa: BLE001 — la lectura nunca rompe la cola
        return empty
    completed = [_row_to_decision(row) for row in rows]
    if not completed:
        return empty
    bands: dict[tuple, dict] = {}
    for row in completed:
        p = row.get("p_success")
        if p is None:
            continue
        band = min(
            (b for b in _CALIBRATION_BANDS if float(p) <= b),
            default=1.0,
        )
        slot = bands.setdefault(
            band,
            {"band": band, "count": 0, "observed_successes": 0, "sum_predicted": 0.0},
        )
        slot["count"] += 1
        slot["sum_predicted"] += float(p)
        if str(row.get("outcome") or "") == "ok":
            slot["observed_successes"] += 1
    result = []
    total_error = 0.0
    total_count = 0
    for band in _CALIBRATION_BANDS:
        slot = bands.get(band)
        if not slot:
            continue
        observed_rate = round(slot["observed_successes"] / slot["count"], 3)
        mean_predicted = round(slot["sum_predicted"] / slot["count"], 3)
        result.append(
            {
                "band": slot["band"],
                "count": slot["count"],
                "mean_predicted_p_success": mean_predicted,
                "observed_success_rate": observed_rate,
                "error": round(mean_predicted - observed_rate, 3),
            }
        )
        total_error += (mean_predicted - observed_rate) * slot["count"]
        total_count += slot["count"]
    return {
        "completed_count": len(completed),
        "bands": result,
        "calibration_error": (
            round(total_error / total_count, 3) if total_count else None
        ),
    }
