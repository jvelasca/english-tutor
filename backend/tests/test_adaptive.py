"""Tests del Adaptive Engine (puros, deterministas, sin LLM ni red)."""

from services import adaptive
from services.academy import build_skill_profile
from services.curriculum import load_level

NOW = "2026-08-01T00:00:00+00:00"


def _entry(skill, score=0.0, confidence=0.0, evidence_count=0, **kwargs):
    return {
        "skill": skill,
        "score": score,
        "confidence": confidence,
        "evidence_count": evidence_count,
        "last_evidence": kwargs.get("last_evidence", ""),
        "review_due": kwargs.get("review_due", False),
        "subskills": [],
        "evidence_by_kind": kwargs.get("evidence_by_kind", {}),
    }


# --- Nivel continuo -------------------------------------------------------


def test_numeric_to_level_frontiers():
    assert adaptive.numeric_to_level(1.0) == "A1"
    assert adaptive.numeric_to_level(1.4) == "A1"
    assert adaptive.numeric_to_level(1.5) == "A2"
    assert adaptive.numeric_to_level(2.4) == "A2"
    assert adaptive.numeric_to_level(3.0) == "B1"
    assert adaptive.numeric_to_level(5.4) == "C1"
    assert adaptive.numeric_to_level(5.5) == "C2"
    assert adaptive.numeric_to_level(6.0) == "C2"


def test_estimated_level_empty_profile_is_a1_no_confidence():
    est = adaptive.estimated_level([])
    assert est["level"] == "A1"
    assert est["numeric"] == 1.0
    assert est["confidence"] == 0.0


def test_estimated_level_scales_with_overall():
    high = [
        _entry(s, score=0.9, confidence=0.9, evidence_count=5)
        for s in ("grammar", "vocabulary", "reading", "listening")
    ]
    est = adaptive.estimated_level(high)
    assert est["numeric"] > 3.0
    assert est["confidence"] > 0.0


# --- Estabilidad ----------------------------------------------------------


def test_skill_stability_combines_confidence_and_retrieval():
    recent = "2026-08-01T00:00:00+00:00"
    old = "2026-01-01T00:00:00+00:00"
    # Mismo score/confidence: más estable con repaso reciente que con olvido.
    assert adaptive.skill_stability(
        0.9, 0.9, recent, NOW
    ) > adaptive.skill_stability(0.9, 0.9, old, NOW)
    # Consistencia baja penaliza la estabilidad.
    assert adaptive.skill_stability(
        0.9, 0.3, recent, NOW
    ) < adaptive.skill_stability(0.9, 0.9, recent, NOW)


def test_skill_stability_bounded():
    assert 0.0 <= adaptive.skill_stability(1.0, 1.0, NOW, NOW) <= 1.0


# --- Readiness ------------------------------------------------------------


def test_readiness_requires_score_confidence_and_evidence():
    profile = [
        _entry("grammar", score=0.9, confidence=0.9, evidence_count=5),
        _entry("vocabulary", score=0.9, confidence=0.9, evidence_count=2),
        _entry("listening", score=0.5, confidence=0.9, evidence_count=5),
    ]
    result = adaptive.readiness(profile, "B1")
    by_skill = {s["skill"]: s for s in result["skills"]}
    assert by_skill["grammar"]["ready"] is True
    assert by_skill["vocabulary"]["ready"] is False  # pocas evidencias
    assert by_skill["listening"]["ready"] is False  # score bajo
    assert result["ready"] is False
    assert set(result["blocking_skills"]) == {"vocabulary", "listening"}


def test_readiness_ignores_unevaluated_skills():
    profile = [_entry("grammar")]
    result = adaptive.readiness(profile, "B1")
    # Una destreza sin evaluar no cuenta como bloqueante: aún no hay dato.
    assert result["overall"] == 0.0
    assert result["blocking_skills"] == []
    assert result["skills"][0]["ready"] is False


