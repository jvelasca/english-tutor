"""Repositorio del registro de DECISIONES (Decision Provenance, V3.66).

La decisión de tarea del Planner 3.0 deja de ser efímera: cada carta servida en
la cola de repaso léxico se registra como una fila append-only con la evidencia
y la política que gobernaron su `p_success`. Es el PROVENANCE que V3.65 dejó
pendiente (P3): permite reconstruir `decision_id`, fingerprints de evidencia y de
estado, candidatas puntuadas y drivers, sin mezclarse con la evidencia de alumno.

Solo escribe: no hay lectura de negocio todavía (la auditoría la relee en bruto).
Nunca lanza hacia el llamador (el escritor es best-effort desde la cola).
"""

from __future__ import annotations

import json
import uuid
from contextlib import closing

from repositories.db import _conn, _now
from repositories.users import get_user

# Versión DECLARADA de la política de resolución de `p_success` (V3.66).
# `task_empirical` → `skill_empirical` → `margin`.
DECISION_POLICY_VERSION = "v3.66.0"


def record_decision(
    user_id: str,
    *,
    target_id: str = "",
    evidence_fingerprint: str = "",
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
    """Registra UNA decisión de tarea servida (append-only; best-effort).

    `candidates` son las alternativas puntuadas (`decision.alternatives`) y
    `drivers` los drivers proyectados del eje elegido. Ambos se serializan como
    JSON determinista. Devuelve la fila o `None` si el usuario no existe.
    """
    if get_user(user_id) is None:
        return None
    now = _now()
    decision_id = uuid.uuid4().hex
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
    with closing(_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO decision_records "
            "(user_id, decision_id, created_at, target_id, evidence_fingerprint, "
            "decision_start_fingerprint, state_fingerprint, policy_version, "
            "selected_skill, selected_activity, selected_reason, p_success, "
            "p_success_source, expected_learning_value, candidates_json, "
            "drivers_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                decision_id,
                now,
                str(target_id or ""),
                str(evidence_fingerprint or ""),
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
        "target_id": str(target_id or ""),
        "created_at": now,
        "policy_version": DECISION_POLICY_VERSION,
    }
