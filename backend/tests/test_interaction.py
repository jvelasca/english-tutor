"""Tests del módulo puro de evidencia objetiva de interacción (Interaction 2.0)."""

from services.interaction import (
    INTERRUPTION_LATENCY_MS,
    TURN_DURATION_FULL_MS,
    TURN_DURATION_MIN_MS,
    _turn_duration_score,
    interaction_evidence,
)


def _turn(role, duration_ms=None, latency_ms=None):
    return {"role": role, "duration_ms": duration_ms, "latency_ms": latency_ms}


def test_empty_turns_all_unobservable():
    ev = interaction_evidence([])
    assert ev["turn_balance"] is None
    assert ev["avg_response_latency_ms"] is None
    assert ev["turn_duration"] is None
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


def test_turn_balance_within_plateau_is_one():
    # 40% y 60% de turnos del alumno están dentro de la meseta [0.30, 0.70] → 1.0.
    ev_40 = interaction_evidence(
        [
            _turn("student"),
            _turn("student"),
            _turn("assistant"),
            _turn("assistant"),
            _turn("assistant"),
        ]
    )
    assert ev_40["turn_balance"] == 1.0
    ev_60 = interaction_evidence(
        [
            _turn("student"),
            _turn("student"),
            _turn("student"),
            _turn("assistant"),
            _turn("assistant"),
        ]
    )
    assert ev_60["turn_balance"] == 1.0


def test_turn_balance_imbalanced_lower():
    # 10% de turnos del alumno → 0.1 / 0.3 (tramo bajo de la meseta).
    ev = interaction_evidence(
        [_turn("student")] + [_turn("assistant") for _ in range(9)]
    )
    assert ev["turn_balance"] == round(0.1 / 0.3, 3)


def test_turn_balance_imbalanced_high():
    # 90% de turnos del alumno → (1 - 0.9) / (1 - 0.7) (tramo alto).
    ev = interaction_evidence(
        [_turn("student") for _ in range(9)] + [_turn("assistant")]
    )
    assert ev["turn_balance"] == round((1.0 - 0.9) / (1.0 - 0.7), 3)


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


def test_turn_duration_score_thresholds():
    # 500ms → 0.0; 4000ms → 1.0; el mapeo de duración se mantiene intacto.
    assert _turn_duration_score(TURN_DURATION_MIN_MS) == 0.0
    assert _turn_duration_score(TURN_DURATION_FULL_MS) == 1.0
    mid = (TURN_DURATION_MIN_MS + TURN_DURATION_FULL_MS) / 2
    assert _turn_duration_score(mid) == 0.5


def test_turn_duration_ramp():
    # duración mínima → 0.0; plena → 1.0; punto medio → 0.5.
    assert (
        interaction_evidence(
            [_turn("student", duration_ms=TURN_DURATION_MIN_MS), _turn("assistant")]
        )["turn_duration"]
        == 0.0
    )
    assert (
        interaction_evidence(
            [_turn("student", duration_ms=TURN_DURATION_FULL_MS), _turn("assistant")]
        )["turn_duration"]
        == 1.0
    )
    mid = (TURN_DURATION_MIN_MS + TURN_DURATION_FULL_MS) / 2
    assert (
        interaction_evidence(
            [_turn("student", duration_ms=mid), _turn("assistant")]
        )["turn_duration"]
        == 0.5
    )


def test_turn_duration_averages_student_durations():
    turns = [
        _turn("student", duration_ms=1000),
        _turn("assistant", duration_ms=9999),  # el turno del tutor no cuenta
        _turn("student", duration_ms=3000),
    ]
    ev = interaction_evidence(turns)
    # media 2000 ms → (2000 - 500) / 3500 = 0.4286 → 0.429.
    assert ev["turn_duration"] == 0.429


def test_turn_duration_unobservable_without_student_duration():
    ev = interaction_evidence([_turn("student"), _turn("assistant", duration_ms=1000)])
    assert ev["turn_duration"] is None


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
    assert TURN_DURATION_MIN_MS < TURN_DURATION_FULL_MS
