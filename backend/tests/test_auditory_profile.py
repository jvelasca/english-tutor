"""V3.27 (Listening Engine 4.0): perfil auditivo (services.auditory_profile).
Casos A-D de la especificación §5, precedencia, mínimos de muestra y perfil
vacío cuando no hay evidencia."""
from services.auditory_profile import (
    COND_HIGH,
    COND_LOW,
    HIGH,
    INF_LOW,
    PROFILE_MIN_ATTEMPTS,
    R_LOW,
    auditory_profile,
    intervention_label,
)


def _layer(layer: str, accuracy: float, attempts: int = PROFILE_MIN_ATTEMPTS) -> dict:
    return {
        "layer": layer,
        "attempts": attempts,
        "correct": round(attempts * accuracy / 100),
        "accuracy": float(accuracy),
    }


def _res(dimension: str, accuracy: float, attempts: int = PROFILE_MIN_ATTEMPTS) -> dict:
    return {
        "dimension": dimension,
        "attempts": attempts,
        "correct": round(attempts * accuracy / 100),
        "accuracy": float(accuracy),
    }


def _diagnostic(
    layers: list[dict] | None = None, res: list[dict] | None = None
) -> dict:
    return {
        "by_layer": layers or [],
        "resilience": {"dimensions": res or []},
        "subskills": [],
    }


def test_empty_diagnostic_needs_min_attempts():
    profile = auditory_profile(_diagnostic())
    assert profile["intervention"] is None
    assert profile["layer"] is None
    assert profile["needs_min_attempts"] is True


def test_too_little_evidence_needs_min_attempts():
    diag = _diagnostic(
        layers=[_layer("recognition", 50.0, attempts=PROFILE_MIN_ATTEMPTS - 1)],
        res=[_res("clear_speech", 90.0, attempts=PROFILE_MIN_ATTEMPTS - 1)],
    )
    profile = auditory_profile(diag)
    assert profile["intervention"] is None
    assert profile["needs_min_attempts"] is True


def test_case_a_bottom_up():
    diag = _diagnostic(
        layers=[
            _layer("recognition", R_LOW - 15),
            _layer("comprehension", HIGH + 5),
            _layer("inference", HIGH),
        ],
        res=[_res("clear_speech", COND_HIGH - 10)],
    )
    profile = auditory_profile(diag)
    assert profile["layer"] == "recognition"
    assert profile["intervention"] == "bottom_up_path"
    assert profile["reason"] == "recognition"
    assert profile["needs_min_attempts"] is False


def test_case_b_comprehension():
    diag = _diagnostic(
        layers=[
            _layer("recognition", HIGH + 5),
            _layer("comprehension", R_LOW - 15),
            _layer("inference", HIGH),
        ],
        res=[_res("clear_speech", COND_HIGH - 10)],
    )
    profile = auditory_profile(diag)
    assert profile["layer"] == "comprehension"
    assert profile["intervention"] == "comprehension_path"


def test_case_c_top_down():
    diag = _diagnostic(
        layers=[
            _layer("recognition", HIGH),
            _layer("comprehension", HIGH + 2),
            _layer("inference", INF_LOW - 10),
        ],
        res=[_res("clear_speech", COND_HIGH - 10)],
    )
    profile = auditory_profile(diag)
    assert profile["layer"] == "inference"
    assert profile["intervention"] == "top_down_path"


def test_case_d_connected_speech_wins_over_a():
    """Precedencia D: condición acústica se detecta aunque recognition sea débil."""
    diag = _diagnostic(
        layers=[
            _layer("recognition", R_LOW - 15),  # dispararía el caso A
            _layer("comprehension", HIGH + 5),
            _layer("inference", HIGH),
        ],
        res=[
            _res("clear_speech", COND_HIGH + 5),
            _res("connected_speech", COND_LOW - 20),
        ],
    )
    profile = auditory_profile(diag)
    assert profile["layer"] is None
    assert profile["intervention"] == "connected_speech_path"
    assert profile["reason"] == "connected_speech"


def test_case_d_natural_speech_fallback():
    """Sin evidencia en connected_speech pero sí en natural_speech: igual caso D."""
    diag = _diagnostic(
        layers=[_layer("recognition", HIGH), _layer("comprehension", HIGH)],
        res=[
            _res("clear_speech", COND_HIGH + 5),
            _res("natural_speech", COND_LOW - 10),
        ],
    )
    profile = auditory_profile(diag)
    assert profile["intervention"] == "connected_speech_path"
    assert profile["reason"] == "natural_speech"


def test_balanced_strong_profile_has_no_intervention():
    diag = _diagnostic(
        layers=[
            _layer("recognition", HIGH + 5),
            _layer("comprehension", HIGH + 5),
            _layer("inference", HIGH),
        ],
        res=[_res("clear_speech", COND_HIGH + 5)],
    )
    profile = auditory_profile(diag)
    assert profile["intervention"] is None
    assert profile["needs_min_attempts"] is False


def test_intervention_label_maps_to_i18n_key():
    assert intervention_label("bottom_up_path") == (
        "listening.profile.intervention.bottom_up_path"
    )
    assert intervention_label("") == "listening.profile.intervention.none"
