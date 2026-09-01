"""Tests de la capa de medición curricular (V2.6).

Cubre las nuevas métricas que complementan `coverage_metric` (matriz nivel×sección):

- `unit_coverage`: cobertura por unidad (las 7 secciones de cada unidad).
- `depth_score`: CEFR DEPTH SCORE (0..100) con componentes ponderados auditables.
- `unit_detail`: drill-down LEVEL → UNIT → LESSON → OBJECTIVE.
- `curriculum_quality_report` + `quality_report_delta`: dashboard y delta before/after.

Los invariantes son mayoritariamente estructurales (no dependen del contenido) para
que añadir/ampliar contenido no rompa el instrumento. Hay dos invariantes de
snapshot intencionadamente frágiles que codifican hallazgos de la auditoría V2.6
y que se actualizan/eliminan cuando el contenido evolucione (p. ej. V2.7 C1/C2).
"""
import pytest

from services import course as course_svc
from services.curriculum import (
    Activity,
    Lesson,
    Level,
    Module,
    Objective,
    Unit,
    load_level,
)
from services.curriculum_coverage import (
    DEPTH_WEIGHTS,
    LEARNING_LOOP_PHASES,
    OBJECTIVE_DENSITY_TARGET,
    OBJECTIVE_VOLUME_TARGET,
    curriculum_quality_report,
    depth_score,
    loop_coverage,
    quality_report_delta,
    unit_coverage,
    unit_detail,
    unit_learning_loop,
)

COURSE_LEVELS = ("a1", "a2", "b1", "b2", "c1", "c2")


def _level_with_activity(phase: str) -> Level:
    """Nivel mínimo de una unidad con una única actividad etiquetada con `phase`."""
    activity = Activity(id="a1", type="dialogue", instruction="x", phase=phase)
    objective = Objective(
        id="o1", can_do="c", title="t", skills=["speaking"], activities=[activity]
    )
    return Level(
        course_id="t",
        level_id="a1",
        level="A1",
        title="T",
        modules=[
            Module(
                id="m1",
                title="M",
                order=1,
                units=[
                    Unit(
                        id="u1",
                        title="U",
                        order=1,
                        lessons=[
                            Lesson(
                                id="l1",
                                title="L",
                                order=1,
                                objectives=[objective],
                            )
                        ],
                    )
                ],
            )
        ],
    )


# --- UNIT COVERAGE ----------------------------------------------------------

def test_unit_coverage_reports_each_unit_with_7_sections():
    for level_id in COURSE_LEVELS:
        uc = unit_coverage(load_level(level_id))
        assert uc["total_units"] == len(uc["units"]) > 0
        for unit in uc["units"]:
            assert [s["section"] for s in unit["sections"]] == list(
                course_svc.UNIT_SECTIONS
            )
            populated = [s["section"] for s in unit["sections"] if s["populated"]]
            assert unit["covered_sections"] == len(populated)
            assert unit["missing"] == [
                s["section"] for s in unit["sections"] if not s["populated"]
            ]
            assert unit["coverage_pct"] == round(
                len(populated) / len(course_svc.UNIT_SECTIONS) * 100, 1
            )
            assert 0.0 <= unit["coverage_pct"] <= 100.0


def test_unit_coverage_by_section_is_consistent():
    for level_id in COURSE_LEVELS:
        uc = unit_coverage(load_level(level_id))
        for sec in uc["by_section"]:
            assert sec["units"] == uc["total_units"]
            expected = sum(
                1
                for unit in uc["units"]
                if any(
                    s["section"] == sec["section"] and s["populated"]
                    for s in unit["sections"]
                )
            )
            assert sec["with_content"] == expected
            assert sec["coverage_pct"] == round(
                expected / sec["units"] * 100, 1
            )


def test_unit_coverage_overall_is_coherent():
    for level_id in COURSE_LEVELS:
        uc = unit_coverage(load_level(level_id))
        complete = sum(1 for unit in uc["units"] if not unit["missing"])
        assert uc["overall"]["complete_units"] == complete
        expected_mean = round(
            sum(unit["coverage_pct"] for unit in uc["units"]) / uc["total_units"], 1
        )
        assert uc["overall"]["mean_unit_coverage_pct"] == expected_mean


# --- CEFR DEPTH SCORE -------------------------------------------------------

def test_depth_weights_sum_to_one():
    assert sum(DEPTH_WEIGHTS.values()) == 1.0
    assert set(DEPTH_WEIGHTS) == {
        "objective_density",
        "objective_volume",
        "section_coverage",
        "subskill_breadth",
    }


