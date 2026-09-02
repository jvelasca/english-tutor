"""Golden tests del scheduler FSRS-lite (auditoría E).

Las historias de review de `tests/golden/fsrs/sequences.json` fijan propiedades
cualitativas del scheduling: el intervalo no es "Good → +7 fijo" sino que crece
con la historia de aciertos, un lapse reinicia y permite recuperación, Easy
programa bastante más lejos que Hard, y el scheduler es hoy uniforme entre tipos
de memoria (skill/lexicon) — comportamiento documentado, no cambiado en V3.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from golden import loader

from services import fsrs

_GRADE = {label: value for value, label in fsrs.GRADE_LABELS.items()}


def _now(t0: str, day: float) -> str:
    base = datetime.fromisoformat(t0)
    return (base + timedelta(days=day)).isoformat()


def _simulate(
    t0: str, target_type: str, target_id: str, steps: list[dict]
) -> list[dict]:
    card = fsrs.empty_card(
        target_type=target_type, target_id=target_id, now=t0
    )
    history: list[dict] = []
    for step in steps:
        now = _now(t0, step["at_day"])
        card = fsrs.schedule(card, _GRADE[step["grade"]], now=now)
        interval = fsrs.days_between(card["last_review_at"], card["due_at"])
        history.append(
            {
                "state": card["state"],
                "stability": float(card["stability"]),
                "difficulty": float(card["difficulty"]),
                "reps": int(card["reps"]),
                "lapses": int(card["lapses"]),
                "due_at": card["due_at"],
                "interval_days": interval,
            }
        )
    return history


def test_good_reviews_grow_stability_and_interval():
    fixture = loader.load_json("fsrs/sequences")
    seq = next(s for s in fixture["sequences"] if s["id"] == "good-x4-grows")
    hist = _simulate(fixture["t0"], seq["target_type"], seq["target_id"], seq["steps"])

    final = hist[-1]
    assert final["reps"] == seq["expect"]["final_reps"]
    assert final["lapses"] == seq["expect"]["final_lapses"]
    assert final["state"] == seq["expect"]["final_state"]

    if seq["expect"].get("monotonic_stability"):
        stabilities = [h["stability"] for h in hist]
        assert all(
            b > a for a, b in zip(stabilities, stabilities[1:], strict=False)
        ), stabilities
    if seq["expect"].get("monotonic_interval"):
        intervals = [h["interval_days"] for h in hist]
        assert all(
            b > a for a, b in zip(intervals, intervals[1:], strict=False)
        ), intervals


def test_lapse_and_recovery():
    fixture = loader.load_json("fsrs/sequences")
    seq = next(
        s for s in fixture["sequences"] if s["id"] == "good-then-lapse-then-recovery"
    )
    hist = _simulate(fixture["t0"], seq["target_type"], seq["target_id"], seq["steps"])

    final = hist[-1]
    assert final["reps"] == seq["expect"]["final_reps"]
    assert final["lapses"] == seq["expect"]["final_lapses"]
    assert final["state"] == seq["expect"]["final_state"]
    if seq["expect"].get("lapse_lowers_stability"):
        assert hist[1]["stability"] < hist[0]["stability"]
    if seq["expect"].get("recovery_raises_stability"):
        assert hist[2]["stability"] > hist[1]["stability"]


def test_easy_schedules_much_farther_than_hard():
    fixture = loader.load_json("fsrs/sequences")
    seq = next(
        s for s in fixture["sequences"] if s["id"] == "easy-vs-hard-after-first-good"
    )
    t0 = fixture["t0"]
    cards = {}
    for grade in ("hard", "easy"):
        card = fsrs.empty_card(
            target_type=seq["target_type"],
            target_id=f"{seq['target_id']}-{grade}",
            now=t0,
        )
        card = fsrs.schedule(card, _GRADE[seq["first_grade"]], now=t0)
        cards[grade] = fsrs.schedule(
            card, _GRADE[grade], now=_now(t0, seq["second_day"])
        )
    hard_days = fsrs.days_between(
        cards["hard"]["last_review_at"], cards["hard"]["due_at"]
    )
    easy_days = fsrs.days_between(
        cards["easy"]["last_review_at"], cards["easy"]["due_at"]
    )
    assert hard_days < easy_days


def test_new_card_state_transitions():
    fixture = loader.load_json("fsrs/sequences")
    seq = next(
        s for s in fixture["sequences"] if s["id"] == "new-card-grade-transitions"
    )
    t0 = fixture["t0"]
    good = fsrs.schedule(
        fsrs.empty_card(target_type=seq["target_type"], target_id="good-card", now=t0),
        _GRADE["good"],
        now=t0,
    )
    again = fsrs.schedule(
        fsrs.empty_card(target_type=seq["target_type"], target_id="again-card", now=t0),
        _GRADE["again"],
        now=t0,
    )
    assert good["state"] == seq["new_good_state"]
    assert again["state"] == seq["new_again_state"]
    assert again["state"] != good["state"]


def test_scheduler_is_uniform_across_memory_types():
    """Documenta la uniformidad actual: misma historia → mismo resultado para
    skill y lexicon. (Recomendación de diferenciación, aparcada en PARKED.md.)"""
    fixture = loader.load_json("fsrs/sequences")
    seq = next(
        s for s in fixture["sequences"] if s["id"] == "memory-type-uniformity"
    )
    results = {}
    for target_type in seq["expect"]["types_identical"]:
        hist = _simulate(
            fixture["t0"],
            target_type,
            f"target-{target_type}",
            seq["steps"],
        )
        results[target_type] = hist[-1]
    a, b = results[seq["expect"]["types_identical"][0]], results[
        seq["expect"]["types_identical"][1]
    ]
    for key in ("stability", "difficulty", "reps", "lapses", "state", "due_at"):
        assert a[key] == b[key], f"{key}: {a[key]} != {b[key]}"
