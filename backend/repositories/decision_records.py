"""Repositorio del registro de DECISIONES (Decision Provenance, V3.66 → V3.68).

La decisión de tarea del Planner 3.0 deja de ser efímera: cada carta servida en
la cola de repaso léxico se registra como una fila con la evidencia y la política
que gobernaron su `p_success`. Es el PROVENANCE que V3.65 dejó pendiente (P3).

V3.67 convirtió el registro de append-only en **idempotente por `decision_id`
determinista** y le dio CICLO DE VIDA.

V3.68 (P1-02 y P1-03 de la auditoría de V3.67) lo endurece en dos frentes:

**P1-02 — el ciclo de vida pasa a ser una FSM REAL.** Hasta V3.67 las
transiciones eran un `UPDATE ... WHERE decision_id = ?` sin comprobar el estado
previo, así que se aceptaba `completed → served`, `computed → completed` o
`abandoned → completed`. Ahora las transiciones válidas están DECLARADAS
(`_ALLOWED_TRANSITIONS`) y se aplican con una escritura compare-and-set:

    computed → served → started → completed / abandoned

    served   → served     (idempotente: refresco de la cola)
    served   → started
    served   → completed  (VÁLIDA y declarada: sin inicio declarado el outcome
                           no se pierde — el round-trip del cliente es
                           best-effort y perder la medición sería peor)
    served   → abandoned
    started  → started    (idempotente)
    started  → completed / abandoned
    completed→ completed  (SOLO con `outcome` idéntico: idempotente)
    abandoned→ abandoned  (idempotente)

    RECHAZADAS: computed → started/completed/abandoned, completed → *, y
    abandoned → served/started/completed.

**P1-03 — el provenance queda ligado al USUARIO y al TARGET ejecutado.** Todas
las transiciones reciben `user_id` y el `target_id` del intento; la escritura los
exige en el `WHERE`, de modo que el `decision_id` de OTRO usuario (o de otro
ítem) no puede modificar la fila. El fallo es **best-effort y silencioso hacia el
llamador** (nunca rompe la cola ni el drill) pero **contabilizado** por motivo en
`transition_health()`, para que la pérdida sea visible.

La ACTIVIDAD no es puerta: el drill degrada peldaños (recognition → recall →
sentence) y el alumno puede cambiar de rung, así que una actividad distinta es un
hecho legítimo —y señal de auditoría del Planner— que se REGISTRA
(`executed_activity`) en vez de rechazar la medición.

Nunca lanza hacia el llamador (el escritor es best-effort desde la cola).
"""

from __future__ import annotations

import hashlib
import json
from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user
from services import observed_difficulty

# Versión DECLARADA de la política de resolución de `p_success` (V3.68).
# `task_empirical` → `target_empirical` → `skill_empirical` → `margin`.
DECISION_POLICY_VERSION = "v3.68.0"

# Estados del ciclo de vida (V3.67, P1-02). `computed` es el default de las filas
# legacy y de las recién insertadas antes del primer `served`.
_DECISION_STATUSES = (
    "computed",
    "served",
    "started",
    "completed",
    "abandoned",
)

# Estados TERMINALES del ciclo (V3.68, P1-02): una vez alcanzados solo se acepta
# la repetición idempotente del mismo estado (y, en `completed`, del MISMO
# outcome). Cualquier otra transición desde aquí se rechaza y se cuenta.
_TERMINAL_STATUSES = ("completed", "abandoned")

# Transiciones VÁLIDAS de la FSM (V3.68, P1-02): mapa `estado destino → estados
# de origen permitidos`. Todo lo que no esté aquí se rechaza. La tabla es la
# ÚNICA fuente de verdad de la máquina de estados.
_ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "served": ("computed", "served"),
    "started": ("served", "started"),
    "completed": ("served", "started", "completed"),
    "abandoned": ("served", "started", "abandoned"),
}

