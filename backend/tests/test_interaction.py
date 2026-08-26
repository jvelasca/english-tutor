"""Tests del módulo puro de evidencia objetiva de interacción (Interaction 2.0)."""

from services.interaction import (
    INTERRUPTION_LATENCY_MS,
    TURN_COMPLETION_FULL_MS,
    TURN_COMPLETION_MIN_MS,
    interaction_evidence,
)


def _turn(role, duration_ms=None, latency_ms=None):
    return {"role": role, "duration_ms": duration_ms, "latency_ms": latency_ms}


def test_empty_turns_all_unobservable():
    ev = interaction_evidence([])
    assert ev["turn_balance"] is None
    assert ev["avg_response_latency_ms"] is None
    assert ev["turn_completion"] is None
    assert ev["student_turns"] == 0
    assert ev["assistant_turns"] == 0
    assert ev["interruptions"] is None


def test_counts_student_and_assistant():
    turns = [
        _turn("student", 1000, 500),
        _turn("assistant", 2000, 300),
        _turn("student", 1500, 700),
    ]
    ev = interaction_evidence(turns)
    assert ev["student_turns"] == 2
    assert ev["assistant_turns"] == 1


def test_turn_balance_perfect_is_one():
    ev = interaction_evidence(
        [_turn("student"), _turn("assistant"), _turn("student"), _turn("assistant")]
    )
    assert ev["turn_balance"] == 1.0


def test_turn_balance_imbalanced_lower():
    ev = interaction_evidence(
        [_turn("student"), _turn("student"), _turn("student"), _turn("assistant")]
    )
    # proporción de alumno 0.75 → 1 - 2·0.25 = 0.5.
    assert ev["turn_balance"] == 0.5


def test_turn_balance_unobservable_without_exchange():
    assert interaction_evidence([_turn("student"), _turn("student")])[
        "turn_balance"
    ] is None
    assert interaction_evidence([_turn("assistant")])["turn_balance"] is None


def test_avg_response_latency_ms():
    ev = interaction_evidence(
        [_turn("student", latency_ms=500), _turn("assistant", latency_ms=300)]
    )
    assert ev["avg_response_latency_ms"] == 400


def test_avg_response_latency_ms_none_without_data():
    ev = interaction_evidence([_turn("student"), _turn("assistant")])
    assert ev["avg_response_latency_ms"] is None


def test_turn_completion_ramp():
    # duración mínima → 0.0; completa → 1.0; punto medio → 0.5.
    assert (
        interaction_evidence(
            [_turn("student", duration_ms=TURN_COMPLETION_MIN_MS), _turn("assistant")]
        )["turn_completion"]
        == 0.0
    )
    assert (
        interaction_evidence(
            [_turn("student", duration_ms=TURN_COMPLETION_FULL_MS), _turn("assistant")]
        )["turn_completion"]
        == 1.0
    )
    mid = (TURN_COMPLETION_MIN_MS + TURN_COMPLETION_FULL_MS) / 2
    assert (
        interaction_evidence(
            [_turn("student", duration_ms=mid), _turn("assistant")]
        )["turn_completion"]
        == 0.5
    )


def test_turn_completion_averages_student_durations():
    turns = [
        _turn("student", duration_ms=1000),
        _turn("assistant", duration_ms=9999),  # el turno del tutor no cuenta
        _turn("student", duration_ms=3000),
    ]
    ev = interaction_evidence(turns)
    # media 2000 ms → (2000 - 500) / 3500 = 0.4286 → 0.429.
    assert ev["turn_completion"] == 0.429


def test_turn_completion_unobservable_without_student_duration():
    ev = interaction_evidence([_turn("student"), _turn("assistant", duration_ms=1000)])
    assert ev["turn_completion"] is None


def test_interruptions_counts_low_latency_student():
    turns = [
        _turn("student", latency_ms=100),  # < umbral → interrupción
        _turn("assistant", latency_ms=500),
        _turn("student", latency_ms=1000),
    ]
    assert interaction_evidence(turns)["interruptions"] == 1


def test_interruptions_zero_when_latency_observed():
    turns = [_turn("student", latency_ms=1000), _turn("assistant", latency_ms=500)]
    assert interaction_evidence(turns)["interruptions"] == 0


def test_interruptions_unobservable_without_student_latency():
    ev = interaction_evidence([_turn("student"), _turn("assistant", latency_ms=500)])
    assert ev["interruptions"] is None


def test_interruption_threshold_constant_is_positive():
    assert INTERRUPTION_LATENCY_MS > 0
    assert TURN_COMPLETION_MIN_MS < TURN_COMPLETION_FULL_MS