def test_readiness_all_ready():
    # B1 exige evidencia de transferencia en reading/listening (macro-destrezas).
    profile = [
        _entry(
            s,
            score=0.9,
            confidence=0.9,
            evidence_count=4,
            evidence_by_kind={"transfer": 1, "novel": 0},
        )
        for s in ("grammar", "vocabulary", "reading", "listening")
    ]
    result = adaptive.readiness(profile, "B1")
    assert result["ready"] is True
    assert result["overall"] == 100.0
    assert result["blocking_skills"] == []


def test_readiness_b1_listening_blocked_without_transfer():
    profile = [
        _entry(
            "listening",
            score=0.9,
            confidence=0.9,
            evidence_count=4,
            evidence_by_kind={"transfer": 0, "novel": 0},
        )
    ]
    result = adaptive.readiness(profile, "B1")
    by_skill = {s["skill"]: s for s in result["skills"]}
    assert by_skill["listening"]["ready"] is False
    assert by_skill["listening"]["transfer_required"] == 1
    assert by_skill["listening"]["transfer_count"] == 0
    assert result["ready"] is False
    assert result["blocking_skills"] == ["listening"]


def test_readiness_b2_blocked_without_novel():
    profile = [
        _entry(
            "listening",
            score=0.9,
            confidence=0.9,
            evidence_count=4,
            evidence_by_kind={"transfer": 2, "novel": 0},
        )
    ]
    result = adaptive.readiness(profile, "B2")
    by_skill = {s["skill"]: s for s in result["skills"]}
    assert by_skill["listening"]["ready"] is False
    assert by_skill["listening"]["novel_required"] == 1
    assert by_skill["listening"]["novel_count"] == 0
    assert result["blocking_skills"] == ["listening"]


def test_readiness_legacy_profile_without_evidence_by_kind_not_blocked():
    # Perfil legacy (sin la clave `evidence_by_kind`): el gate de transfer/novedad
    # no se aplica y la destreza puede quedar ready por score/confianza/evidencia.
    entry = _entry("listening", score=0.9, confidence=0.9, evidence_count=4)
    del entry["evidence_by_kind"]
    result = adaptive.readiness([entry], "B1")
    by_skill = {s["skill"]: s for s in result["skills"]}
    assert by_skill["listening"]["ready"] is True
    assert result["ready"] is True


# --- Reevaluación continua -------------------------------------------------


def test_reassessment_due_none_without_evidence():
    assert adaptive.reassessment_due([], [], NOW) is None


def test_reassessment_due_first_reassessment():
    profile = [
        _entry("grammar", score=0.8, confidence=0.8, evidence_count=4),
        _entry("vocabulary", score=0.7, confidence=0.7, evidence_count=3),
    ]
    result = adaptive.reassessment_due(profile, [], NOW)
    assert result is not None
    assert result["reason"] == "first-reassessment"
    assert result["skill"] == "vocabulary"  # más débil


def test_reassessment_due_time_elapsed():
    profile = [
        _entry("grammar", score=0.8, confidence=0.8, evidence_count=4),
        _entry("vocabulary", score=0.7, confidence=0.7, evidence_count=3),
    ]
    history = [{"created_at": "2026-07-01T00:00:00+00:00", "passed": True}]
    result = adaptive.reassessment_due(profile, history, NOW)
    assert result is not None
    assert result["reason"] == "time-elapsed"


def test_reassessment_due_not_yet():
    profile = [
        _entry("grammar", score=0.8, confidence=0.8, evidence_count=4),
        _entry("vocabulary", score=0.7, confidence=0.7, evidence_count=3),
    ]
    history = [{"created_at": "2026-08-01T00:00:00+00:00", "passed": True}]
    assert adaptive.reassessment_due(profile, history, NOW) is None


def test_reassessment_due_requires_confidence():
    profile = [
        _entry("grammar", score=0.8, confidence=0.2, evidence_count=4),
        _entry("vocabulary", score=0.7, confidence=0.2, evidence_count=3),
    ]
    assert adaptive.reassessment_due(profile, [], NOW) is None


# --- Today's Plan ---------------------------------------------------------


def test_today_plan_empty_profile_gives_next_objective_only():
    plan = adaptive.today_plan(
        [], level=load_level("a1"), next_objective_id="a1-m01-u01-l01-o01"
    )
    kinds = {i["kind"] for i in plan}
    assert "new" in kinds
    assert "weakness" not in kinds