# Outcomes MEDIBLES (V3.68, P2-08): son los únicos que entran en la calibración.
# `unclear` (el ASR no reconoció el audio) y `abandoned` no son evidencia de
# dominio: se registran, pero NO puntúan al Planner.
MEASURED_OUTCOMES: tuple[str, ...] = ("ok", "ko")

# Motivos de RECHAZO contabilizados (V3.68, P1-03). Se separan para que la señal
# de salud diga QUÉ está fallando, no solo cuánto.
_TRANSITION_REASONS = (
    "missing",
    "wrong_owner",
    "target_mismatch",
    "duplicate_outcome",
    "invalid_transition",
)

# Contadores MONOTÓNICOS en memoria del proceso (V3.68, P1-03). No se persisten
# (volumen doméstico): hacen visible la pérdida silenciosa sin romper nada.
_TRANSITION_COUNTS: dict[str, int] = dict.fromkeys(_TRANSITION_REASONS, 0)
_TRANSITION_OK = 0
# Re-servicios de una decisión ya MEDIDA: la medición manda y no se sobrescribe.
_CLOSED_DECISIONS = 0
# Reaperturas de una decisión terminal SIN outcome medible (V3.68, P1-02).
_REOPENED_DECISIONS = 0

# Separador de los componentes del hash de identidad: no aparece en los valores
# de negocio (IDs, claves y huellas usan hex/base64 seguros).
_ID_SEPARATOR = "\x1f"

# Valor de `provenance_status` de una fila que se reabrió al re-servirse.
PROVENANCE_RECORDED = "recorded"
PROVENANCE_REOPENED = "reopened"