def test_depth_score_is_weighted_sum_and_bounded():
    for level_id in COURSE_LEVELS:
        d = depth_score(load_level(level_id))
        expected = round(
            100
            * sum(
                d["components"][key]["value"] * DEPTH_WEIGHTS[key]
                for key in DEPTH_WEIGHTS
            ),
            1,
        )
        assert d["score"] == expected
        assert 0.0 <= d["score"] <= 100.0
        for key, comp in d["components"].items():
            assert 0.0 <= comp["value"] <= 1.0
            assert comp["weight"] == DEPTH_WEIGHTS[key]


def test_depth_density_and_volume_values_are_derived():
    for level_id in COURSE_LEVELS:
        level = load_level(level_id)
        d = depth_score(level)["components"]
        objectives = d["objective_density"]["objectives"]
        units = d["objective_density"]["units"]
        expected_density = min(objectives / units / OBJECTIVE_DENSITY_TARGET, 1.0)
        assert d["objective_density"]["value"] == round(expected_density, 3)
        assert d["objective_volume"]["value"] == round(
            min(objectives / OBJECTIVE_VOLUME_TARGET, 1.0), 3
        )


def test_depth_flags_c1_c2_as_shallower_than_a1():
    # Snapshot intencionadamente frágil: codifica el hallazgo de la auditoría V2.6
    # (C1=7 y C2=5 objetivos frente a A1=23). Se actualiza/elimina cuando V2.7
    # amplíe C1/C2.
    a1_depth = depth_score(load_level("a1"))["score"]
    for level_id in ("c1", "c2"):
        assert depth_score(load_level(level_id))["score"] < a1_depth


# --- DRILL-DOWN -------------------------------------------------------------

def test_unit_detail_returns_full_hierarchy():
    detail = unit_detail("a1", "a1-m01-u01")
    assert detail["level_id"] == "a1"
    assert detail["unit_id"] == "a1-m01-u01"
    assert detail["module_id"] == "a1-m01"
    assert detail["lessons"]
    for lesson in detail["lessons"]:
        assert lesson["lesson_id"]
        for obj in lesson["objectives"]:
            assert obj["objective_id"]
            assert obj["can_do"]
            assert isinstance(obj["activities"], int)
            assert isinstance(obj["checks"], int)
            assert isinstance(obj["listening_items"], list)
            assert isinstance(obj["scenario_ids"], list)
    assert [s["section"] for s in detail["sections"]] == list(course_svc.UNIT_SECTIONS)


def test_unit_detail_raises_for_unknown_unit():
    with pytest.raises(KeyError):
        unit_detail("a1", "no-existe")


# --- CURRICULUM QUALITY DASHBOARD -------------------------------------------

def test_quality_report_has_7_dimensions_and_6_levels():
    report = curriculum_quality_report()
    assert set(report["dimensions"]) == {
        "coverage",
        "depth",
        "listening",
        "speaking",
        "interaction",
        "assessment",
        "review",
    }
    assert report["overall"] == round(
        sum(d["score"] for d in report["dimensions"].values())
        / len(report["dimensions"]),
        1,
    )
    assert [lv["level_id"] for lv in report["by_level"]] == list(COURSE_LEVELS)
    for lv in report["by_level"]:
        assert 0.0 <= lv["depth"] <= 100.0
        assert 0.0 <= lv["unit_coverage_mean"] <= 100.0
        assert set(lv["sections"]) == set(course_svc.UNIT_SECTIONS)


def test_quality_report_is_deterministic():
    assert curriculum_quality_report() == curriculum_quality_report()


def test_quality_report_delta_identity_is_zero():
    report = curriculum_quality_report()
    delta = quality_report_delta(report, report)
    assert delta["overall"]["delta"] == 0.0
    assert all(d["delta"] == 0.0 for d in delta["dimensions"].values())
    assert all(d["delta"] == 0.0 for d in delta["by_level"].values())


# --- UNIT LEARNING LOOP -----------------------------------------------------

def test_learning_loop_has_9_phases():
    assert len(LEARNING_LOOP_PHASES) == 9
    assert LEARNING_LOOP_PHASES == (
        "introduce",
        "practice",
        "listen",
        "speak",
        "interact",
        "retrieve",
        "transfer",
        "assess",
        "review",
    )


