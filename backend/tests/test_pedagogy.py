"""Tests de regresión pedagógica (V2.2).

Invariantes que protegen la lógica educativa al margen de cambios de código:
- la métrica única de contenido validado no se desincroniza (anti-drift),
- cada unidad expone la plantilla fija de 7 secciones,
- los Learning Objectives de unidad derivan de `can_do`,
- los Mastery Gates bloquean una unidad si una sección declarada no llega al
  umbral compuesto (y no se "pasa" por sumar ejercicios),
- el Adaptive Engine recomienda la sub-destreza de listening más débil,
- el contrato CEFR y la tríada Progress/Mastery/Readiness son consistentes.
"""
from services import adaptive
from services import course as course_svc
from services.content_validation import content_stats, run_content_validation
from services.curriculum import load_level
from services.listening import QUESTION_BANK
from services.speaking_scenarios import list_scenarios

# --- Métrica única (anti-drift) -------------------------------------------

def test_content_stats_matches_validator_and_bank():
    stats = content_stats()
    report = run_content_validation()
    # El validador reporta la misma cifra canónica que content_stats().
    assert (
        report["total_validated_learning_items"]
        == stats["total_validated_learning_items"]
    )
    # La cifra deriva de las dos fuentes canónicas (banco + escenarios).
    expected = len(QUESTION_BANK) + len(list_scenarios())
    assert stats["total_validated_learning_items"] == expected
    # Desglose coherente: corpus + legacy == total del banco.
    assert (
        stats["listening"]["corpus"] + stats["listening"]["legacy_tts"]
        == stats["listening"]["total"]
    )
    # Niveles CEFR completos.
    assert stats["levels"] == ["A1", "A2", "B1", "B2", "C1", "C2"]


# --- Plantilla fija de 7 secciones -----------------------------------------

def test_every_unit_exposes_7_sections():
    for level_id in ("a1", "a2", "b1", "b2", "c1", "c2"):
        lv = load_level(level_id)
        for mod in lv.modules:
            for unit in mod.units:
                sections = course_svc.unit_sections(lv, unit)
                assert [s["section"] for s in sections] == list(
                    course_svc.UNIT_SECTIONS
                )
                for s in sections:
                    assert s["count"] >= 0
                    assert s["needs_content"] == (s["count"] == 0)


def test_unit_sequence_exposes_sections_objectives_gates():
    lv = load_level("a1")
    units = course_svc.unit_sequence(lv, set())
    for unit in units:
        assert len(unit["sections"]) == len(course_svc.UNIT_SECTIONS)
        assert isinstance(unit["objectives"], list)
        assert "gate_mastered" in unit
        assert unit["gates"] == []  # sin profile no se desglosan gates


# --- Learning Objectives de unidad -----------------------------------------

def test_unit_objectives_derive_from_can_do():
    lv = load_level("a1")
    for mod in lv.modules:
        for unit in mod.units:
            objectives = course_svc.unit_objectives(unit)
            flattened = [o.can_do for les in unit.lessons for o in les.objectives]
            assert objectives == flattened


# --- Mastery Gates ---------------------------------------------------------

def _profile(macro: set[str], score: float, transfer: int = 1) -> list[dict]:
    return [
        {
            "skill": s,
            "score": score,
            "confidence": 0.9,
            "evidence_count": 3,
            "review_due": False,
            "evidence_by_kind": {"familiar": 1, "transfer": transfer, "novel": 0},
        }
        for s in macro
    ]


def _declared_macro(lv, unit) -> set[str]:
    sections = {s["section"]: s for s in course_svc.unit_sections(lv, unit)}
    return {
        s
        for s in course_svc.UNIT_GATE_THRESHOLDS
        if sections.get(s, {}).get("count", 0) > 0
    }


def test_unit_gates_mastered_when_all_declared_met():
    lv = load_level("a1")
    unit = next(u for m in lv.modules for u in m.units)
    macro = _declared_macro(lv, unit)
    assert macro, "la unidad debe declarar al menos una sección macro"
    result = course_svc.unit_gates(lv, unit, _profile(macro, 0.9))
    assert result["mastered"] is True
    assert all(g["met"] for g in result["gates"])


def test_unit_gates_blocking_section_blocks_mastery():
    lv = load_level("a1")
    unit = next(u for m in lv.modules for u in m.units)
    macro = _declared_macro(lv, unit)
    blocking = sorted(macro)[0]
    # Todas las secciones altas excepto una por debajo del umbral.
    profile = _profile(macro, 0.9)
    for e in profile:
        if e["skill"] == blocking:
            e["score"] = 0.4
    result = course_svc.unit_gates(lv, unit, profile)
    assert result["mastered"] is False
    gate = next(g for g in result["gates"] if g["section"] == blocking)
    assert gate["met"] is False
    # El gate compuesto no se pasa por promediar: una sección bloqueante basta.
    assert any(g["met"] is False for g in result["gates"])


def test_unit_gates_retention_or_transfer_blocks():
    lv = load_level("a1")
    unit = next(u for m in lv.modules for u in m.units)
    macro = _declared_macro(lv, unit)
    # Sin evidencia de transferencia → no dominado aunque el score sea alto.
    result = course_svc.unit_gates(lv, unit, _profile(macro, 0.9, transfer=0))
    assert result["mastered"] is False
    transfer_gate = next(g for g in result["gates"] if g["section"] == "transfer")
    assert transfer_gate["met"] is False


# --- Adaptive: recomendación por sub-destreza débil -------------------------

def test_weak_connected_speech_recommends_connected_speech():
    steps = adaptive.session_plan(
        [],
        listening_weak=["connected_speech", "fast_speech"],
    )
    listening = [s for s in steps if s["kind"] == "listening"]
    assert listening, "debe incluir práctica de listening"
    assert listening[0]["subskill"] == "connected_speech"
    nba = adaptive.next_best_activity(steps, [])
    assert nba is not None
    assert nba["subskill"] == "connected_speech"
    assert nba["reason"] == "weak_subskill"
    assert "connected speech" in nba["why"]


# --- Contrato CEFR + Tríada ------------------------------------------------

def test_dimension_state_contract():
    mastery = [
        {"skill": "listening", "score": 0.8, "evidence_count": 5},
        {"skill": "speaking", "score": 0.5, "evidence_count": 2},
        {"skill": "grammar", "score": 0.9, "evidence_count": 0},
    ]
    assert adaptive.dimension_state(mastery, "listening") == "mastered"
    assert adaptive.dimension_state(mastery, "speaking") == "in_progress"
    assert adaptive.dimension_state(mastery, "grammar") == "not_started"
    # Dimensión sin destreza registrada → not_started.
    assert adaptive.dimension_state(mastery, "writing") == "not_started"


def test_student_dashboard_triad():
    dashboard = adaptive.student_dashboard(
        progress=0.5,
        mastery=[
            {"skill": "listening", "score": 0.8, "evidence_count": 4},
            {"skill": "speaking", "score": 0.6, "evidence_count": 2},
            {"skill": "grammar", "score": 0.4, "evidence_count": 0},
        ],
        readiness={"overall": 66.7, "band": "approaching"},
    )
    assert dashboard["progress"] == 50.0
    assert dashboard["mastery"] == 70.0  # media de 0.8 y 0.6 (grammar sin evidencia)
    assert dashboard["readiness"] == {"overall": 66.7, "band": "approaching"}
