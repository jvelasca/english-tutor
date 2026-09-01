"""Tests del wiring curso↔bancos (V2.5-C4).

Protegen la relación por ID entre el contenido del curso (`listening_items` /
`scenario_ids` en los objetivos) y los bancos de destrezas:
- el conteo de `unit_sections` refleja las referencias;
- `validate_level` detecta referencias rotas y desfases de nivel;
- tras el wiring, ningún nivel con curso tiene listening/speaking `empty`.
"""
from services import course as course_svc
from services.curriculum import (
    Lesson,
    Level,
    Module,
    Objective,
    Unit,
    load_level,
    validate_level,
)
from services.curriculum_coverage import EMPTY, level_coverage

COURSE_LEVELS = ("a1", "a2", "b1", "b2", "c1", "c2")


def _minimal_level(level: str, objective: Objective) -> Level:
    return Level(
        course_id="test",
        level_id=level.lower(),
        level=level,
        title="Test",
        modules=[
            Module(
                id="m1",
                title="M1",
                order=1,
                units=[
                    Unit(
                        id="u1",
                        title="U1",
                        order=1,
                        lessons=[
                            Lesson(
                                id="l1",
                                title="L1",
                                order=1,
                                objectives=[objective],
                            )
                        ],
                    )
                ],
            )
        ],
    )


# --- Conteo -----------------------------------------------------------------

def test_unit_sections_sums_bank_references():
    # En A1 (con wiring completo), listening/speaking deben sumar las referencias
    # por ID a los bancos, además de los objetivos/checks declarados.
    level = load_level("a1")
    for module in level.modules:
        for unit in module.units:
            objs = [o for les in unit.lessons for o in les.objectives]
            refs_listening = sum(len(o.listening_items) for o in objs)
            refs_speaking = sum(len(o.scenario_ids) for o in objs)
            declared_listening = sum(1 for o in objs if "listening" in o.skills) + sum(
                1 for o in objs for c in o.checks if c.skill == "listening"
            )
            declared_speaking = sum(1 for o in objs if "speaking" in o.skills) + sum(
                1 for o in objs for c in o.checks if c.skill == "speaking"
            )
            sections = {
                s["section"]: s["count"]
                for s in course_svc.unit_sections(level, unit)
            }
            assert sections["listening"] == declared_listening + refs_listening
            assert sections["speaking"] == declared_speaking + refs_speaking


# --- Validación de integridad de referencias --------------------------------

def test_validator_detects_broken_listening_reference():
    obj = Objective(id="o1", can_do="c", title="t", skills=["listening"],
                    listening_items=["c999"])
    errors = validate_level(_minimal_level("A1", obj))
    assert any("c999" in e and "no existe" in e for e in errors)


def test_validator_detects_listening_level_mismatch():
    # `l1` es A1; referenciarlo desde un nivel A2 debe fallar.
    obj = Objective(id="o1", can_do="c", title="t", skills=["listening"],
                    listening_items=["l1"])
    errors = validate_level(_minimal_level("A2", obj))
    assert any("l1" in e and "A1" in e and "A2" in e for e in errors)


def test_validator_detects_broken_scenario_reference():
    obj = Objective(id="o1", can_do="c", title="t", skills=["speaking"],
                    scenario_ids=["s999"])
    errors = validate_level(_minimal_level("A1", obj))
    assert any("s999" in e and "no existe" in e for e in errors)


def test_validator_detects_scenario_level_mismatch():
    # `restaurant` tiene cefr_target A2; referenciarlo desde A1 debe fallar.
    obj = Objective(id="o1", can_do="c", title="t", skills=["speaking"],
                    scenario_ids=["restaurant"])
    errors = validate_level(_minimal_level("A1", obj))
    assert any("restaurant" in e and "A2" in e for e in errors)


# --- Invariantes tras el wiring --------------------------------------------

def test_no_course_level_has_empty_listening_speaking():
    # V2.5-C4: los bancos están cableados a las unidades, así que ningún nivel
    # con curso queda con listening/speaking `empty`.
    for level_id in COURSE_LEVELS:
        by_section = {s["section"]: s for s in level_coverage(level_id)["sections"]}
        for section in ("listening", "speaking"):
            assert by_section[section]["status"] != EMPTY, f"{level_id} {section} empty"


def test_validate_level_empty_for_wired_levels():
    for level_id in COURSE_LEVELS:
        assert validate_level(load_level(level_id)) == [], f"{level_id} con issues"