def test_unit_learning_loop_reports_all_phases_and_bounded_pct():
    for level_id in COURSE_LEVELS:
        level = load_level(level_id)
        for mod in level.modules:
            for unit in mod.units:
                loop = unit_learning_loop(level, unit)
                assert [p["phase"] for p in loop["phases"]] == list(
                    LEARNING_LOOP_PHASES
                )
                covered = sum(1 for p in loop["phases"] if p["covered"])
                assert loop["covered_phases"] == covered
                assert loop["loop_pct"] == round(
                    covered / len(LEARNING_LOOP_PHASES) * 100, 1
                )
                assert 0.0 <= loop["loop_pct"] <= 100.0


def test_loop_introduce_and_practice_are_covered_in_every_unit():
    # Todas las unidades del currículo presentan (concepts/vocabulary) y practican
    # (actividades/checks). Si esto falla, hay una unidad vacía de contenido.
    for level_id in COURSE_LEVELS:
        lp = loop_coverage(load_level(level_id))
        by_phase = {entry["phase"]: entry for entry in lp["by_phase"]}
        for phase in ("introduce", "practice"):
            assert by_phase[phase]["coverage_pct"] == 100.0, f"{level_id} {phase}"


def test_loop_retrieve_and_transfer_are_tagged():
    # V2.6 C5: las unidades normales etiquetan retrieve/transfer con el marcador
    # `phase`, así que dejan de estar en 0. En A1 son las 9 unidades que no son el
    # módulo Final.
    lp = loop_coverage(load_level("a1"))
    by_phase = {entry["phase"]: entry for entry in lp["by_phase"]}
    assert by_phase["retrieve"]["covered_units"] > 0
    assert by_phase["transfer"]["covered_units"] > 0


def test_loop_assess_and_review_cover_every_unit():
    # V2.6 C5: assess/review ya no viven solo en el módulo Final; cada unidad
    # normal etiqueta una actividad de cierre (phase assess/review), de modo que
    # todas las unidades del nivel cubren ambas fases.
    lp = loop_coverage(load_level("a1"))
    by_phase = {entry["phase"]: entry for entry in lp["by_phase"]}
    for phase in ("assess", "review"):
        assert by_phase[phase]["covered_units"] == lp["total_units"]


def test_loop_reads_retrieve_and_transfer_from_activity_phase():
    # El marcador `phase` (V2.6) debe reflejarse en la medición del loop: una
    # actividad etiquetada retrieve/transfer deja de ser 0 en su fase.
    for phase in ("retrieve", "transfer"):
        level = _level_with_activity(phase)
        unit = level.modules[0].units[0]
        loop = unit_learning_loop(level, unit)
        by_phase = {p["phase"]: p for p in loop["phases"]}
        assert by_phase[phase]["covered"] is True
        assert by_phase[phase]["evidence"] == 1


def test_loop_reads_review_and_assess_from_activity_phase_in_non_final_unit():
    # Una actividad con phase="review"/"assess" marca la fase incluso fuera del
    # módulo Final (evaluación/repaso formativo por unidad, V2.6).
    for phase in ("review", "assess"):
        level = _level_with_activity(phase)
        unit = level.modules[0].units[0]
        loop = unit_learning_loop(level, unit)
        assert loop["is_final"] is False
        by_phase = {p["phase"]: p for p in loop["phases"]}
        assert by_phase[phase]["covered"] is True
        assert by_phase[phase]["evidence"] == 1


def test_coverage_loop_phases_alias_matches_curriculum_taxonomy():
    # Anti-drift: la taxonomía del instrumento re-exporta la fuente de verdad.
    from services.curriculum import LEARNING_PHASES

    assert LEARNING_LOOP_PHASES == LEARNING_PHASES


def test_quality_report_includes_learning_loop_block():
    report = curriculum_quality_report()
    loop = report["learning_loop"]
    assert loop["phases"] == list(LEARNING_LOOP_PHASES)
    assert 0.0 <= loop["mean_loop_pct"] <= 100.0
    assert [entry["phase"] for entry in loop["by_phase"]] == list(
        LEARNING_LOOP_PHASES
    )
    assert [lv["level_id"] for lv in loop["by_level"]] == list(COURSE_LEVELS)
    # Las 7 dimensiones del dashboard no cambian (el loop es un bloque aditivo).
    assert set(report["dimensions"]) == {
        "coverage",
        "depth",
        "listening",
        "speaking",
        "interaction",
        "assessment",
        "review",
    }
