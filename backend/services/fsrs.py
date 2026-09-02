"""FSRS-lite — scheduler de retención (V2.11).

Scheduler tipo FSRS (Free Spaced Repetition Scheduler) sobre el Evidence Model.
No calibra los 19 pesos de FSRS-5; usa una formulación determinista y auditable
alineada con FSRS-4.5 (retrievability + stability + difficulty + grades 1..4).

El scheduler responde las preguntas de la auditoría:

    What?          → target (skill / lexicon / objective)
    Why?           → razón pedagógica (olvido, weak, retention due…)
    When?          → due_at
    How strong?    → stability + retrievability
    Last evidence? → last_evidence_at / last_review_at
    Next evidence? → next_due (intervalo)

Puro: sin FastAPI ni BD.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

FSRS_VERSION = "2.11.0-lite"

# Grades FSRS: Again / Hard / Good / Easy
GRADE_AGAIN = 1
GRADE_HARD = 2
GRADE_GOOD = 3
GRADE_EASY = 4
GRADES: tuple[int, ...] = (GRADE_AGAIN, GRADE_HARD, GRADE_GOOD, GRADE_EASY)
GRADE_LABELS: dict[int, str] = {
    GRADE_AGAIN: "again",
    GRADE_HARD: "hard",
    GRADE_GOOD: "good",
    GRADE_EASY: "easy",
}

STATES: tuple[str, ...] = ("new", "learning", "review", "relearning")

TARGET_TYPES: tuple[str, ...] = ("skill", "lexicon", "objective")

# Parámetros FSRS-4.5 (retrievability). FACTOR = 19/81, DECAY = -0.5.
FSRS_FACTOR = 19.0 / 81.0
FSRS_DECAY = -0.5
REQUEST_RETENTION = 0.9
MAX_INTERVAL_DAYS = 365.0
MIN_STABILITY = 0.1

# Estabilidad inicial tras la primera revisión (días), por grade.
INITIAL_STABILITY: dict[int, float] = {
    GRADE_AGAIN: 0.4,
    GRADE_HARD: 1.2,
    GRADE_GOOD: 3.0,
    GRADE_EASY: 7.0,
}

# Dificultad inicial (1..10): más grade → más fácil (menor D).
INITIAL_DIFFICULTY: dict[int, float] = {
    GRADE_AGAIN: 7.0,
    GRADE_HARD: 6.0,
    GRADE_GOOD: 5.0,
    GRADE_EASY: 4.0,
}

# Umbral de retrievability bajo el cual una carta entra en la cola due.
DUE_RETRIEVABILITY = 0.9


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def grade_from_score(score: float) -> int:
    """Mapea un score 0..1 a grade FSRS 1..4 (determinista)."""
    s = _clamp(float(score), 0.0, 1.0)
    if s < 0.5:
        return GRADE_AGAIN
    if s < 0.7:
        return GRADE_HARD
    if s < 0.9:
        return GRADE_GOOD
    return GRADE_EASY


def retrievability(stability: float, elapsed_days: float) -> float:
    """R(t) FSRS-4.5: (1 + FACTOR·t/S)^DECAY."""
    s = max(MIN_STABILITY, float(stability))
    t = max(0.0, float(elapsed_days))
    if t <= 0.0:
        return 1.0
    return round((1.0 + FSRS_FACTOR * t / s) ** FSRS_DECAY, 4)


def interval_for_stability(
    stability: float, *, retention: float = REQUEST_RETENTION
) -> float:
    """Días hasta que R caiga a `retention` (inversa de retrievability)."""
    s = max(MIN_STABILITY, float(stability))
    r = _clamp(float(retention), 0.01, 0.99)
    # R = (1 + F*t/S)^D  →  t = S/F * (R^(1/D) - 1)
    days = s / FSRS_FACTOR * (r ** (1.0 / FSRS_DECAY) - 1.0)
    return round(_clamp(days, 0.0, MAX_INTERVAL_DAYS), 3)


def days_between(start: str, end: str) -> float:
    a = _parse_iso(start)
    b = _parse_iso(end)
    if a is None or b is None:
        return 0.0
    return max(0.0, (b - a).total_seconds() / 86400.0)


def empty_card(
    *,
    target_type: str,
    target_id: str,
    label: str = "",
    why: str = "new",
    now: str = "",
) -> dict:
    """Carta nueva (sin revisiones)."""
    if target_type not in TARGET_TYPES:
        raise ValueError(f"target_type desconocido: {target_type}")
    now_iso = now or _iso(datetime.now(timezone.utc))
    return {
        "target_type": target_type,
        "target_id": target_id,
        "label": label or target_id,
        "state": "new",
        "difficulty": 5.0,
        "stability": MIN_STABILITY,
        "reps": 0,
        "lapses": 0,
        "due_at": now_iso,
        "last_review_at": "",
        "last_evidence_at": "",
        "last_grade": None,
        "why": why,
        "fsrs_version": FSRS_VERSION,
    }


def seed_card_from_evidence(
    *,
    target_type: str,
    target_id: str,
    label: str,
    score: float,
    last_evidence_at: str = "",
    why: str = "evidence",
    now: str = "",
) -> dict:
    """Siembra una carta a partir de evidencia existente (sin grade explícito)."""
    grade = grade_from_score(score)
    now_iso = now or _iso(datetime.now(timezone.utc))
    card = empty_card(
        target_type=target_type,
        target_id=target_id,
        label=label,
        why=why,
        now=now_iso,
    )
    # Primera revisión implícita con el grade derivado del score.
    return schedule(card, grade, now=last_evidence_at or now_iso, why=why)


def next_difficulty(difficulty: float, grade: int) -> float:
    """Actualiza D (1..10): Again endurece, Easy facilita."""
    d = _clamp(float(difficulty), 1.0, 10.0)
    delta = {GRADE_AGAIN: 1.2, GRADE_HARD: 0.3, GRADE_GOOD: -0.2, GRADE_EASY: -0.8}
    return round(_clamp(d + delta.get(grade, 0.0), 1.0, 10.0), 3)


def next_stability(
    stability: float,
    difficulty: float,
    retriev: float,
    grade: int,
    *,
    reps: int,
) -> float:
    """Actualiza S según grade (crecimiento/decay tipo FSRS, sin 19 pesos)."""
    s = max(MIN_STABILITY, float(stability))
    d = _clamp(float(difficulty), 1.0, 10.0)
    r = _clamp(float(retriev), 0.01, 1.0)

    if grade == GRADE_AGAIN:
        # Lapse: estabilidad cae fuerte (relearning).
        return round(max(MIN_STABILITY, s * 0.25 * r), 3)

    # Factor de crecimiento: más fácil (D bajo) y mejor grade → más S.
    ease = (11.0 - d) / 10.0
    if grade == GRADE_HARD:
        mult = 1.15 + 0.25 * ease * r
    elif grade == GRADE_GOOD:
        mult = 1.6 + 0.7 * ease * r
    else:  # EASY
        mult = 2.2 + 1.1 * ease * r

    # Primeras reps crecen algo menos (learning → review).
    if reps < 2:
        mult = 0.85 * mult + 0.15
    return round(_clamp(s * mult, MIN_STABILITY, MAX_INTERVAL_DAYS), 3)


def schedule(
    card: dict,
    grade: int,
    *,
    now: str = "",
    why: str | None = None,
) -> dict:
    """Aplica un grade y devuelve la carta actualizada (nueva dict)."""
    if grade not in GRADES:
        raise ValueError(f"grade inválido: {grade}")
    now_iso = now or _iso(datetime.now(timezone.utc))
    now_dt = _parse_iso(now_iso) or datetime.now(timezone.utc)

    prev = dict(card)
    reps = int(prev.get("reps") or 0)
    lapses = int(prev.get("lapses") or 0)
    state = prev.get("state") or "new"
    difficulty = float(prev.get("difficulty") or 5.0)
    stability = float(prev.get("stability") or MIN_STABILITY)
    last_ref = prev.get("last_review_at") or prev.get("last_evidence_at") or ""
    elapsed = days_between(last_ref, now_iso) if last_ref else 0.0
    r = retrievability(stability, elapsed) if reps > 0 else 1.0

    if reps == 0 or state == "new":
        difficulty = INITIAL_DIFFICULTY[grade]
        stability = INITIAL_STABILITY[grade]
        new_state = "relearning" if grade == GRADE_AGAIN else "learning"
        if grade >= GRADE_GOOD:
            new_state = "review"
    else:
        difficulty = next_difficulty(difficulty, grade)
        stability = next_stability(
            stability, difficulty, r, grade, reps=reps
        )
        if grade == GRADE_AGAIN:
            lapses += 1
            new_state = "relearning"
        else:
            new_state = "review"

    interval = interval_for_stability(stability)
    if grade == GRADE_AGAIN:
        interval = min(interval, 0.5)
    elif grade == GRADE_HARD:
        interval = max(0.5, interval * 0.85)
    elif grade == GRADE_EASY:
        interval = min(MAX_INTERVAL_DAYS, interval * 1.3)

    due_dt = now_dt + timedelta(days=interval)
    return {
        "target_type": prev["target_type"],
        "target_id": prev["target_id"],
        "label": prev.get("label") or prev["target_id"],
        "state": new_state,
        "difficulty": round(difficulty, 3),
        "stability": round(stability, 3),
        "reps": reps + 1,
        "lapses": lapses,
        "due_at": _iso(due_dt),
        "last_review_at": now_iso,
        "last_evidence_at": now_iso,
        "last_grade": grade,
        "why": why if why is not None else prev.get("why") or "review",
        "fsrs_version": FSRS_VERSION,
    }


def explain(card: dict, *, now: str = "") -> dict:
    """Respuesta auditable: What / Why / When / How strong / Last / Next."""
    now_iso = now or _iso(datetime.now(timezone.utc))
    last = card.get("last_review_at") or card.get("last_evidence_at") or ""
    elapsed = days_between(last, now_iso) if last else 0.0
    stability = float(card.get("stability") or MIN_STABILITY)
    r = retrievability(stability, elapsed) if (card.get("reps") or 0) > 0 else 1.0
    due_at = card.get("due_at") or now_iso
    due = is_due(card, now=now_iso)
    next_in = days_between(now_iso, due_at)
    if next_in < 0:
        next_in = 0.0
    return {
        "what": {
            "target_type": card.get("target_type"),
            "target_id": card.get("target_id"),
            "label": card.get("label") or card.get("target_id"),
        },
        "why": card.get("why") or "scheduled",
        "when": {
            "due_at": due_at,
            "due": due,
            "next_in_days": round(next_in, 3),
        },
        "how_strong": {
            "stability": round(stability, 3),
            "retrievability": r,
            "difficulty": float(card.get("difficulty") or 5.0),
            "state": card.get("state") or "new",
            "reps": int(card.get("reps") or 0),
            "lapses": int(card.get("lapses") or 0),
        },
        "last_evidence": {
            "at": last or None,
            "grade": card.get("last_grade"),
            "grade_label": GRADE_LABELS.get(card.get("last_grade") or 0),
        },
        "next_evidence": {
            "due_at": due_at,
            "suggested_interval_days": round(
                interval_for_stability(stability), 3
            ),
        },
        "fsrs_version": FSRS_VERSION,
    }


def is_due(card: dict, *, now: str = "") -> bool:
    """True si la carta toca repasar ahora."""
    now_iso = now or _iso(datetime.now(timezone.utc))
    due_at = card.get("due_at") or ""
    if not due_at:
        return True
    now_dt = _parse_iso(now_iso)
    due_dt = _parse_iso(due_at)
    if now_dt is None or due_dt is None:
        return True
    return now_dt >= due_dt


def due_queue(cards: list[dict], *, now: str = "", limit: int = 20) -> list[dict]:
    """Cola de cartas due, ordenada por urgencia (menor retrievability primero)."""
    now_iso = now or _iso(datetime.now(timezone.utc))
    due = [c for c in cards if is_due(c, now=now_iso)]

    def urgency(card: dict) -> tuple:
        last = card.get("last_review_at") or card.get("last_evidence_at") or ""
        elapsed = days_between(last, now_iso) if last else 999.0
        r = (
            retrievability(float(card.get("stability") or MIN_STABILITY), elapsed)
            if (card.get("reps") or 0) > 0
            else 0.0
        )
        return (r, card.get("due_at") or "")

    due.sort(key=urgency)
    return due[: max(0, limit)]


def why_for_skill(entry: dict) -> str:
    """Razón pedagógica al sembrar una carta de destreza."""
    if entry.get("review_due"):
        return "forgetting-curve"
    score = float(entry.get("score") or 0.0)
    if score < 0.7:
        return "weak-skill"
    by_kind = entry.get("evidence_by_kind") or {}
    if int(by_kind.get("delayed", 0)) == 0:
        return "missing-delayed-evidence"
    return "maintenance"


def why_for_lexicon(status: str) -> str:
    if status == "weak":
        return "weak-lexicon"
    if status == "learning":
        return "learning-lexicon"
    if status == "known":
        return "recognition-only"
    return "lexicon-maintenance"
