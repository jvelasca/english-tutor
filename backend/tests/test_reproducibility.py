"""Tests de reproducibilidad: mismas versiones + mismas respuestas ⇒ mismo resultado.

Refuerza la garantía central de V1.5.2/1.5.3: para un instrumento (curriculum +
assessment + placement + listening bank) fijo, la salida es determinista. Incluye
la monotonicidad de θ del placement adaptativo (acierto ⇒ θ no baja, fallo ⇒ θ no
sube).
"""

from services import academy as academy_svc
from services.curriculum import load_assessments, load_level
from services.listening import listening_diagnostic


def _placement_items():
    return load_assessments().placement.items


# --- Placement: determinismo ---------------------------------------------


def test_placement_result_is_deterministic():
    items = _placement_items()
    answers = {it.id: it.correct_index for it in items[:5]}
    first = academy_svc.placement_result_adaptive(items, answers)
    second = academy_svc.placement_result_adaptive(items, dict(answers))
    assert first == second
    assert first["theta"] == second["theta"]
    assert first["level"] == second["level"]
    assert first["confidence"] == second["confidence"]


# --- Placement: monotonicidad de θ ---------------------------------------


def test_placement_theta_monotonic_in_responses():
    base = [(1, True), (3, True), (5, False)]
    theta_base = academy_svc.ability_theta(base)
    # Un acierto adicional no reduce θ.
    theta_correct = academy_svc.ability_theta(base + [(2, True)])
    assert theta_correct >= theta_base
    # Un fallo adicional no aumenta θ.
    theta_wrong = academy_svc.ability_theta(base + [(4, False)])
    assert theta_wrong <= theta_base


def test_placement_theta_deterministic():
    responses = [(1, True), (3, True), (5, False), (4, False)]
    assert academy_svc.ability_theta(responses) == academy_svc.ability_theta(
        list(responses)
    )


# --- Evidencia: determinismo ---------------------------------------------


def test_evidence_from_items_is_deterministic():
    items = _placement_items()
    answers = {it.id: it.correct_index for it in items[:3]}
    kwargs = dict(
        level_id="a1",
        objective_id="o1",
        source="objective_assessment",
        curriculum_version="1.2.5",
        assessment_version="1.0.0",
    )
    first = academy_svc.evidence_from_items(items, answers, **kwargs)
    second = academy_svc.evidence_from_items(items, dict(answers), **kwargs)
    assert first == second
    assert [r["result"] for r in first] == [1.0, 1.0, 1.0]


# --- Listening: determinismo ---------------------------------------------


def test_listening_diagnostic_is_deterministic():
    rows = [
        {
            "question_id": "l1",
            "skill": "detail",
            "correct": False,
            "response_time_ms": 1000,
            "replay_count": 0,
        },
        {
            "question_id": "l1",
            "skill": "detail",
            "correct": True,
            "response_time_ms": 800,
            "replay_count": 2,
        },
        {
            "question_id": "l2",
            "skill": "detail",
            "correct": True,
            "response_time_ms": 900,
            "replay_count": 0,
        },
    ]
    assert listening_diagnostic(rows) == listening_diagnostic([dict(r) for r in rows])


# --- Perfil CEFR: determinismo -------------------------------------------


def test_build_skill_profile_is_deterministic():
    lv = load_level("a1")
    objective_mastery: dict[str, dict[str, dict]] = {}
    for o in lv.objectives():
        for skill in o.assessable_skills():
            objective_mastery.setdefault(o.id, {})[skill] = {
                "score": 0.75,
                "confidence": 0.6,
                "last_seen_at": "2026-01-01T00:00:00Z",
            }
    evidence_rows = [
        {
            "skill": "grammar",
            "created_at": "2026-01-01T00:00:00Z",
            "result": 1.0,
        }
    ]
    now = "2026-02-01T00:00:00Z"
    first = academy_svc.build_skill_profile(lv, objective_mastery, evidence_rows, now)
    second = academy_svc.build_skill_profile(lv, objective_mastery, evidence_rows, now)
    assert first == second
    assert first, "perfil vacío inesperado"
