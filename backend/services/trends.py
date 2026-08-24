"""Agregación temporal de la actividad del alumno (puro, determinista)."""
from __future__ import annotations

from datetime import datetime

_KEYS = ("messages", "exercises", "corrections", "pronunciation")


def _day(iso_ts: str) -> str:
    # _now() genera ISO UTC; los 10 primeros caracteres son YYYY-MM-DD.
    return iso_ts[:10]


def active_days(events: list[dict]) -> list[str]:
    """Días con actividad (YYYY-MM-DD), sin duplicados, orden asc."""
    return sorted({_day(e["created_at"]) for e in events})


def daily_activity(events: list[dict]) -> list[dict]:
    """Agrega eventos en una fila por día. Un evento es {created_at, kind, mode}
    con kind en {"message","pronunciation"}."""
    agg: dict[str, dict] = {}
    for e in events:
        day = _day(e["created_at"])
        row = agg.setdefault(
            day,
            {
                "day": day,
                "messages": 0,
                "exercises": 0,
                "corrections": 0,
                "pronunciation": 0,
            },
        )
        if e["kind"] == "pronunciation":
            row["pronunciation"] += 1
        else:
            row["messages"] += 1
            if e.get("mode") == "exercises":
                row["exercises"] += 1
            elif e.get("mode") == "grammar":
                row["corrections"] += 1
    return [agg[d] for d in sorted(agg)]


def _week_key(day: str) -> str:
    iso = datetime.fromisoformat(day).isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _month_key(day: str) -> str:
    return day[:7]


def aggregate_series(daily: list[dict], bucket: str) -> list[dict]:
    """Reagrupa filas diarias en buckets day|week|month (orden ascendente)."""
    if bucket == "day":
        return [{"bucket": r["day"], **{k: r[k] for k in _KEYS}} for r in daily]
    key_fn = _week_key if bucket == "week" else _month_key
    agg: dict[str, dict] = {}
    order: list[str] = []
    for r in daily:
        key = key_fn(r["day"])
        if key not in agg:
            agg[key] = {"bucket": key, "messages": 0, "exercises": 0,
                        "corrections": 0, "pronunciation": 0}
            order.append(key)
        for k in _KEYS:
            agg[key][k] += r[k]
    return [agg[k] for k in order]


def compute_streak(active_days: list[str]) -> dict:
    """Racha: días consecutivos con actividad. current = racha que termina en el
    último día activo; best = racha más larga del histórico."""
    days = sorted(set(active_days))
    if not days:
        return {"current_days": 0, "best_days": 0, "last_active_date": None}

    def consecutive(a: str, b: str) -> bool:
        return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).days == 1

    best = 1
    run = 1
    for i in range(1, len(days)):
        if consecutive(days[i - 1], days[i]):
            run += 1
        else:
            run = 1
        best = max(best, run)

    current = 1
    i = len(days) - 1
    while i > 0 and consecutive(days[i - 1], days[i]):
        current += 1
        i -= 1

    return {"current_days": current, "best_days": best, "last_active_date": days[-1]}
