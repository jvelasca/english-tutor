"""Tests de la auditoría de cobertura curricular (V2.4).

Invariantes que protegen el instrumento de cobertura al margen de cambios de
contenido:
- los 7 niveles (Pre-A1 + A1..C2) aparecen, cada uno con 7 secciones;
- Pre-A1 es una banda sin curso (todas las secciones vacías);
- el cruce con los bancos de destrezas refleja el contenido real;
- la métrica TOTAL CURRICULUM COVERAGE es coherente y determinista;
- las dos métricas (validated items vs coverage) conviven en `content_stats()`.
"""
from collections import Counter

from services import course as course_svc
from services.content_validation import content_stats
from services.curriculum_coverage import (
    COVERAGE_LEVEL_IDS,
    EMPTY,
    bank_intersection,
    coverage_metric,
    curriculum_coverage_report,
    level_coverage,
)
from services.listening import QUESTION_BANK
from services.speaking_scenarios import list_scenarios

# --- Estructura del reporte ------------------------------------------------

def test_report_has_7_levels_each_with_7_sections():
    report = curriculum_coverage_report()
    assert [lv["level_id"] for lv in report["levels"]] == list(COVERAGE_LEVEL_IDS)
    for lv in report["levels"]:
        assert [s["section"] for s in lv["sections"]] == list(course_svc.UNIT_SECTIONS)


def test_pre_a1_is_band_only_without_course():
    pre = curriculum_coverage_report()["levels"][0]
    assert pre["level_id"] == "pre-a1"
    assert pre["has_course"] is False
    assert pre["band_only"] is True
    assert pre["units"] == 0
    assert pre["objectives"] == 0
    assert all(s["status"] == EMPTY for s in pre["sections"])
    assert all(s["needs_content"] for s in pre["sections"])


# --- Cruce con los bancos de destrezas -------------------------------------

def test_bank_intersection_matches_sources():
    banks = bank_intersection()
    listening_by_level = Counter(q["level"] for q in QUESTION_BANK)
    speaking_by_level = Counter(s["cefr_target"] for s in list_scenarios())
    for level, expected_listening in listening_by_level.items():
        assert banks[level]["listening"] == expected_listening
    for level, expected_speaking in speaking_by_level.items():
        assert banks[level]["speaking"] == expected_speaking


def test_bank_intersection_covers_listening_c1_c2():
    banks = bank_intersection()
    # C1/C2 ya tienen ítems de listening en el banco (hueco completado en V2.5-C1).
    assert banks["C1"]["listening"] > 0
    assert banks["C2"]["listening"] > 0
    for level in ("A1", "A2", "B1", "B2"):
        assert banks[level]["listening"] > 0


def test_listening_bank_has_at_least_20_items_per_level():
    # Invariante: el banco de listening cubre los 6 niveles con ≥20 ítems cada uno.
    by_level = Counter(q["level"] for q in QUESTION_BANK)
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        assert by_level[level] >= 20


def test_bank_intersection_covers_speaking_c2():
    banks = bank_intersection()
    # C2 ya tiene escenarios de speaking en el banco (hueco completado en V2.5-C2).
    assert banks["C2"]["speaking"] > 0


def test_interaction_section_populated_in_a1_a2_b2_c1_c2():
    # V2.5-C3: interaction deja de estar `empty` en los niveles con curso.
    for level_id in ("a1", "a2", "b2", "c1", "c2"):
        by_section = {s["section"]: s for s in level_coverage(level_id)["sections"]}
        interaction = by_section["interaction"]
        assert interaction["count"] > 0, f"{level_id} interaction sigue vacío"
        assert interaction["status"] != EMPTY


def test_level_coverage_attaches_bank_count_to_listening_speaking():
    lv = level_coverage("a1")
    by_section = {s["section"]: s for s in lv["sections"]}
    banks = bank_intersection()
    assert by_section["listening"]["bank_count"] == banks["A1"]["listening"]
    assert by_section["speaking"]["bank_count"] == banks["A1"]["speaking"]
    # Las demás secciones no tienen banco asociado.
    for section in ("vocabulary", "grammar", "interaction", "review", "assessment"):
        assert by_section[section]["bank_count"] == 0


# --- Métrica TOTAL CURRICULUM COVERAGE -------------------------------------

def test_coverage_metric_is_coherent():
    metric = coverage_metric()
    assert metric["total_cells"] == 7 * 7
    assert 0 <= metric["populated_cells"] <= metric["total_cells"]
    assert 0.0 <= metric["coverage_pct"] <= 100.0
    expected = round(metric["populated_cells"] / metric["total_cells"] * 100, 1)
    assert metric["coverage_pct"] == expected
    # Desgloses consistentes con el total.
    assert sum(lv["populated"] for lv in metric["by_level"].values()) == metric[
        "populated_cells"
    ]
    assert sum(sec["populated"] for sec in metric["by_section"].values()) == metric[
        "populated_cells"
    ]


def test_coverage_report_is_deterministic():
    report_a = curriculum_coverage_report()
    report_b = curriculum_coverage_report()
    assert report_a == report_b


# --- Coexistencia de las dos métricas --------------------------------------

def test_content_stats_coexists_validated_items_and_coverage():
    stats = content_stats()
    assert "total_validated_learning_items" in stats
    assert "total_curriculum_coverage" in stats
    # Son métricas diferentes: una es un entero (contenido validado) y la otra
    # un dict (cobertura curricular), y deben coincidir con sus fuentes.
    assert isinstance(stats["total_validated_learning_items"], int)
    assert stats["total_curriculum_coverage"] == coverage_metric()
