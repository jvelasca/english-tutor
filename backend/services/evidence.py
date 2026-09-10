"""Modelo de evidencia LONGITUDINAL (V3.35, Longitudinal Learning Evidence 1.0).

El motor de recall de V3.34 sabía responder "¿puede el alumno recuperar una
palabra?", pero medía la retención con repeticiones ancladas a la PRIMERA
exposición. Eso confunde volumen con historia: cuatro aciertos seguidos en días
consecutivos parecían cuatro recuperaciones demoradas cuando el intervalo real
era de un día entre ellos.

Este módulo puro (sin I/O ni FastAPI) define la capa que faltaba:

    evento_1 → intervalo_1 → evento_2 → intervalo_2 → evento_3 → ...

Cada intento es un EVENTO con su propio intervalo (`interval_since_last_evidence`)
y su propio rol (`event_role`). Con eso:

- los INTENTOS se separan de los ÉXITOS (`attempts` vs `successes`): un fallo es
  evidencia (negativa) y no un evento inexistente;
- los ÉXITOS se separan de los DÍAS distintos (`distinct_success_days`): acertar
  dos veces el mismo día no duplica la evidencia temporal;
- los INTERVALOS se conservan (`intervals`): la historia fina que el scheduler
  necesita para programar el siguiente repaso.

`event_role` evita que `learning_events` siga mezclando señales heterogéneas:
una pregunta de Recognition (informativa, no demuestra destrezas productivas) no
es lo mismo que una recuperación de Recall (evidencia) ni que un log de
telemetría.

Puro y determinista: recibe filas ya agregadas o construidas por el repositorio.
"""

from __future__ import annotations

from datetime import datetime, timezone

# Roles del ledger de eventos (V3.35). `evidence` = señal que puede acreditar
# aprendizaje; `informative` = señal que informa pero no acredita (p. ej. el MCQ
# de Recognition, V3.13); `telemetry` = traza operativa sin valor pedagógico.
EVIDENCE_ROLES: tuple[str, ...] = ("evidence", "telemetry", "informative")

# Resultados de un intento de micro-drill. `unclear` no es ni acierto ni fallo:
# el ASR no reconoció el audio (V3.21, V20-14/V20-15), así que no se penaliza.
_DRILL_OUTCOMES = frozenset({"ok", "ko", "unclear"})

# Campos de una fila de `learning_evidence` (documentación del contrato).
EVIDENCE_FIELDS: tuple[str, ...] = (
    "occurred_at",
    "skill",
    "target_type",
    "target_id",
    "surface_form",
    "lexical_unit",
    "task",
    "activity",
    "success",
    "interval_since_last_evidence",
    "event_role",
)


def _truthy(value: object) -> bool:
    """Normaliza un booleano que puede llegar como int de SQLite."""
    if isinstance(value, str):
        return value not in ("", "0", "False", "false")
    return bool(value)


def _parse_iso(value: str) -> datetime | None:
    """`datetime` UTC de una marca ISO-8601 (None si vacía o inválida)."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def interval_days(previous_at: str, now: str) -> float | None:
    """Días transcurridos entre dos marcas ISO (None si falta alguna).

    Es el `interval_since_last_evidence` de un evento: el hueco REAL desde la
    evidencia anterior del mismo ítem, no desde el primer contacto con él. Sin
    evidencia previa no hay intervalo (None), y esa ausencia es información: es
    la primera observación de la cadena longitudinal.
    """
    previous = _parse_iso(previous_at)
    current = _parse_iso(now)
    if previous is None or current is None:
        return None
    return round(max(0.0, (current - previous).total_seconds() / 86400.0), 4)


def classify_event_role(event_type: str, detail: str) -> str:
    """Rol de un evento de `learning_events` (evidence/telemetry/informative).

    Reglas deterministas por (tipo, detalle):

    - `drill:<word>:recognition:<ok|ko>` → `informative`: el MCQ de
      reconocimiento no demuestra destrezas productivas (V3.13) y por eso nunca
      acredita nada, aunque siempre se registre.
    - `drill:<word>:recall:<ok|ko>` → `evidence`: recuperar la forma desde el
      significado SÍ es una señal de recuperación real (V3.34).
    - `drill:<word>[:sentence]:<ok|ko>` → `evidence`: la recuperación del
      micro-drill (palabra o frase) acredita retención si supera el intervalo.
    - `drill:*:unclear` → `telemetry`: el ASR no reconoció el audio, no hubo ni
      acierto ni fallo (no se penaliza al alumno).
    - Cualquier otro evento → `telemetry`.
    """
    event_type = (event_type or "").strip()
    detail = (detail or "").strip()
    if event_type != "exercise" or not detail.startswith("drill:"):
        return "telemetry"
    parts = detail[len("drill:") :].split(":")
    outcome = parts[-1] if parts else ""
    if outcome not in _DRILL_OUTCOMES:
        return "telemetry"
    if outcome == "unclear":
        return "telemetry"
    if len(parts) >= 2 and parts[-2] == "recognition":
        return "informative"
    return "evidence"


def summarize_evidence(rows: list[dict]) -> dict:
    """Resumen longitudinal de una lista de filas de `learning_evidence`.

    Devuelve:

    - `attempts` — nº de eventos (incluye fallos);
    - `successes` — nº de eventos con `success` verdadero;
    - `distinct_success_days` — días naturales distintos con éxito (dos aciertos
      el mismo día cuentan una sola vez, igual que `recall_days`);
    - `intervals` — intervalos (en días) de los eventos CON éxito, ascendentes.
      Es la historia que el scheduler puede leer como cadena de repasos.

    Nunca lanza: una fila incompleta se cuenta como intento sin éxito.
    """
    attempts = 0
    successes = 0
    days: set[str] = set()
    intervals: list[float] = []
    for row in rows:
        attempts += 1
        if not _truthy(row.get("success")):
            continue
        successes += 1
        day = (row.get("occurred_at") or "")[:10]
        if day:
            days.add(day)
        raw = row.get("interval_since_last_evidence")
        if raw is None:
            continue
        try:
            intervals.append(round(float(raw), 4))
        except (TypeError, ValueError):
            continue
    intervals.sort()
    return {
        "attempts": attempts,
        "successes": successes,
        "distinct_success_days": len(days),
        "intervals": intervals,
    }


def empty_summary() -> dict:
    """Resumen de evidencia de un ítem sin eventos (mismo contrato que
    `summarize_evidence`). Dict nuevo en cada llamada: nunca compartir estado."""
    return {
        "attempts": 0,
        "successes": 0,
        "distinct_success_days": 0,
        "intervals": [],
    }
