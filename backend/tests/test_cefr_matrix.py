"""Tests de la matriz de assessment CEFR (puros, deterministas)."""

from services.cefr_matrix import load_matrix, requirements_for


def test_load_matrix_validates_json():
    matrix = load_matrix()
    assert matrix.version == "1.0.0"
    assert set(matrix.levels) == {"A1", "A2", "B1", "B2"}
    for level in matrix.levels.values():
        assert set(level.skills) == {"listening", "speaking", "reading", "writing"}


def test_requirements_for_b1_listening_transfer():
    req = requirements_for("B1", "listening")
    assert req is not None
    assert req.transfer_required == 1
    assert req.minimum_mastery == 0.70


def test_requirements_for_c1_returns_none():
    assert requirements_for("C1", "listening") is None


def test_requirements_for_grammar_returns_none():
    # grammar/vocabulary/pronunciation no están en la matriz: fallback plano.
    assert requirements_for("B1", "grammar") is None