def test_today_plan_mixes_categories_and_sums_budget():
    level = load_level("a1")
    objs = level.objectives()
    target = objs[1]
    skill = target.assessable_skills()[0]
    remediation = [{"skill": skill, "score": 0.4, "objective_ids": [target.id]}]
    profile = [
        _entry(
            skill,
            score=0.4,
            confidence=0.4,
            evidence_count=4,
            last_evidence="2026-01-01T00:00:00+00:00",
            review_due=True,
        ),
        _entry(
            "vocabulary",
            score=0.9,
            confidence=0.9,
            evidence_count=4,
            last_evidence="2026-08-01T00:00:00+00:00",
            review_due=False,
        ),
    ]
    plan = adaptive.today_plan(
        profile,
        level=level,
        remediation=remediation,
        mastered_ids=set(),
        next_objective_id=objs[0].id,
        budget_minutes=30,
    )
    assert plan, "el plan no está vacío"
    kinds = {i["kind"] for i in plan}
    assert "weakness" in kinds
    assert "review" in kinds
    assert "new" in kinds
    assert "easy_wins" in kinds
    assert sum(i["minutes"] for i in plan) == 30
    expected_keys = {"kind", "skill", "objective_id", "title", "reason", "minutes"}
    for item in plan:
        assert set(item) == expected_keys


def test_today_plan_weakness_gets_most_minutes():
    profile = [
        _entry(
            "grammar",
            score=0.3,
            confidence=0.3,
            evidence_count=4,
            last_evidence="2026-01-01T00:00:00+00:00",
            review_due=True,
        ),
        _entry(
            "vocabulary",
            score=0.9,
            confidence=0.9,
            evidence_count=4,
            last_evidence="2026-08-01T00:00:00+00:00",
            review_due=False,
        ),
    ]
    plan = adaptive.today_plan(
        profile,
        level=load_level("a1"),
        remediation=[{"skill": "grammar", "score": 0.3, "objective_ids": ["o1"]}],
        mastered_ids=set(),
        next_objective_id="o2",
        budget_minutes=30,
    )
    minutes = {i["kind"]: i["minutes"] for i in plan}
    assert minutes["weakness"] >= minutes["review"]
    assert minutes["weakness"] >= minutes["new"]
    assert sum(minutes.values()) == 30


def test_today_plan_handles_zero_budget():
    plan = adaptive.today_plan([], next_objective_id="o1", budget_minutes=0)
    for item in plan:
        assert item["minutes"] == 0


# --- Session Engine -------------------------------------------------------


def test_session_plan_orders_review_then_listening_then_new():
    profile = [
        _entry(
            "grammar",
            score=0.6,
            confidence=0.6,
            evidence_count=4,
            last_evidence="2026-01-01T00:00:00+00:00",
            review_due=True,
        ),
    ]
    steps = adaptive.session_plan(
        profile,
        level=load_level("a1"),
        listening_weak=["gist", "detail"],
        next_objective_id="a1-m01-u01-l01-o01",
        budget_minutes=20,
    )
    kinds = [s["kind"] for s in steps]
    # El repaso vence antes que el listening; el material nuevo va al final.
    assert kinds.index("review") < kinds.index("listening")
    assert kinds.index("listening") < kinds.index("new")
    assert sum(s["minutes"] for s in steps) == 20


def test_session_plan_caps_listening_when_many_pending():
    all_subskills = [
        "gist",
        "detail",
        "inference",
        "attitude",
        "vocabulary",
        "numbers",
        "speaker_intention",
        "fast_speech",
        "connected_speech",
        "dictation",
        "shadowing",
        "multiple_speakers",
        "note_taking",
        "prediction",
        "sequencing",
    ]
    steps = adaptive.session_plan(
        [],
        level=load_level("a1"),
        listening_weak=all_subskills,
        next_objective_id="a1-m01-u01-l01-o01",
        budget_minutes=15,
    )
    listening_steps = adaptive.steps_of(steps, "listening")
    assert len(listening_steps) == 2
    # Las dos sub-destrezas más prioritarias (orden del diagnóstico).
    assert [s["subskill"] for s in listening_steps] == ["gist", "detail"]