def build_decision_id(
    user_id: str,
    *,
    target_id: str = "",
    task_key: str = "",
    decision_start_fingerprint: str = "",
) -> str:
    """`decision_id` determinista (V3.67 → V3.68): hash estable de la identidad.

    La MISMA decisión (mismo alumno, mismo ítem, misma DEFINICIÓN de tarea y
    mismo snapshot de inicio) produce el MISMO id, de modo que el upsert de
    `record_decision` hace idempotente el ciclo GET→GET→GET. Puro y nunca lanza.

    V3.68 (P1-01): hashea `task_key` (la DEFINICIÓN: ítem, actividad, apoyo,
    carga servida y skill evaluada) y NO la instancia. El contexto se elige en el
    GET del peldaño, así que la identidad de la decisión no puede depender de él
    (si dependiera, el `decision_id` no existiría cuando el Planner decide).
    """
    raw = _ID_SEPARATOR.join(
        (
            str(user_id or ""),
            str(target_id or ""),
            str(task_key or ""),
            str(decision_start_fingerprint or ""),
            DECISION_POLICY_VERSION,
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _json(value: object, default: object) -> str:
    """JSON determinista de un valor (nunca lanza; usa `default` si no encaja)."""
    if isinstance(value, list) and isinstance(default, list):
        payload: object = value
    elif isinstance(value, dict) and isinstance(default, dict):
        payload = value
    else:
        payload = default
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


_RECORD_COLUMNS = (
    "user_id, decision_id, created_at, target_id, task_key, task_signature, "
    "context_id, context_instance, served_load_json, support_level, "
    "assessment_mode, decision_status, decision_start_fingerprint, "
    "state_fingerprint, policy_version, selected_skill, selected_activity, "
    "selected_reason, p_success, p_success_source, expected_learning_value, "
    "candidates_json, drivers_json, provenance_status"
)


def record_decision(
    user_id: str,
    *,
    target_id: str = "",
    task_key: str = "",
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

    `task_key` es la DEFINICIÓN de la tarea (lo que el Planner conoce antes de
    elegir instancia) y `task_signature` la INSTANCIA (definición + contexto). En
    la cola el contexto aún no existe, así que la instancia llega como
    `task_key + "|"` y la completa `mark_served` cuando el GET del peldaño declara
    el contexto servido.

    `candidates` son las alternativas puntuadas (`decision.alternatives`) y
    `drivers` los drivers proyectados del eje elegido. Ambos se serializan como
    JSON determinista. `served_load` es la carga servida (vector de dificultad)
    serializada como JSON. Devuelve la fila resumida o `None` si el usuario no
    existe.

    V3.68 (P1-02, regla de re-servicio): el `decision_id` es determinista, así que
    la MISMA decisión puede re-servirse. Tres caminos declarados:

    - fila nueva → INSERT con status `computed`;
    - fila NO terminal → upsert de la metadata (el estado NO se toca);
    - fila TERMINAL **sin** outcome medible (`abandoned`, o `completed` con
      `unclear`/`''`) → se REABRE (status `computed`, timestamps y outcome
      limpiados, `provenance_status = "reopened"`);
    - fila TERMINAL **con** outcome medible (`ok`/`ko`) → **no se sobrescribe**:
      la medición manda y el re-servicio se cuenta como `closed_decision`.
    """
    if get_user(user_id) is None:
        return None
    global _CLOSED_DECISIONS, _REOPENED_DECISIONS
    now = _now()
    target_id = str(target_id or "")
    task_key = str(task_key or "")
    task_signature = str(task_signature or "")
    decision_id = build_decision_id(
        user_id,
        target_id=target_id,
        task_key=task_key,
        decision_start_fingerprint=str(decision_start_fingerprint or ""),
    )
    values = (
        user_id,
        decision_id,
        now,
        target_id,
        task_key,
        task_signature,
        str(context_id or ""),
        str(context_instance or ""),
        _json(served_load, {}),
        str(support_level or ""),
        str(assessment_mode or ""),
        # `decision_status` se decide por rama (ver abajo).
        str(decision_start_fingerprint or ""),
        str(state_fingerprint or ""),
        DECISION_POLICY_VERSION,
        str(selected_skill or ""),
        str(selected_activity or ""),
        str(selected_reason or ""),
        p_success,
        str(p_success_source or ""),
        expected_learning_value,
        _json(candidates, []),
        _json(drivers, {}),
        PROVENANCE_RECORDED,
    )
    with closing(_conn()) as conn, conn:
        existing = conn.execute(
            "SELECT decision_status, outcome, created_at FROM decision_records "
            "WHERE decision_id = ?",
            (decision_id,),
        ).fetchone()
        status = "computed"
        reopened = False
        if existing is not None:
            status = str(existing["decision_status"] or "computed")
            if status in _TERMINAL_STATUSES:
                if str(existing["outcome"] or "") in MEASURED_OUTCOMES:
                    # La medición manda: el re-servicio NO se sobrescribe.
                    _CLOSED_DECISIONS += 1
                    return {
                        "decision_id": decision_id,
                        "user_id": user_id,
                        "target_id": target_id,
                        "task_key": task_key,
                        "task_instance_key": task_signature,
                        "created_at": str(existing["created_at"] or now),
                        "policy_version": DECISION_POLICY_VERSION,
                        "reopened": False,
                        "closed": True,
                    }
                # Terminal SIN medición útil → se reabre para poder medirla.
                status = "computed"
                reopened = True
                _REOPENED_DECISIONS += 1
        # `provenance_status` viaja en `values` como `recorded`; la reapertura lo
        # reescribe explícitamente para que la fila declare su historia.
        insert_values = values[:11] + (status,) + values[11:]
        conn.execute(
            f"INSERT INTO decision_records ({_RECORD_COLUMNS}) "
            f"VALUES ({', '.join('?' * len(insert_values))}) "
            "ON CONFLICT(decision_id) DO UPDATE SET "
            "user_id = excluded.user_id, "
            "target_id = excluded.target_id, "
            "task_key = excluded.task_key, "
            "task_signature = excluded.task_signature, "
            "context_id = excluded.context_id, "
            "context_instance = excluded.context_instance, "
            "served_load_json = excluded.served_load_json, "
            "support_level = excluded.support_level, "
            "assessment_mode = excluded.assessment_mode, "
            "decision_start_fingerprint = excluded.decision_start_fingerprint, "
            "state_fingerprint = excluded.state_fingerprint, "
            "policy_version = excluded.policy_version, "
            "selected_skill = excluded.selected_skill, "
            "selected_activity = excluded.selected_activity, "
            "selected_reason = excluded.selected_reason, "
            "p_success = excluded.p_success, "
            "p_success_source = excluded.p_success_source, "
            "expected_learning_value = excluded.expected_learning_value, "
            "candidates_json = excluded.candidates_json, "
            "drivers_json = excluded.drivers_json, "
            "decision_status = excluded.decision_status, "
            "provenance_status = CASE WHEN ? THEN ? "
            "ELSE decision_records.provenance_status END, "
            # Reapertura: los sellos del ciclo anterior se limpian SOLO si la rama
            # lo decidió (`status == 'computed'` sobre una fila terminal previa).
            "served_at = CASE WHEN ? THEN '' ELSE decision_records.served_at END, "
            "started_at = CASE WHEN ? THEN '' ELSE decision_records.started_at END, "
            "completed_at = CASE WHEN ? THEN '' "
            "ELSE decision_records.completed_at END, "
            "outcome = CASE WHEN ? THEN '' ELSE decision_records.outcome END",
            insert_values + (reopened, PROVENANCE_REOPENED, reopened, reopened,
                             reopened, reopened),
        )
    return {
        "decision_id": decision_id,
        "user_id": user_id,
        "target_id": target_id,
        "task_key": task_key,
        "task_instance_key": task_signature,
        "created_at": now,
        "policy_version": DECISION_POLICY_VERSION,
        "reopened": reopened,
        "closed": False,
    }


def _count_reason(reason: str) -> None:
    """Suma UN rechazo al motivo declarado (monotónico; nunca lanza)."""
    if reason in _TRANSITION_COUNTS:
        _TRANSITION_COUNTS[reason] += 1


def _classify_rejection(
    row,
    user_id: str,
    target_id: str,
    outcome: str,
) -> str:
    """Motivo del rechazo de una transición que no actualizó ninguna fila.

    El orden delata la CAUSA más específica: fila inexistente, dueño distinto,
    target distinto, repetición con outcome distinto y, por último, transición
    inválida de la FSM. Puro; nunca lanza.
    """
    if row is None:
        return "missing"
    if str(row["user_id"] or "") != user_id:
        return "wrong_owner"
    if target_id and str(row["target_id"] or "") != target_id:
        return "target_mismatch"
    if (
        outcome
        and str(row["decision_status"] or "") == "completed"
        and str(row["outcome"] or "") != outcome
    ):
        return "duplicate_outcome"
    return "invalid_transition"


def _transition(
    user_id: str,
    decision_id: str,
    *,
    status: str,
    timestamp_field: str,
    outcome: str = "",
    target_id: str = "",
    activity: str = "",
    context: tuple[str, str] | None = None,
) -> bool:
    """Transición de estado de UNA decisión (V3.68, P1-02/P1-03).

    Escritura **compare-and-set**: el `UPDATE` solo aplica si la fila pertenece al
    `user_id`, su `target_id` coincide (cuando el llamador lo declara) y el estado
    ACTUAL está entre los orígenes válidos de `status` (`_ALLOWED_TRANSITIONS`).
    En `completed`, repetir el estado exige el MISMO `outcome` (idempotencia).

    `activity` se REGISTRA en `executed_activity` (nunca es puerta) y `context`
    permite declarar el contexto de la INSTANCIA servida (actualiza `context_id`,
    `context_instance` y la instancia `task_signature` con la misma función pura
    del ledger).

    Devuelve `True` si actualizó una fila y `False` si la rechazó (contabilizando
    el motivo). Nunca lanza.
    """
    origins = _ALLOWED_TRANSITIONS.get(status)
    if not origins:
        _count_reason("invalid_transition")
        return False
    try:
        with closing(_conn()) as conn, conn:
            # La lista de parámetros se construye en el ORDEN exacto de los `?`
            # del SQL: SET…, WHERE, IN… y la cláusula de idempotencia.
            assignments = [f"{timestamp_field} = ?", "decision_status = ?"]
            params: list = [_now(), status]
            if outcome:
                assignments.append("outcome = ?")
                params.append(outcome)
            if activity:
                assignments.append("executed_activity = ?")
                params.append(activity)
            if context is not None:
                context_id, context_instance = context
                instance_key = ""
                if context_id or context_instance:
                    stored = conn.execute(
                        "SELECT task_key FROM decision_records "
                        "WHERE decision_id = ?",
                        (decision_id,),
                    ).fetchone()
                    task_key = str((stored["task_key"] if stored else "") or "")
                    if task_key:
                        instance_key = observed_difficulty.task_instance_key_from(
                            task_key, context_instance or context_id
                        )
                assignments.extend(
                    ("context_id = ?", "context_instance = ?", "task_signature = ?")
                )
                params.extend((context_id, context_instance, instance_key))
            clauses = ["decision_id = ?", "user_id = ?"]
            params.extend((decision_id, user_id))
            if target_id:
                # Guarda de TARGET (V3.68, P1-03): el `decision_id` de otro ítem
                # no puede servir ni cerrar esta decisión.
                clauses.append("target_id = ?")
                params.append(target_id)
            placeholders = ", ".join("?" for _ in origins)
            clauses.append(f"decision_status IN ({placeholders})")
            params.extend(origins)
            if status == "completed":
                # Idempotencia EXIGENTE: repetir `completed` solo con el MISMO
                # outcome (la primera medición de la sesión manda).
                clauses.append("(decision_status <> 'completed' OR outcome = ?)")
                params.append(outcome)
            cursor = conn.execute(
                f"UPDATE decision_records SET {', '.join(assignments)} "
                f"WHERE {' AND '.join(clauses)}",
                params,
            )
            if cursor.rowcount > 0:
                global _TRANSITION_OK
                _TRANSITION_OK += 1
                return True
            row = conn.execute(
                "SELECT user_id, target_id, decision_status, outcome "
                "FROM decision_records WHERE decision_id = ?",
                (decision_id,),
            ).fetchone()
    except Exception:  # noqa: BLE001 — el ciclo de vida es best-effort
        _count_reason("missing")
        return False
    _count_reason(_classify_rejection(row, user_id, target_id, outcome))
    return False


def mark_served(
    user_id: str,
    decision_id: str,
    *,
    target_id: str = "",
    activity: str = "",
    context_id: str = "",
    context_instance: str = "",
) -> bool:
    """Marca una decisión como SERVIDA (el cliente recibió la carta).

    Declara además la INSTANCIA servida (`context_id`/`context_instance`) y la
    actividad EJECUTADA, que es lo que permite distinguir después
    `P(éxito | alumno, tarea)` de `P(éxito | alumno, instancia)`.
    """
    return _transition(
        user_id,
        decision_id,
        status="served",
        timestamp_field="served_at",
        target_id=target_id,
        activity=activity,
        context=(str(context_id or ""), str(context_instance or "")),
    )


def mark_started(
    user_id: str,
    decision_id: str,
    *,
    target_id: str = "",
    activity: str = "",
) -> bool:
    """Marca una decisión como INICIADA (el alumno empezó el peldaño)."""
    return _transition(
        user_id,
        decision_id,
        status="started",
        timestamp_field="started_at",
        target_id=target_id,
        activity=activity,
    )


def mark_completed(
    user_id: str,
    decision_id: str,
    outcome: str = "",
    *,
    target_id: str = "",
    activity: str = "",
) -> bool:
    """Marca una decisión como COMPLETADA y guarda el `outcome` del intento.

    `outcome` es el veredicto del intento (`ok`/`ko`/`unclear`); solo `ok`/`ko`
    son MEDIBLES (`MEASURED_OUTCOMES`) y entran en la calibración. Repetir un
    `completed` exige el MISMO outcome: un outcome distinto se rechaza como
    `duplicate_outcome` (la primera medición de la sesión manda).
    """
    return _transition(
        user_id,
        decision_id,
        status="completed",
        timestamp_field="completed_at",
        outcome=str(outcome or ""),
        target_id=target_id,
        activity=activity,
    )


def mark_abandoned(
    user_id: str,
    decision_id: str,
    *,
    target_id: str = "",
    activity: str = "",
) -> bool:
    """Marca una decisión como ABANDONADA (servida pero nunca completada).

    Es válida desde `served`/`started` y NO desde `completed`: el abandono
    declarado por el cliente al salir del peldaño no puede borrar una medición
    ya registrada (la terminalidad la decide la FSM, no el cliente).
    """
    return _transition(
        user_id,
        decision_id,
        status="abandoned",
        timestamp_field="completed_at",
        target_id=target_id,
        activity=activity,
    )


def close_stale(user_id: str, *, before_iso: str) -> int:
    """Cierra como `abandoned` las decisiones SERVIDAS/INICIADAS y antiguas.

    Barrido de higiene del ciclo de vida (V3.68, P1-02): una decisión servida que
    el alumno nunca completó ni abandonó explícitamente quedaría en `served` para
    siempre y ensuciaría la lectura del provenance. Solo toca `served`/`started`
    (NUNCA `computed`, que aún no se ha servido, ni las terminales) y solo filas
    del alumno. La antigüedad se mide desde `served_at` y, si falta, desde
    `created_at`. Devuelve cuántas filas cerró (0 ante cualquier fallo: nunca
    lanza).
    """
    if not user_id or not before_iso:
        return 0
    try:
        with closing(_conn()) as conn, conn:
            cursor = conn.execute(
                "UPDATE decision_records "
                "SET decision_status = 'abandoned', completed_at = ? "
                "WHERE user_id = ? AND decision_status IN ('served', 'started') "
                "AND COALESCE(NULLIF(served_at, ''), created_at) < ?",
                (_now(), user_id, before_iso),
            )
            return int(cursor.rowcount or 0)
    except Exception:  # noqa: BLE001 — el barrido nunca rompe la cola
        return 0


def transition_health() -> dict:
    """Salud de la FSM del ciclo de vida (V3.68, P1-03; puro).

    Devuelve los contadores MONOTÓNICOS del proceso: transiciones aplicadas,
    reaperturas, re-servicios de decisiones ya medidas y rechazos por motivo. Todo
    a `0` es lo sano; un `wrong_owner` creciente alertaría de un `decision_id`
    ajeno llegando al endpoint.
    """
    return {
        "ok": _TRANSITION_OK,
        "reopened": _REOPENED_DECISIONS,
        "closed_decision": _CLOSED_DECISIONS,
        "rejections": dict(_TRANSITION_COUNTS),
    }


# ---------------------------------------------------------------------------
# Lectura y analítica (V3.67, P3-11 / P3-12): SOLO LECTURA. Responde "¿qué
# recomendó el Planner, con qué `p_success`, y — una vez `completed` — si
# acertó?", para validar SIN ML si el Planner heurístico predice.
# ---------------------------------------------------------------------------

_DECISION_SELECT = (
    "id, user_id, decision_id, created_at, target_id, task_key, task_signature, "
    "context_id, context_instance, served_load_json, support_level, "
    "assessment_mode, decision_status, served_at, started_at, completed_at, "
    "outcome, provenance_status, decision_start_fingerprint, state_fingerprint, "
    "policy_version, selected_skill, selected_activity, executed_activity, "
    "selected_reason, p_success, p_success_source, expected_learning_value, "
    "candidates_json, drivers_json"
)


def _outcome_measured(outcome: object) -> bool:
    """`True` si el outcome es MEDIBLE (`ok`/`ko`) y por tanto calibrable."""
    return str(outcome or "") in MEASURED_OUTCOMES


def _row_to_decision(row) -> dict:
    """Fila SQLite → payload legible (JSON determinista de los campos blob).

    V3.68 (P1-01/P1-03) añade la lectura honesta de la identidad y del estado:
    `task_key` (DEFINICIÓN) e `task_instance_key` (INSTANCIA, con `instance_known`
    diciendo si el contexto llegó a declararse), `executed_activity` con
    `activity_match` (auditoría del Planner) y `outcome_measured` (si el resultado
    puntúa en la calibración).
    """
    served_load = {}
    try:
        served_load = json.loads(row["served_load_json"] or "{}")
    except (ValueError, TypeError):
        served_load = {}
    selected_activity = str(row["selected_activity"] or "")
    executed_activity = str(row["executed_activity"] or "")
    outcome = str(row["outcome"] or "")
    return {
        "decision_id": row["decision_id"],
        "created_at": row["created_at"],
        "target_id": row["target_id"],
        "task_key": str(row["task_key"] or ""),
        "task_instance_key": str(row["task_signature"] or ""),
        "instance_known": bool(
            str(row["context_id"] or "") or str(row["context_instance"] or "")
        ),
        "context_id": row["context_id"],
        "context_instance": row["context_instance"],
        "served_load": served_load,
        "support_level": row["support_level"],
        "assessment_mode": row["assessment_mode"],
        "decision_status": row["decision_status"],
        "served_at": row["served_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "outcome": outcome,
        "outcome_measured": _outcome_measured(outcome),
        "provenance_status": row["provenance_status"],
        "decision_start_fingerprint": row["decision_start_fingerprint"],
        "state_fingerprint": row["state_fingerprint"],
        "policy_version": row["policy_version"],
        "selected_skill": row["selected_skill"],
        "selected_activity": selected_activity,
        "executed_activity": executed_activity,
        "activity_match": (
            executed_activity == selected_activity
            if selected_activity and executed_activity
            else None
        ),
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
# `ok` sobre las filas `completed` MEDIBLES). Sin ML: solo descriptivo.
_CALIBRATION_BANDS = (0.2, 0.4, 0.6, 0.8, 1.0)


def calibration_report(user_id: str) -> dict:
    """Informe de calibración predicted vs observed (V3.67 → V3.68; solo lectura).

    Sobre las filas `completed` del alumno, agrupa por banda de `p_success` (ancho
    0.2) y devuelve, por banda, cuántas decisiones cayeron, la tasa de acierto
    OBSERVADA (`outcome == "ok"`) y la diferencia media predicho − observado.

    V3.68 (P2-08, honestidad del denominador): solo puntúan las filas con outcome
    MEDIBLE (`ok`/`ko`). `unclear` (el ASR no reconoció el audio: incertidumbre de
    MEDICIÓN, no fallo de dominio) y `abandoned` NO son evidencia de dominio y
    quedan FUERA de las bandas y del denominador, con su propio contador. Meterlos
    como "no éxito" sesgaría la lectura del Planner a la baja.

    Nunca lanza: ante un fallo devuelve el informe vacío.
    """
    empty: dict = {
        "completed_count": 0,
        "measured_count": 0,
        "unclear_count": 0,
        "abandoned_count": 0,
        "other_count": 0,
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
    counts = {"unclear": 0, "abandoned": 0, "other": 0}
    bands: dict[float, dict] = {}
    for row in completed:
        outcome = str(row.get("outcome") or "")
        if not _outcome_measured(outcome):
            # Fuera del denominador: se cuentan, no se puntúan (V3.68, P2-08).
            if outcome in ("unclear", "abandoned"):
                counts[outcome] += 1
            else:
                counts["other"] += 1
            continue
        p = row.get("p_success")
        if p is None:
            counts["other"] += 1
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
        if outcome == "ok":
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
        "measured_count": total_count,
        "unclear_count": counts["unclear"],
        "abandoned_count": counts["abandoned"],
        "other_count": counts["other"],
        "bands": result,
        "calibration_error": (
            round(total_error / total_count, 3) if total_count else None
        ),
    }
