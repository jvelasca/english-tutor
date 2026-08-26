"""Tests del currículo B1 (cierre de A1→B1, re-scope de V1.8)."""

from services.curriculum import (
    CANONICAL_SKILLS,
    SUBSKILLS,
    available_level_ids,
    load_level,
    next_level_id,
    validate_level,
)


def test_b1_loads_and_validates():
    lv = load_level("b1")
    assert lv.level == "B1"
    assert lv.modules, "B1 debe tener módulos"
    assert len(lv.objectives()) >= 6
    assert validate_level(lv) == []


def test_b1_objectives_have_canonical_skills_and_can_do():
    lv = load_level("b1")
    for o in lv.objectives():
        assert o.can_do.startswith("I can "), o.id
        assert o.skills, o.id
        assert set(o.skills) <= set(CANONICAL_SKILLS), o.id


def test_b1_subskills_belong_to_declared_skills():
    lv = load_level("b1")
    objectives_with_subskills = [o for o in lv.objectives() if o.subskills]
    assert objectives_with_subskills, "B1 declara subskills en algunos objetivos"
    for o in objectives_with_subskills:
        for subskill in o.subskills:
            assert any(
                subskill in SUBSKILLS.get(skill, ()) for skill in o.skills
            ), (o.id, subskill)


def test_b1_checks_have_valid_correct_index():
    lv = load_level("b1")
    for o in lv.objectives():
        for check in o.checks:
            assert 0 <= check.correct_index < len(check.options), (
                o.id,
                check.id,
            )


def test_available_levels_are_a1_a2_b1_b2():
    assert available_level_ids() == ["a1", "a2", "b1", "b2"]


def test_next_level_id_b1_points_to_b2():
    # B2 ya tiene archivo: el siguiente nivel tras B1 es b2.
    assert next_level_id("B1") == "b2"
    assert next_level_id("C2") is None
