"""Tests del registro por competencia (4 estados, Constitución §2.1/§6)."""
from services.competence import competence_state, competence_states
from services.mastery import MASTERY_SKILLS


def _entry(
    *,
    score: float = 0.0,
    confidence: float = 0.0,
    evidence_count: int = 0,
    evidence_by_kind: dict | None = None,
    review_due: bool = False,
) -> dict:
    return {
        "skill": "grammar",
        "score": score,
        "confidence": confidence,
        "evidence_count": evidence_count,
        "evidence_by_kind": evidence_by_kind or {},
        "review_due": review_due,
    }


def test_empty_profile_all_not_started():
    records = competence_states([], "A1")
    assert [r["skill"] for r in records] == list(MASTERY_SKILLS)
    assert all(r["state"] == "not_started" for r in records)
    assert all(r["demonstrated"] is False for r in records)
    assert all(r["estimated_band"] == "—" for r in records)


def test_no_entry_is_not_started_without_band():
    record = competence_state(None, "grammar", "A1")
    assert record["state"] == "not_started"
    assert record["estimated_band"] == "—"
    assert record["demonstrated"] is False


def test_partial_evidence_is_developing():
    record = competence_state(_entry(score=0.5, confidence=0.8, evidence_count=2), "grammar", "A1")
    assert record["state"] == "developing"
    # La banda heurística por destreza es la del Student Model (proxy interno).
    assert record["estimated_band"] != "—"
    assert record["gate"]["score_ok"] is False
    assert record["gate"]["confidence_ok"] is True


def test_gate_met_is_functional_but_not_demonstrated():
    # Score 0.85 >= 0.7 (mínimo de grammar), confianza y volumen suficientes,
    # sin repaso pendiente ni retención retardada: FUNCTIONAL, nunca DEMONSTRATED.
    record = competence_state(
        _entry(score=0.85, confidence=0.8, evidence_count=5),
        "grammar",
        "A1",
    )
    assert record["state"] == "functional"
    assert record["demonstrated"] is False
    assert record["gate"]["retention_ok"] is False


def test_delayed_evidence_grants_demonstrated():
    record = competence_state(
        _entry(
            score=0.85,
            confidence=0.8,
            evidence_count=5,
            evidence_by_kind={"familiar": 4, "delayed": 1},
        ),
        "grammar",
        "A1",
    )
    assert record["state"] == "demonstrated"
    assert record["demonstrated"] is True


def test_review_due_blocks_functional_even_with_delayed():
    record = competence_state(
        _entry(
            score=0.85,
            confidence=0.8,
            evidence_count=5,
            evidence_by_kind={"delayed": 1},
            review_due=True,
        ),
        "grammar",
        "A1",
    )
    assert record["state"] == "developing"
    assert record["demonstrated"] is False


def test_interaction_uses_default_floor():
    record = competence_state(_entry(score=0.75, confidence=0.8, evidence_count=4), "interaction", "A1")
    assert record["state"] == "functional"


def _listening_entry(routes: list[dict]) -> dict:
    entry = _entry(evidence_count=0)
    entry["skill"] = "listening"
    entry["routes"] = routes
    return entry


def test_listening_route_functional_elevates_without_formal_evidence():
    records = competence_states([_listening_entry([{"level": "A1", "state": "functional"}])], "A1")
    record = next(r for r in records if r["skill"] == "listening")
    assert record["state"] == "functional"


def test_listening_route_demonstrated_only_with_retention():
    records = competence_states([_listening_entry([{"level": "A1", "state": "demonstrated"}])], "A1")
    record = next(r for r in records if r["skill"] == "listening")
    assert record["state"] == "demonstrated"
    assert record["demonstrated"] is True
    assert record["gate"]["retention_ok"] is True


def test_listening_route_other_level_ignored():
    # El estado se calcula para el nivel actual del Student Model (A1): la ruta
    # de otro nivel no eleva esta competencia.
    records = competence_states([_listening_entry([{"level": "A2", "state": "demonstrated"}])], "A1")
    record = next(r for r in records if r["skill"] == "listening")
    assert record["state"] == "not_started"
