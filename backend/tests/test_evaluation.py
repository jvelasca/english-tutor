"""Tests del evaluador objetivo del tutor (services/evaluation.py)."""
from services.evaluation import (
    EVAL_CASES,
    conciseness_score,
    contains_fragment,
    engagement_score,
    english_word_ratio,
    evaluate_tutor_reply,
    normalize,
    spanish_word_ratio,
    summarize,
)


def test_normalize_lowers_and_strips():
    assert "hello" in normalize("Hello, World!")
    assert "world" in normalize("Hello, World!")
    assert normalize("Doesn't") == "doesn t"


def test_contains_fragment_true():
    assert contains_fragment("We say 'I am twenty years old'.", "am twenty")


def test_contains_fragment_false():
    assert not contains_fragment("I have twenty years old.", "am twenty")


def test_spanish_word_ratio_detects_spanish():
    assert spanish_word_ratio("Está muy bien, gracias.") > 0.5


def test_english_word_ratio_all_english():
    assert english_word_ratio("We say I am twenty years old.") == 1.0


def test_conciseness_ideal():
    assert conciseness_score(50) == 100


def test_conciseness_short():
    assert conciseness_score(5) == 50


def test_conciseness_long():
    assert conciseness_score(500) == 40


def test_engagement_question():
    assert engagement_score("Good! How old are you?") == 100


def test_engagement_marker():
    assert engagement_score("Great work, keep going.") == 70


def test_engagement_none():
    assert engagement_score("Just a statement.") == 0


def test_evaluate_good_reply():
    case = EVAL_CASES[0]
    r = evaluate_tutor_reply(
        "We say 'I am twenty years old'. How old are you?", case
    )
    assert r["correction"] == 100
    assert r["english"] == 100
    assert r["engagement"] == 100
    assert r["total"] >= 80


def test_evaluate_bad_reply():
    case = EVAL_CASES[0]
    r = evaluate_tutor_reply(
        "Muy bien, la frase está bien escrita. Gracias.", case
    )
    assert r["correction"] == 0
    assert r["english"] < 50


def test_evaluate_without_case():
    r = evaluate_tutor_reply("Nice work! Keep going.")
    assert "correction" not in r
    assert "case_id" not in r
    assert r["english"] == 100


def test_summarize_averages():
    results = [
        {
            "case_id": "a",
            "correction": 100,
            "english": 100,
            "conciseness": 100,
            "engagement": 100,
            "total": 100,
        },
        {
            "case_id": "b",
            "correction": 0,
            "english": 60,
            "conciseness": 60,
            "engagement": 0,
            "total": 40,
        },
    ]
    s = summarize(results)
    assert s["cases"] == 2
    assert s["avg_total"] == 70.0
    assert s["avg_correction"] == 50.0
    assert s["avg_english"] == 80.0


def test_summarize_empty():
    s = summarize([])
    assert s["cases"] == 0
    assert s["avg_total"] is None
