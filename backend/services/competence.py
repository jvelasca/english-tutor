"""Registro por competencia con los 4 estados pedagógicos (Constitución §2.1).

Para cada destreza se responde a la pregunta "¿qué ha demostrado el alumno en su
nivel actual?", distinguiendo (Constitución pedagógica, sección 2.1 y 6):

- `not_started`  → sin evidencia consolidada en el nivel.
- `developing`   → con práctica/evidencia, pero el gate funcional aún no se cumple.
- `functional`   → gate funcional cumplido (dominio evidenciado en el nivel).
- `demonstrated` → functional + retención retardada estable.

Principios:
- Una destreza sin evidencia NUNCA se lee como banda CEFR por defecto
  (`estimated_band` = "—", hallazgo H7).
- "Demostrado" exige evidencia de retención (`delayed` en `academy_evidence` o
  retención retardada estable de la ruta de listening): la práctica reciente sola
  no demuestra nivel (premisa 21 de `docs/PREMISAS.md`; dossier H, H2-H5).
- Para listening, el estado de la ruta de práctica (`route_gate` + retención,
  ver `services.listening.route_competence`) se combina con la evidencia formal:
  superar la ruta del nivel actual eleva la competencia a FUNCTIONAL, y la
  retención retardada estable la eleva a DEMONSTRATED.

El módulo es puro y determinista; la proyección se construye en
`domain/profile.py` desde el Student Model.
"""
from __future__ import annotations

from services.adaptive import (
    READINESS_DEFAULT_MINIMUM,
    READINESS_MIN_CONFIDENCE,
    READINESS_MIN_EVIDENCE,
    READINESS_MINIMUMS,
)
from services.cefr import heuristic_band
from services.mastery import MASTERY_SKILLS

# Orden creciente de los 4 estados (para combinar formal + ruta).
STATE_ORDER = ("not_started", "developing", "functional", "demonstrated")


def _rank(state: str) -> int:
    return STATE_ORDER.index(state) if state in STATE_ORDER else 0


def _score_floor(skill: str) -> float:
    """Suelo de score por destreza para el gate funcional.

    Reutiliza los mínimos de readiness del Adaptive Engine (no inventa umbrales
    nuevos); `interaction`/`mediation` no tienen mínimo propio y usan el default.
    """
    return READINESS_MINIMUMS.get(skill, READINESS_DEFAULT_MINIMUM)


def estimated_band(entry: dict | None) -> str:
    """Banda heurística por destreza con coherencia Pre-A1 (H7).

    Sin evidencia consolidada devuelve "—" (sin señal), nunca "A1" por defecto.
    """
    if entry is None or int(entry.get("evidence_count", 0) or 0) == 0:
        return "—"
    return heuristic_band(entry.get("score"))


def competence_state(
    entry: dict | None,
    skill: str,
    level: str,
    route: dict | None = None,
) -> dict:
    """Estado de competencia de UNA destreza en `level` (nivel actual).

    `entry` es la entrada del Student Model de la destreza (o None si la destreza
    no aparece); `route` es la entrada de la ruta de práctica de listening para
    ese mismo nivel (si existe; ver `services.listening.route_competence`).

    Devuelve `{skill, level, state, demonstrated, estimated_band, score,
    confidence, evidence_count, gate}`. `gate` detalla los criterios que se
    cumplen (score/confianza/evidencia/repaso/retención); `state` es la lectura
    pedagógica (los 4 estados de la sección 2.1 de la Constitución).
    """
    evidence_count = int((entry or {}).get("evidence_count", 0) or 0)
    score = float((entry or {}).get("score", 0.0) or 0.0)
    confidence = float((entry or {}).get("confidence", 0.0) or 0.0)
    by_kind = (entry or {}).get("evidence_by_kind") or {}
    review_due = bool((entry or {}).get("review_due", False))
    delayed_count = int(by_kind.get("delayed", 0) or 0)

    floor = _score_floor(skill)
    score_ok = evidence_count > 0 and score >= floor
    evidence_ok = evidence_count >= READINESS_MIN_EVIDENCE
    confidence_ok = evidence_count > 0 and confidence >= READINESS_MIN_CONFIDENCE
    # Retención retardada estable: evidencia `delayed` formal o ruta DEMONSTRATED.
    route_demonstrated = route is not None and route.get("state") == "demonstrated"
    retention_ok = delayed_count > 0 or route_demonstrated

    formal_functional = (
        score_ok and evidence_ok and confidence_ok and not review_due
    )
    if evidence_count == 0:
        formal_state = "not_started"
    elif formal_functional:
        formal_state = "functional"
    else:
        formal_state = "developing"

    # La ruta de práctica (listening) eleva la competencia si la ha superado.
    route_state = (route or {}).get("state", "not_started")
    if route_state == "not_started":
        merged = formal_state
    else:
        merged = STATE_ORDER[max(_rank(formal_state), _rank(route_state))]

    # "Demostrado" solo se alcanza con retención; sin ella, como mucho FUNCTIONAL.
    if merged == "functional" and retention_ok:
        merged = "demonstrated"
    elif merged == "demonstrated" and not retention_ok:
        merged = "functional"

    return {
        "skill": skill,
        "level": level,
        "state": merged,
        "demonstrated": merged == "demonstrated",
        "estimated_band": estimated_band(entry),
        "score": round(score, 3),
        "confidence": round(confidence, 3),
        "evidence_count": evidence_count,
        "gate": {
            "score_ok": score_ok,
            "confidence_ok": confidence_ok,
            "evidence_ok": evidence_ok,
            "review_due": review_due,
            "retention_ok": retention_ok,
        },
    }


def competence_states(skills: list[dict], level: str) -> list[dict]:
    """Registro completo: un estado por cada destreza canónica (las 9).

    `skills` es el perfil CEFR por destreza del Student Model (puede no contener
    todas las destrezas; las ausentes quedan en `not_started`). Para listening,
    la entrada puede incluir `routes` (estado por ruta de práctica) con el que se
    combina el estado formal.
    """
    by_skill = {entry.get("skill"): entry for entry in skills}
    records: list[dict] = []
    for skill in MASTERY_SKILLS:
        entry = by_skill.get(skill)
        route = None
        if skill == "listening" and entry is not None:
            routes = entry.get("routes") or []
            route = next((r for r in routes if r.get("level") == level), None)
        records.append(competence_state(entry, skill, level, route=route))
    return records
