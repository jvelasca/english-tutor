"""Tests unitarios del modelo de olvido y programación de repaso (V1.4)."""

from services import forgetting

NOW = "2026-08-01T00:00:00+00:00"


def test_stability_increases_with_score():
    assert forgetting.stability_days(1.0) > forgetting.stability_days(0.5)
    assert forgetting.stability_days(0.5) > forgetting.stability_days(0.0)
    assert forgetting.stability_days(0.0) == forgetting.STABILITY_MIN_DAYS


def test_days_since_positive_and_safe():
    assert (
        forgetting.days_since(
            "2026-08-01T00:00:00+00:00", "2026-08-03T00:00:00+00:00"
        )
        == 2.0
    )
    assert forgetting.days_since("", NOW) == 0.0
    assert forgetting.days_since("no-es-fecha", NOW) == 0.0


def test_retrieval_decays_over_time():
    last = "2026-01-01T00:00:00+00:00"
    near = forgetting.retrieval_probability(0.9, last, "2026-01-02T00:00:00+00:00")
    far = forgetting.retrieval_probability(0.9, last, "2026-08-01T00:00:00+00:00")
    assert near > far


def test_review_due_after_enough_time():
    last = "2026-01-01T00:00:00+00:00"
    assert forgetting.review_due(0.9, last, "2026-08-01T00:00:00+00:00") is True
    assert forgetting.review_due(0.9, last, "2026-01-01T00:00:01+00:00") is False


def test_review_due_without_timestamp_falls_back_to_score():
    assert forgetting.review_due(0.5, "", NOW) is True
    assert forgetting.review_due(0.9, "", NOW) is False
