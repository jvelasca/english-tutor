"""Tests de la matriz de requisitos CEFR (puros, deterministas)."""

from services.cefr_matrix import load_matrix, requirements_for

# Las 8 destrezas de la Constitución §7 (pronunciation queda fuera: componente
# de Speaking con mínimo plano en `services/adaptive.READINESS_MINIMUMS`).
EXPECTED_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
EXPECTED_SKILLS = {
    "vocabulary",
    "grammar",
    "listening",
    "speaking",
    "interaction",
    "reading",
    "writing",
    "mediation",
}


def test_load_matrix_validates_json():
    matrix = load_matrix()
    assert matrix.version == "2.0.0"
    assert set(matrix.levels) == EXPECTED_LEVELS
    for level in matrix.levels.values():
        assert set(level.skills) == EXPECTED_SKILLS


def test_requirements_for_b1_listening_transfer():
    req = requirements_for("B1", "listening")
    assert req is not None
    assert req.transfer_required == 1
    assert req.minimum_mastery == 0.70


def test_requirements_for_c1_and_c2_are_declared():
    # C1/C2 ya no caen al fallback plano: la matriz llega hasta C2 (H4).
    c1 = requirements_for("C1", "listening")
    c2 = requirements_for("C2", "reading")
    assert c1 is not None
    assert c2 is not None
    assert c1.minimum_mastery == 0.80
    assert c2.minimum_mastery == 0.85
    assert c1.transfer_required == 3
    assert c2.novel_required == 3


def test_requirements_for_grammar_and_vocabulary_declared():
    # grammar/vocabulary/interaction/mediation entran en la matriz con su suelo
    # plano histórico (mismo valor que su fallback READINESS_MINIMUMS), de modo
    # que ninguna destreza de la Constitución §7 depende del fallback.
    for skill in ("grammar", "vocabulary", "interaction", "mediation"):
        for level in ("A1", "B2", "C2"):
            assert requirements_for(level, skill) is not None, (level, skill)
    assert requirements_for("B1", "grammar").minimum_mastery == 0.70


def test_requirements_for_pronunciation_remains_outside_matrix():
    # pronunciation no es una de las 8 destrezas (Constitución §7): su mínimo lo
    # fija READINESS_MINIMUMS (componente de Speaking), no la matriz.
    assert requirements_for("B1", "pronunciation") is None


def test_matrix_scales_with_level_for_macro_skills():
    # Las 4 macro-destrezas calibradas escalan de forma monótona A1→C2.
    for skill in ("listening", "reading"):
        values = [
            requirements_for(level, skill).minimum_mastery
            for level in ("A1", "A2", "B1", "B2", "C1", "C2")
        ]
        assert values == sorted(values), values
        assert values[-1] > values[0]
