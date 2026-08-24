"""Dominio de errores recurrentes e hitos (puro, determinista)."""
from __future__ import annotations

from datetime import datetime

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
    """Separa errores recurrentes en activos (last_seen reciente) y resueltos
    (sin recurrencia reciente). Heurística v1, determinista."""
    now = datetime.fromisoformat(now_iso)
    active: list[dict] = []
    resolved: list[dict] = []
    for e in errors:
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
