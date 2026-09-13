"""V3.54 — Student Skill State 3.0 (P1 de la auditoría de V3.53.1).

V3.53 colapsaba las modalidades de la capacidad observada en un único vector por
dimensión (máximo entre skills): una producción ESCRITA B2 podía elevar el reto
de una tarea ORAL que el alumno nunca ha producido, y una capacidad parcial podía
elevar una tarea multidimensional. V3.54 conserva la modalidad:

    EVIDENCE → SKILL × DIMENSIÓN → CAPACIDAD OBSERVADA → SUELO POR SKILL

Aquí se cubre lo NUEVO: el estado por skill × dimensión, el nivel por skill (con
la regla de cobertura completa de V3.53.1), la cobertura dimensional, el suelo
por modalidad, el gate de cobertura del Difficulty Engine y la persistencia
aditiva. La no-regresión de V3.51-V3.53 vive en sus propias suites.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import closing

from fastapi.testclient import TestClient

from domain import profile as profile_domain
from domain import vocabulary as vocabulary_domain
from main import app
from repositories import db
from repositories import evidence as evidence_repo
from repositories import profile as profile_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import difficulty, learner_skill, student_state, transfer


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _seed_word(a: str, word: str, *, cefr: str = "B2") -> None:
    vocabulary_repo.seed_curriculum_items(
        a,
        [
            {
                "word": word,
                "lemma": word,
                "cefr": cefr,
                "level_id": "a1",
                "objective_id": "o1",
                "kind": "word",
            }
        ],
    )
    vocabulary_repo.record_exposures(a, [word])


def _columns(table: str) -> set[str]:
    with closing(db._conn()) as conn:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _signals(skill: str, by_dimension: dict[str, dict[str, int]]) -> dict:
    """Señales de `observed_signals` para las dimensiones de un skill."""
    samples: dict[str, dict[str, int]] = {skill: {}}
    days: dict[str, dict[str, int]] = {skill: {}}
    capacity: dict[str, dict[str, int]] = {skill: {}}
    for dimension, values in by_dimension.items():
        samples[skill][dimension] = values["samples"]
        days[skill][dimension] = values["days"]
        capacity[skill][dimension] = values["load"]
    return {
        "observed_samples": samples,
        "observed_days": days,
        "observed_capacity": capacity,
    }


FULL_C2 = {"lexical": 5, "syntax": 5, "discourse": 5, "interaction": 5}


# ------------------------------------------------------------- estado por skill


def test_observed_skill_capacity_keeps_the_modality():
    signals = _signals(
        "written_production",
        {
            "lexical": {"samples": 2, "days": 2, "load": 3},
            # Muestra insuficiente: NO asciende (espaciado por skill × dimensión).
            "syntax": {"samples": 1, "days": 2, "load": 5},
        },
    )
    assert learner_skill.observed_skill_capacity(signals) == {
        "written_production": {"lexical": 3}
    }


def test_observed_skill_capacity_does_not_leak_between_modalities():
    signals = _signals(
        "written_production",
        {"lexical": {"samples": 2, "days": 2, "load": 5}},
    )
    # Ninguna muestra de producción ORAL: no aparece la clave.
    nested = learner_skill.observed_skill_capacity(signals)
    assert "spoken_production" not in nested


def test_observed_capacity_stays_as_the_legacy_projection():
    signals = {
        "observed_samples": {"written_production": {"lexical": 2}},
        "observed_days": {"written_production": {"lexical": 2}},
        "observed_capacity": {"written_production": {"lexical": 3}},
    }
    # La proyección legacy por dimensión se conserva (retrocompatibilidad).
    assert learner_skill.observed_capacity(signals) == {"lexical": 3}


def test_normalize_skill_capacity_accepts_json_and_rejects_garbage():
    nested = {"written_production": {"lexical": 5, "bogus": 9}}
    assert learner_skill.normalize_skill_capacity(json.dumps(nested)) == {
        "written_production": {"lexical": 5}
    }
    assert learner_skill.normalize_skill_capacity(nested) == {
        "written_production": {"lexical": 5}
    }
    assert learner_skill.normalize_skill_capacity("") == {}
    assert learner_skill.normalize_skill_capacity("no-json") == {}
    assert learner_skill.normalize_skill_capacity(None) == {}
    assert learner_skill.normalize_skill_capacity({"written_production": "x"}) == {}


def test_level_from_skill_capacity_requires_full_coverage_per_skill():
    nested = {
        "written_production": {"lexical": 5},  # cobertura parcial: sin nivel
        "spoken_production": difficulty.capacity_for("A2"),  # 4/4: A2
    }
    levels = learner_skill.level_from_skill_capacity(nested)
    assert levels["written_production"] == ""
    assert levels["spoken_production"] == "A2"
    assert learner_skill.level_from_skill_capacity({}) == {}


def test_skill_coverage_counts_canonical_dimensions():
    nested = {
        "a": {"lexical": 3},
        "b": {"lexical": 3, "syntax": 3, "discourse": 3},
        "c": FULL_C2,
    }
    assert learner_skill.skill_coverage(nested) == {
        "a": learner_skill.COVERAGE_PARTIAL,
        "b": learner_skill.COVERAGE_PARTIAL,
        "c": learner_skill.COVERAGE_FULL,
    }
    assert learner_skill.skill_coverage({}) == {}


def test_skill_capacity_reports_coverage_and_never_lowers_the_floor():
    nested = {"written_production": {"lexical": 5}}
    floor = difficulty.capacity_for("B1")
    measured = learner_skill.skill_capacity("B1", nested, "written_production")
    assert measured["coverage"] == learner_skill.COVERAGE_PARTIAL
    assert measured["covered_dimensions"] == ["lexical"]
    assert measured["capacity"]["lexical"] == 5
    # Las dimensiones no observadas conservan el suelo declarado.
    assert measured["capacity"]["syntax"] == floor["syntax"]
    # Un skill sin muestra conserva el suelo declarado y cobertura `none`.
    other = learner_skill.skill_capacity("B1", nested, "spoken_production")
    assert other["coverage"] == learner_skill.COVERAGE_NONE
    assert other["covered_dimensions"] == []
    assert other["capacity"] == floor


def test_observed_skill_state_empty_equals_the_neutral_state():
    assert learner_skill.observed_skill_state({}) == {
        "observed_skill_capacity": {},
        "observed_skill_level": {},
        "skill_coverage": {},
        "observed_level": "",
        "observed_capacity": {},
    }
    assert learner_skill.observed_state(None) == {
        "observed_level": "",
        "observed_capacity": {},
    }


# ------------------------------------------------------------- suelo por skill


def test_floor_level_for_skill_isolates_the_modality():
    # El observado del SKILL (escrito) eleva SOLO la escritura.
    assert student_state.floor_level_for_skill(
        "written_production",
        practice_level="A1",
        estimated_cefr="C1",
        demonstrated_cefr="",
        observed_skill_level={"written_production": "B2"},
        observed_cefr="C2",
    ) == ("B2", "observed")
    # Una modalidad SIN muestra NO hereda el observado global de otra: la
    # producción oral no se eleva por la capacidad escrita.
    assert student_state.floor_level_for_skill(
        "spoken_production",
        practice_level="A1",
        estimated_cefr="C1",
        demonstrated_cefr="",
        observed_skill_level={"written_production": "B2"},
        observed_cefr="C2",
    ) == ("C1", "estimated")


def test_floor_level_for_skill_keeps_demonstrated_and_legacy_fallback():
    # Una certificación sigue ganando a cualquier capacidad observada.
    assert student_state.floor_level_for_skill(
        "written_production",
        demonstrated_cefr="A2",
        observed_skill_level={"written_production": "C2"},
    ) == ("A2", "demonstrated")
    # Caché legacy sin estado por skill: delega en el observado global (V3.53.1).
    assert student_state.floor_level_for_skill(
        "spoken_production",
        practice_level="A1",
        estimated_cefr="C1",
        observed_skill_level={},
        observed_cefr="B2",
    ) == ("B2", "observed")


# ------------------------------------------------------------- gate de cobertura


def test_challenge_for_gates_partial_coverage():
    assert difficulty.challenge_for(
        {"lexical": 5},
        {"lexical": 5},
        covered_dimensions=["lexical"],
    ) == {"lexical": 5}
    # El contexto exige una dimensión NO cubierta: se evalúa contra el suelo.
    assert difficulty.challenge_for(
        {"lexical": 5, "syntax": 5},
        {"lexical": 5},
        covered_dimensions=["lexical"],
        floor_challenge={"lexical": 2},
    ) == {"lexical": 2}
    # Sin gate (cobertura completa o legacy) el reto se devuelve tal cual.
    assert difficulty.challenge_for(
        {"lexical": 5, "syntax": 5},
        {"lexical": 5},
    ) == {"lexical": 5}


def test_select_by_difficulty_only_raises_contexts_inside_the_coverage():
    pool = [
        {"id": "covered", "difficulty_vector": {"lexical": 5}},
        {"id": "wider", "difficulty_vector": {"lexical": 5, "syntax": 5}},
    ]
    gated = difficulty.select_by_difficulty(
        pool,
        {"lexical": 5},
        tolerance=1,
        covered_dimensions=["lexical"],
        floor_challenge={"lexical": 2},
    )
    assert [context["id"] for context in gated] == ["covered"]
    # Sin el gate ambos empatan (el reto elevado aplica a los dos).
    ungated = difficulty.select_by_difficulty(pool, {"lexical": 5}, tolerance=1)
    assert {context["id"] for context in ungated} == {"covered", "wider"}


# ------------------------------------------------------------- integración drill


def test_context_for_does_not_raise_with_another_modality_capacity():
    base = transfer.context_for("travel", level="A2", learner_level="A2")
    # Capacidad de producción ORAL: el transfer mide ESCRITA, así que no eleva.
    spoken = transfer.context_for(
        "travel",
        level="A2",
        learner_level="A2",
        learner_skill_capacity={"spoken_production": FULL_C2},
        capacity_skill="written_production",
    )
    assert spoken["difficulty_fit"]["challenge"] == base["difficulty_fit"]["challenge"]
    # Y la capacidad escrita con cobertura COMPLETA sí eleva el reto.
    raised = transfer.context_for(
        "travel",
        level="A2",
        learner_level="A2",
        learner_skill_capacity={"written_production": FULL_C2},
        capacity_skill="written_production",
    )
    assert raised["difficulty_fit"]["challenge"]["lexical"] == 5
    assert raised["capacity_skill"] == "written_production"


def test_context_for_partial_capacity_does_not_raise_multidimensional_task():
    base = transfer.context_for("travel", level="A2", learner_level="A2")
    # Cobertura PARCIAL (solo léxico): los contextos del banco declaran las 4
    # dimensiones, así que el gate los evalúa contra el suelo declarado.
    partial = transfer.context_for(
        "travel",
        level="A2",
        learner_level="A2",
        learner_skill_capacity={"written_production": {"lexical": 5}},
        capacity_skill="written_production",
    )
    assert partial["difficulty_fit"]["challenge"] == base["difficulty_fit"]["challenge"]
    assert partial["learner_capacity"] == learner_skill.skill_capacity(
        "A2", {"written_production": {"lexical": 5}}, "written_production"
    )["capacity"]


def test_context_for_challenge_without_skill_capacity_is_v353():
    for level in ("A2", "B1", ""):
        base = transfer.context_for("travel", level=level, learner_level="A2")
        nested_empty = transfer.context_for(
            "travel",
            level=level,
            learner_level="A2",
            learner_skill_capacity={},
        )
        assert base["context_id"] == nested_empty["context_id"]
        assert base["difficulty_fit"] == nested_empty["difficulty_fit"]


# ------------------------------------------------------------- persistencia


def test_observed_skill_capacity_column_migration_is_idempotent(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert "observed_skill_capacity" in _columns("learning_profile")
    db.init_db()
    assert "observed_skill_capacity" in _columns("learning_profile")


def test_profile_caches_the_skill_state_for_the_drill(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    vector = difficulty.format_vector(FULL_C2)
    for day in ("2026-09-01", "2026-09-03"):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="travel",
            skill="spontaneous_use",
            assessed_skill="written_production",
            task="transfer",
            activity_id="drill:transfer",
            context_id="transfer:story",
            success=True,
            support_level="spontaneous",
            observed_difficulty=vector,
            occurred_at=f"{day}T10:00:00+00:00",
        )
    asyncio.run(profile_domain.get_profile_summary(uid))
    row = profile_repo.get_profile(uid)
    assert row is not None
    nested = learner_skill.normalize_skill_capacity(row["observed_skill_capacity"])
    assert nested == {"written_production": FULL_C2}
    # El drill lee el JSON en O(1) y deriva el suelo por modalidad.
    state = asyncio.run(vocabulary_domain._learner_level_state(uid))
    assert state["observed_skill_capacity"] == nested
    assert state["floor_level_by_skill"]["written_production"] == "C2"
    # Una modalidad sin evidencia no hereda el nivel observado de la escrita.
    assert state["floor_level_by_skill"]["spoken_production"] != "C2"


def test_get_and_post_share_the_skill_floor(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "travel", cefr="B2")
    profile_repo.set_level_state(
        uid,
        estimated_level="",
        demonstrated_level="",
        observed_level="C2",
        observed_capacity=difficulty.format_vector(FULL_C2),
        observed_skill_capacity=json.dumps({"written_production": FULL_C2}),
    )
    with TestClient(app) as client:
        served = client.get(
            "/api/vocabulary/drill/transfer-context",
            params={"word": "travel", "user_id": uid},
        ).json()
        attempt = client.post(
            "/api/vocabulary/drill/transfer-attempt",
            params={"user_id": uid},
            json={
                "word": "travel",
                "text": "I travel to work by train every single day.",
            },
        ).json()
    assert served["learner_level"] == "C2"
    assert served["capacity_skill"] == "written_production"
    # Paridad GET↔POST: ambos caminos derivan el MISMO contexto.
    assert attempt["context_id"] == served["context_id"]


def test_api_profile_exposes_the_skill_state(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    asyncio.run(profile_domain.get_profile_summary(uid))
    with TestClient(app) as client:
        body = client.get("/api/profile", params={"user_id": uid}).json()
    assert body["observed_skill_capacity"] == {}
    assert body["observed_skill_level"] == {}
    assert body["skill_coverage"] == {}
