"""Tests de la matriz de requisitos CEFR (puros, deterministas).

F-C2 (V3.26 / P2-03): calibración unificada de extremos. Las 4 destrezas de
soporte (`vocabulary`/`grammar`/`interaction`/`mediation`) conservan su suelo
histórico en A1/A2 y pasan a la escalera de `reading` desde B1: la matriz queda
monótona para las 8 destrezas y los extremos quedan unificados (C1/C2 exigen lo
mismo a una destreza de soporte que a una macro).
"""

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

# Escalera de `reading` (referencia de la calibración F-C2): las destrezas de
# soporte siguen esta fila desde B1, tras conservar su suelo histórico A1/A2.
READING_LADDER: dict[str, dict[str, float | int]] = {
    "B1": {
        "minimum_mastery": 0.70,
        "minimum_confidence": 0.60,
        "minimum_evidence": 3,
        "transfer_required": 1,
    },
    "B2": {
        "minimum_mastery": 0.75,
        "minimum_confidence": 0.65,
        "minimum_evidence": 4,
        "transfer_required": 2,
    },
    "C1": {
        "minimum_mastery": 0.80,
        "minimum_confidence": 0.70,
        "minimum_evidence": 5,
        "transfer_required": 3,
    },
    "C2": {
        "minimum_mastery": 0.85,
        "minimum_confidence": 0.75,
        "minimum_evidence": 6,
        "transfer_required": 4,
    },
}

# Suelo histórico de las destrezas de soporte (se mantiene en A1/A2).
SUPPORT_FLOOR: dict[str, float | int] = {
    "minimum_mastery": 0.70,
    "minimum_confidence": 0.60,
    "minimum_evidence": 3,
    "transfer_required": 0,
}


def test_load_matrix_validates_json():
    matrix = load_matrix()
    assert matrix.version == "2.1.0"
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
    # F-K1 (V3.24): `novel` queda reservado sin emisor → exigencia 0 en C2.
    assert c2.novel_required == 0


def test_requirements_for_grammar_and_vocabulary_declared():
    # grammar/vocabulary/interaction/mediation entran en la matriz con su suelo
    # plano histórico, de modo que ninguna destreza de la Constitución §7
    # depende del fallback.
    for skill in ("grammar", "vocabulary", "interaction", "mediation"):
        for level in ("A1", "B2", "C2"):
            assert requirements_for(level, skill) is not None, (level, skill)
    assert requirements_for("B1", "grammar").minimum_mastery == 0.70


def test_requirements_for_pronunciation_remains_outside_matrix():
    # pronunciation no es una de las 8 destrezas (Constitución §7): su mínimo lo
    # fija READINESS_MINIMUMS (componente de Speaking), no la matriz.
    assert requirements_for("B1", "pronunciation") is None


def test_matrix_scales_with_level_for_all_skills():
    # F-C2 (V3.26): las 8 destrezas escalan de forma monótona A1→C2 (antes solo
    # las 4 macro). La calibración deja de ser plana en los extremos.
    for skill in EXPECTED_SKILLS:
        values = [
            requirements_for(level, skill).minimum_mastery
            for level in ("A1", "A2", "B1", "B2", "C1", "C2")
        ]
        assert values == sorted(values), f"{skill}: {values}"
        assert values[-1] > values[0], f"{skill}: sin techo por encima del suelo"


def test_support_skills_follow_reading_from_b1():
    """F-C2: las destrezas de soporte conservan su suelo histórico en A1/A2 y
    adoptan la escalera de `reading` desde B1 (extremos unificados)."""
    for skill in ("vocabulary", "grammar", "interaction", "mediation"):
        for level in ("A1", "A2"):
            req = requirements_for(level, skill)
            assert req.minimum_mastery == SUPPORT_FLOOR["minimum_mastery"]
            assert req.minimum_confidence == SUPPORT_FLOOR["minimum_confidence"]
            assert req.minimum_evidence == SUPPORT_FLOOR["minimum_evidence"]
            assert req.transfer_required == SUPPORT_FLOOR["transfer_required"]
        for level, expected in READING_LADDER.items():
            req = requirements_for(level, skill)
            assert req.minimum_mastery == expected["minimum_mastery"]
            assert req.minimum_confidence == expected["minimum_confidence"]
            assert req.minimum_evidence == expected["minimum_evidence"]
            assert req.transfer_required == expected["transfer_required"]


def test_extremes_unified_across_all_skills():
    """F-C2: los extremos quedan unificados POR FAMILIA y ninguna destreza queda
    plana. Las destrezas de soporte adoptan el techo calibrado de reading
    (C2: 0.85/0.75/6/4; C1: 0.80/0.70/5/3); speaking/writing conservan su techo
    propio de la escalera macro (0.80 en C2). Lo que F-C2 elimina es la banda
    plana A1-C2 de las 4 destrezas de soporte."""
    for skill in ("vocabulary", "grammar", "interaction", "mediation"):
        req_c2 = requirements_for("C2", skill)
        req_c1 = requirements_for("C1", skill)
        # Techo idéntico al de reading (extremo unificado con la macro receptiva).
        reading_c2 = requirements_for("C2", "reading")
        assert req_c2.minimum_mastery == reading_c2.minimum_mastery
        assert req_c2.minimum_confidence == reading_c2.minimum_confidence
        assert req_c2.minimum_evidence == reading_c2.minimum_evidence
        assert req_c2.transfer_required == reading_c2.transfer_required
        # Escalera completa declarada (no cae al fallback plano en ningún nivel).
        assert req_c1.minimum_mastery == 0.80
        assert req_c1.transfer_required == 3
        assert req_c2.minimum_mastery == 0.85
        assert req_c2.transfer_required == 4
        assert req_c2.minimum_mastery > requirements_for("A1", skill).minimum_mastery
    # Las macro-destrezas conservan su propia calibración (speaking/writing 0.80).
    assert requirements_for("C2", "speaking").minimum_mastery == 0.80
    assert requirements_for("C2", "writing").minimum_mastery == 0.80
