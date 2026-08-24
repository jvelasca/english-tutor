"""Tests de services/mastery: clasificación de errores e hitos."""
from services.mastery import classify_errors, compute_milestones


def test_classify_errors_active_vs_resolved():
    now = "2026-08-24T10:00:00+00:00"
    errors = [
        {
            "rule": "a",
            "message": "m1",
            "count": 1,
            "last_example": "",
            "last_seen": "2026-08-20T10:00:00+00:00",
        },
        {
            "rule": "b",
            "message": "m2",
            "count": 1,
            "last_example": "",
            "last_seen": "2026-06-01T10:00:00+00:00",
        },
    ]
    result = classify_errors(errors, now)
    assert [e["rule"] for e in result["active"]] == ["a"]
    assert [e["rule"] for e in result["resolved"]] == ["b"]


def test_classify_errors_empty():
    assert classify_errors([], "2026-08-24T10:00:00+00:00") == {
        "active": [],
        "resolved": [],
    }


def test_classify_errors_mastered_is_resolved():
    now = "2026-08-24T10:00:00+00:00"
    errors = [
        {
            "rule": "a",
            "message": "m1",
            "count": 1,
            "last_example": "",
            "last_seen": "2026-08-20T10:00:00+00:00",
            "mastered": True,
        },
        {
            "rule": "b",
            "message": "m2",
            "count": 1,
            "last_example": "",
            "last_seen": "2026-08-20T10:00:00+00:00",
            "mastered": False,
        },
    ]
    result = classify_errors(errors, now)
    assert [e["rule"] for e in result["resolved"]] == ["a"]
    assert [e["rule"] for e in result["active"]] == ["b"]


def test_compute_milestones_flags():
    none = compute_milestones(
        {
            "messages": 0,
            "conversations": 0,
            "pronunciation": 0,
            "vocab_size": 0,
            "streak_best": 0,
        }
    )
    states = {m["id"]: m["achieved"] for m in none}
    assert len(none) == 10
    assert states["first_message"] is False
    assert states["message_10"] is False
    assert states["streak_7"] is False

    all_achieved = compute_milestones(
        {
            "messages": 60,
            "conversations": 1,
            "pronunciation": 12,
            "vocab_size": 250,
            "streak_best": 8,
        }
    )
    states2 = {m["id"]: m["achieved"] for m in all_achieved}
    assert states2["first_conversation"] is True
    assert states2["first_message"] is True
    assert states2["message_10"] is True
    assert states2["message_50"] is True
    assert states2["pronunciation_1"] is True
    assert states2["pronunciation_10"] is True
    assert states2["vocab_50"] is True
    assert states2["vocab_200"] is True
    assert states2["streak_3"] is True
    assert states2["streak_7"] is True
