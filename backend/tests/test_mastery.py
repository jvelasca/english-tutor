"""Tests de services/mastery: clasificación de errores, hitos y MasteryRecord."""
from services.mastery import (
    MASTERY_SKILLS,
    MasteryRecord,
    classify_errors,
    compute_milestones,
    mastery_records,
    mastery_stage,
    review_interval_days,
)


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


# --- MasteryRecord transversal -------------------------------------------


def test_mastery_records_returns_nine_skills_in_order():
    records = mastery_records([], now="2026-08-31T00:00:00+00:00")
    assert [r.skill for r in records] == list(MASTERY_SKILLS)
    assert len(records) == 9
    # Sin datos: todo en acquire y sin puntuación.
    assert all(r.stage == "acquire" for r in records)
    assert all(r.score == 0.0 for r in records)
    assert all(r.review_in_days is None for r in records)


def test_review_interval_days_increases_with_strength():
    weak = review_interval_days(0.2, 0.2)
    strong = review_interval_days(0.9, 0.9)
    assert weak < strong
    # Acotado a enteros positivos.
    assert weak >= 1
    assert strong >= 1


def test_mastery_stage_timeline():
    assert mastery_stage(0, 0, 0, False) == "acquire"
    assert mastery_stage(2, 0, 0, False) == "practice"
    assert mastery_stage(5, 0, 0, True) == "retrieve"
    assert mastery_stage(5, 2, 0, False) == "transfer"
    assert mastery_stage(5, 0, 2, False) == "retention"
    assert mastery_stage(5, 2, 2, True) == "retention"  # novel domina


def test_mastery_records_from_profile_annotates_review_and_stage():
    now = "2026-08-31T00:00:00+00:00"
    profile = [
        {
            "skill": "grammar",
            "score": 0.5,
            "confidence": 0.8,
            "evidence_count": 2,
            "last_evidence": "2026-08-01T00:00:00+00:00",
            "evidence_by_kind": {"familiar": 2, "transfer": 0, "novel": 0},
        },
        {
            "skill": "listening",
            "score": 0.9,
            "confidence": 0.9,
            "evidence_count": 6,
            "last_evidence": "2026-08-30T00:00:00+00:00",
            "evidence_by_kind": {"familiar": 4, "transfer": 1, "novel": 1},
        },
    ]
    records = mastery_records(profile, now=now)
    by_skill = {r.skill: r for r in records}

    grammar = by_skill["grammar"]
    assert isinstance(grammar, MasteryRecord)
    assert grammar.evidence_count == 2
    assert grammar.review_in_days is not None
    # Evidencia antigua + score medio => cae a repaso y a retrieve.
    assert grammar.review_due is True
    assert grammar.stage == "retrieve"

    listening = by_skill["listening"]
    assert listening.novel_count == 1
    assert listening.transfer_count == 1
    assert listening.stage == "retention"
    assert listening.review_due is False

    # Las destrezas sin datos siguen presentes (transversal, 9 registros).
    assert by_skill["interaction"].stage == "acquire"
    assert by_skill["mediation"].stage == "acquire"