def test_session_plan_steps_have_subskill_key():
    steps = adaptive.session_plan(
        [],
        level=load_level("a1"),
        listening_weak=["gist"],
        next_objective_id="a1-m01-u01-l01-o01",
        budget_minutes=10,
    )
    expected_keys = {
        "kind",
        "step_key",
        "skill",
        "subskill",
        "objective_id",
        "level_id",
        "skills",
        "title",
        "reason",
        "minutes",
    }
    for step in steps:
        assert set(step) == expected_keys


def test_session_summary_counts_review_and_practice():
    steps = [
        {"kind": "review", "minutes": 5},
        {"kind": "listening", "minutes": 3},
        {"kind": "weakness", "minutes": 4},
        {"kind": "new", "minutes": 2},
        {"kind": "easy_wins", "minutes": 1},
    ]
    summary = adaptive.session_summary(steps)
    assert summary == {"review_count": 2, "practice_count": 2}


def test_session_plan_new_step_carries_level_and_skills():
    level = load_level("a1")
    obj = level.objectives()[0]
    steps = adaptive.session_plan(
        [],
        level=level,
        next_objective_id=obj.id,
        budget_minutes=10,
    )
    new_step = next(s for s in steps if s["kind"] == "new")
    assert new_step["objective_id"] == obj.id
    assert new_step["level_id"] == level.level_id
    assert set(new_step["skills"]) == set(obj.skills)


def test_step_key_is_deterministic_per_kind():
    assert adaptive.step_key({"kind": "review", "skill": "grammar"}) == "review:grammar"
    assert (
        adaptive.step_key({"kind": "easy_wins", "skill": "vocabulary"})
        == "easy_wins:vocabulary"
    )
    assert (
        adaptive.step_key({"kind": "listening", "subskill": "gist"})
        == "listening:gist"
    )
    assert (
        adaptive.step_key(
            {"kind": "new", "level_id": "a1", "objective_id": "o1"}
        )
        == "new:a1:o1"
    )


def test_session_plan_exclude_keys_filters_and_respreads_minutes():
    level = load_level("a1")
    obj = level.objectives()[0]
    steps = adaptive.session_plan(
        [],
        level=level,
        listening_weak=["gist", "detail"],
        next_objective_id=obj.id,
        budget_minutes=15,
        exclude_keys={"listening:gist"},
    )
    keys = {s["step_key"] for s in steps}
    assert "listening:gist" not in keys
    assert "listening:detail" in keys
    # Los minutos se reparten solo entre los pasos restantes.
    assert sum(s["minutes"] for s in steps) == 15


def test_session_plan_excludes_all_steps_gives_empty():
    level = load_level("a1")
    obj = level.objectives()[0]
    steps = adaptive.session_plan(
        [],
        level=level,
        listening_weak=["gist", "detail"],
        next_objective_id=obj.id,
        budget_minutes=15,
        exclude_keys={"listening:gist", "listening:detail", f"new:a1:{obj.id}"},
    )
    assert steps == []


# --- Integración con build_skill_profile ----------------------------------


def test_stability_and_estimated_level_over_real_profile():
    level = load_level("a1")
    obj = next(iter(level.objectives()))
    skill = obj.skills[0]
    objective_mastery = {
        obj.id: {
            skill: {
                "score": 0.9,
                "recent_score": 0.9,
                "confidence": 0.8,
                "streak": 3,
                "attempts": 3,
                "last_seen_at": "2026-08-01T00:00:00+00:00",
            }
        }
    }
    evidence_rows = [
        {"skill": skill, "created_at": "2026-08-01T00:00:00+00:00"}
        for _ in range(3)
    ]
    profile = build_skill_profile(level, objective_mastery, evidence_rows, now=NOW)
    entry = next(e for e in profile if e["skill"] == skill)
    stability = adaptive.skill_stability(
        entry["score"], entry["confidence"], entry["last_evidence"], NOW
    )
    assert 0.0 <= stability <= 1.0
