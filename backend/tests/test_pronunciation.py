from services.pronunciation import score_pronunciation


def test_exact_match_scores_100():
    r = score_pronunciation("Hello world", "Hello world")
    assert r["score"] == 100
    assert r["ok"] is True
    assert r["level"] == "good"


def test_ignores_case_and_punctuation():
    r = score_pronunciation("Hello, world!", "hello world")
    assert r["score"] == 100


def test_empty_heard_scores_zero():
    r = score_pronunciation("Hello", "")
    assert r["score"] == 0
    assert r["ok"] is False
    assert r["level"] == "needs_practice"


def test_partial_match_levels():
    r = score_pronunciation("I have twenty years old", "I am twenty years old")
    # ~ 90%+ similitud con una palabra distinta
    assert 50 <= r["score"] < 100


def test_phoneme_accuracy_proxy_field_present():
    r = score_pronunciation("Hello world", "Hello world")
    assert "phoneme_accuracy_proxy" in r
    assert r["phoneme_accuracy_proxy"] == 100
    assert r["pronunciation_source"] == "transcript"


def test_prosody_and_phoneme_breakdown_present():
    r = score_pronunciation("Hello world", "Hello world")
    assert "prosody_proxy" in r
    assert r["prosody_proxy"] == 100
    assert "phoneme_breakdown" in r
    assert r["phoneme_breakdown"]["total"] > 0
