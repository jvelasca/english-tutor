"""Tests de services/trends: agregación temporal y racha."""
from services.trends import (
    aggregate_series,
    compute_streak,
    daily_activity,
)


def _event(day: str, kind: str, mode: str | None = None) -> dict:
    return {"created_at": f"{day}T10:00:00+00:00", "kind": kind, "mode": mode}


def _row(
    day: str,
    messages: int = 0,
    exercises: int = 0,
    corrections: int = 0,
    pronunciation: int = 0,
) -> dict:
    return {
        "day": day,
        "messages": messages,
        "exercises": exercises,
        "corrections": corrections,
        "pronunciation": pronunciation,
    }


def test_daily_activity_counts_modes():
    events = [
        _event("2026-08-10", "message", "exercises"),
        _event("2026-08-10", "message", "grammar"),
        _event("2026-08-10", "message", "conversation"),
        _event("2026-08-10", "pronunciation"),
        _event("2026-08-11", "message", "grammar"),
    ]
    rows = daily_activity(events)
    assert len(rows) == 2

    day10 = rows[0]
    assert day10["day"] == "2026-08-10"
    assert day10["messages"] == 3
    assert day10["exercises"] == 1
    assert day10["corrections"] == 1
    assert day10["pronunciation"] == 1

    day11 = rows[1]
    assert day11["day"] == "2026-08-11"
    assert day11["messages"] == 1
    assert day11["exercises"] == 0
    assert day11["corrections"] == 1
    assert day11["pronunciation"] == 0


def test_aggregate_series_day():
    daily = [
        _row("2026-08-10", messages=1, pronunciation=2),
        _row("2026-08-11", messages=2, exercises=1),
    ]
    series = aggregate_series(daily, "day")
    assert len(series) == 2
    assert series[0]["bucket"] == "2026-08-10"
    assert series[0]["pronunciation"] == 2
    assert series[1]["bucket"] == "2026-08-11"
    assert series[1]["messages"] == 2


def test_aggregate_series_week():
    daily = [
        _row("2026-08-10", messages=1),
        _row("2026-08-12", messages=2, exercises=1),
        _row("2026-08-17", messages=5, corrections=1),
    ]
    series = aggregate_series(daily, "week")
    assert len(series) == 2
    assert series[0]["messages"] == 3
    assert series[0]["exercises"] == 1
    assert series[1]["messages"] == 5
    assert series[1]["corrections"] == 1
    assert series[0]["bucket"] != series[1]["bucket"]


def test_aggregate_series_month():
    daily = [
        _row("2026-08-10", messages=1),
        _row("2026-08-11", messages=2),
        _row("2026-09-01", messages=4, exercises=1),
    ]
    series = aggregate_series(daily, "month")
    assert len(series) == 2
    assert series[0]["bucket"] == "2026-08"
    assert series[0]["messages"] == 3
    assert series[1]["bucket"] == "2026-09"
    assert series[1]["messages"] == 4
    assert series[1]["exercises"] == 1


def test_compute_streak_empty():
    assert compute_streak([]) == {
        "current_days": 0,
        "best_days": 0,
        "last_active_date": None,
    }


def test_compute_streak_best_and_current():
    days = ["2026-08-10", "2026-08-11", "2026-08-12"]
    result = compute_streak(days)
    assert result["current_days"] == 3
    assert result["best_days"] == 3
    assert result["last_active_date"] == "2026-08-12"


def test_compute_streak_gap_resets_run():
    days = ["2026-08-10", "2026-08-11", "2026-08-13", "2026-08-14"]
    result = compute_streak(days)
    assert result["current_days"] == 2
    assert result["best_days"] == 2
    assert result["last_active_date"] == "2026-08-14"
