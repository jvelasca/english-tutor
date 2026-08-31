"""Dominio de errores recurrentes, hitos y MasteryRecord transversal (determinista).

Además de los errores recurrentes y los hitos, este módulo alberga la abstracción
común de dominio (`MasteryRecord`) con la que el Adaptive Engine observa TODAS las
destrezas (vocabulary/grammar/pronunciation/listening/speaking/reading/writing/
interaction/mediation) de forma homogénea, y conecta la curva de olvido
(`services.forgetting`) a todo el currículo con un timeline
acquire→practice→retrieve→transfer→novel→retention y "review in N days".
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from services import forgetting

RESOLVED_AFTER_DAYS = 14

_MILESTONES = [
    ("first_conversation", "Primera conversación"),
    ("first_message", "Primer mensaje"),
    ("message_10", "10 mensajes"),
    ("message_50", "50 mensajes"),
    ("pronunciation_1", "Primera pronunciación"),
    ("pronunciation_10", "10 pronunciaciones"),
    ("vocab_50", "50 palabras de vocabulario"),
    ("vocab_200", "200 palabras de vocabulario"),
    ("streak_3", "Racha de 3 días"),
    ("streak_7", "Racha de 7 días"),
]


def classify_errors(
    errors: list[dict], now_iso: str, resolved_after_days: int = RESOLVED_AFTER_DAYS
) -> dict:
    """Separa errores recurrentes en activos y resueltos. Un error está resuelto si
    está marcado como `mastered` (evidencia positiva) o si no recurre desde hace más
    de `resolved_after_days`. Heurística v1, determinista."""
    now = datetime.fromisoformat(now_iso)
    active: list[dict] = []
    resolved: list[dict] = []
    for e in errors:
        if e.get("mastered"):
            resolved.append(e)
            continue
        try:
            last = datetime.fromisoformat(e["last_seen"])
        except (KeyError, ValueError):
            active.append(e)
            continue
        if (now - last).days <= resolved_after_days:
            active.append(e)
        else:
            resolved.append(e)
    return {"active": active, "resolved": resolved}


def compute_milestones(signals: dict) -> list[dict]:
    """Devuelve el catálogo completo de hitos con su estado achieved según
    señales: messages, conversations, pronunciation, vocab_size, streak_best."""
    checks = {
        "first_conversation": signals.get("conversations", 0) >= 1,
        "first_message": signals.get("messages", 0) >= 1,
        "message_10": signals.get("messages", 0) >= 10,
        "message_50": signals.get("messages", 0) >= 50,
        "pronunciation_1": signals.get("pronunciation", 0) >= 1,
        "pronunciation_10": signals.get("pronunciation", 0) >= 10,
        "vocab_50": signals.get("vocab_size", 0) >= 50,
        "vocab_200": signals.get("vocab_size", 0) >= 200,
        "streak_3": signals.get("streak_best", 0) >= 3,
        "streak_7": signals.get("streak_best", 0) >= 7,
    }
    return [
        {"id": mid, "label": label, "achieved": checks[mid]}
        for mid, label in _MILESTONES
    ]


# --- MasteryRecord transversal (una sola abstracción de dominio) ----------

# Todas las destrezas que el Adaptive Engine observa de forma homogénea:
# las 7 canónicas + interacción y mediación (dimensiones CEFR comunicativas).
MASTERY_SKILLS: tuple[str, ...] = (
    "vocabulary",
    "grammar",
    "pronunciation",
    "listening",
    "speaking",
    "reading",
    "writing",
    "interaction",
    "mediation",
)

# Límite superior del intervalo de repaso (días), para no espaciar en exceso.
MAX_REVIEW_INTERVAL_DAYS = 30


def review_interval_days(score: float, confidence: float) -> int:
    """Días hasta el próximo repaso (escala SRS corta).

    Combina dominio y consistencia en una "fuerza" (0..1) y la convierte a días
    con la estabilidad de la curva de olvido (`stability_days`): a más dominio
    mantenido, más se espacia el repaso (p. ej. ~2 días para lo débil, ~10+ para
    lo consolidado). Determinista y acotado a [1, MAX_REVIEW_INTERVAL_DAYS].
    """
    s = max(0.0, min(1.0, score))
    c = max(0.0, min(1.0, confidence))
    strength = 0.7 * s + 0.3 * c
    days = int(round(forgetting.stability_days(strength)))
    return max(1, min(MAX_REVIEW_INTERVAL_DAYS, days))


def mastery_stage(
    evidence_count: int, transfer_count: int, novel_count: int, review_due: bool
) -> str:
    """Etapa del timeline de dominio.

    acquire → practice → retrieve → transfer → novel → retention. La evidencia de
    novedad confirma dominio generalizado (retention); la de transferencia queda en
    transfer; si toca repasar (curva de olvido) la etapa es retrieve; con poca
    evidencia es practice; y sin evidencia, acquire.
    """
    if evidence_count == 0:
        return "acquire"
    if novel_count > 0:
        return "retention"
    if transfer_count > 0:
        return "transfer"
    if review_due:
        return "retrieve"
    if evidence_count < 3:
        return "practice"
    return "retention"


class MasteryRecord(BaseModel):
    """Vista transversal de dominio de UNA destreza.

    Es la abstracción común para las 9 destrezas: el Adaptive Engine (y la UI)
    leen esta forma homogénea en lugar de conocer 8 motores distintos. Incluye el
    mastery (`score`), la consistencia (`confidence`), el volumen de evidencia,
    la retención/estabilidad de la curva de olvido, el estado de repaso
    (`review_due` + `review_in_days`) y la etapa del timeline.
    """

    skill: str
    score: float = 0.0
    confidence: float = 0.0
    evidence_count: int = 0
    last_seen_at: str = ""
    retention: float = 0.0
    stability: float = 0.0
    review_due: bool = False
    review_in_days: int | None = None
    transfer_count: int = 0
    novel_count: int = 0
    stage: str = "acquire"


def _record_from_entry(skill: str, entry: dict | None, now: str) -> MasteryRecord:
    """Construye el `MasteryRecord` de una destreza desde su entrada del perfil
    CEFR anotado (o una destreza sin datos)."""
    if entry is None:
        return MasteryRecord(skill=skill, stage="acquire")

    score = float(entry.get("score", 0.0))
    confidence = float(entry.get("confidence", 0.0))
    evidence_count = int(entry.get("evidence_count", 0))
    last_seen = entry.get("last_evidence", "") or entry.get("last_seen_at", "")
    by_kind = entry.get("evidence_by_kind") or {}
    transfer_count = int(by_kind.get("transfer", 0))
    novel_count = int(by_kind.get("novel", 0))

    # `retrieval_probability` devuelve el score cuando no hay timestamp de última
    # evidencia (sin olvido observable).
    retention = forgetting.retrieval_probability(score, last_seen, now)
    due = forgetting.review_due(score, last_seen, now)

    return MasteryRecord(
        skill=skill,
        score=round(score, 3),
        confidence=round(confidence, 3),
        evidence_count=evidence_count,
        last_seen_at=last_seen,
        retention=round(retention, 3),
        stability=round(confidence * retention, 3),
        review_due=due,
        review_in_days=(
            review_interval_days(score, confidence) if evidence_count > 0 else None
        ),
        transfer_count=transfer_count,
        novel_count=novel_count,
        stage=mastery_stage(evidence_count, transfer_count, novel_count, due),
    )


def mastery_records(skill_profile: list[dict], now: str = "") -> list[MasteryRecord]:
    """Vista transversal del dominio sobre TODO el currículo.

    Devuelve un `MasteryRecord` por cada destreza de `MASTERY_SKILLS` (siempre las
    9, ordenadas), de modo que el Adaptive Engine observa un conjunto homogéneo y
    completo aunque una destreza aún no tenga evidencia (aparece en `acquire`).
    """
    by_skill = {entry.get("skill"): entry for entry in skill_profile}
    return [
        _record_from_entry(skill, by_skill.get(skill), now)
        for skill in MASTERY_SKILLS
    ]
