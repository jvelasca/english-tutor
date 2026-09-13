"""V3.57 — Planner 3.0: argmax `(skill, actividad)` sobre ELV.

V3.56 convirtió la prioridad en un VALOR ESPERADO de aprendizaje y pasó a ORDENAR
la cola por él, pero la TAREA la seguía eligiendo la cascada de razones
(`planner.select_task`, V3.39). V3.57 cierra esa mitad: entre las tareas
pedagógicamente ADMISIBLES (las que la cascada ya sabe justificar), elige la de
mayor ELV.

    candidatas = razones admisibles hoy (error_prone, skill_gap, slow_recall,
                 transfer_gap)
    ELV(c)     = desirability(P(éxito | canal evaluado)) × skill_priorities[c.skill]
    tarea      = argmax ELV   ← solo con capacidad del alumno

Invariante de no-regresión: sin capacidad (o sin ninguna candidata con margen
comparable) la decisión es EXACTAMENTE `select_task`, así que la tarea servida
hoy sin perfil no cambia. Se cubren además las dos deudas de planner declaradas:
`skill_priorities` → `select_task` y el doble conteo de `written_production`
(política: el EJE manda el valor y el hueco, el CANAL EVALUADO manda la
capacidad).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import evidence as evidence_repo
from repositories import profile as profile_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import difficulty, fsrs, lexicon, planner
from services import evidence as evidence_svc

NOW = "2026-09-13T10:00:00+00:00"
SKILLS = ("recall", "written_production", "spoken_production", "spontaneous_use")


def _signals(**weakness: float) -> dict:
    """Señales con prioridad por modalidad controlable (para aislar el argmax)."""
    skills = {
        skill: {"weakness": value, "support": 0.0, "latency": 0.0}
        for skill, value in weakness.items()
    }
    return {"forgetting": 0.0, "gap": 0.0, "skills": skills}


def _row(**overrides) -> dict:
    row = {
        "word": "river",
        "cefr": "B1",
        "exposure_count": 3,
        "writing_prod": 1,
        "recall_successes": 2,
        "recall_days": 2,
    }
    row.update(overrides)
    return row


def _card(**overrides) -> dict:
    card = {
        "target_id": "river",
        "due_at": "2026-09-12T10:00:00+00:00",
        "state": "review",
        "stability": 5.0,
        "last_review_at": "2026-09-09T10:00:00+00:00",
    }
    card.update(overrides)
    return card


def _learner_state(*, floor: str = "", observed: dict | None = None) -> dict:
    """Estado del alumno con la MISMA forma que `learner_level_state`."""
    return {
        "floor_level": floor,
        "floor_source": "estimated" if floor else "none",
        "floor_level_by_skill": {skill: floor for skill in SKILLS},
        "floor_source_by_skill": {
            skill: ("estimated" if floor else "none") for skill in SKILLS
        },
        "observed_skill_capacity": observed or {},
    }


PRODUCTION_EVIDENCE = {
    "error_types": {"wrong_word": 2},
    "skill_successes": {"recall": 2, "spoken_production": 2},
}


# ------------------------------------------------------------ canal evaluado


def test_capacity_skill_maps_the_axis_to_the_assessed_channel():
    # El transfer se ENTREGA por texto: su eje es `spontaneous_use`, pero lo que
    # MIDE es producción escrita. Sin esta separación, `write` y `transfer`
    # contarían la misma capacidad dos veces.
    assert planner.capacity_skill("spontaneous_use") == "written_production"
    assert planner.capacity_skill("written_production") == "written_production"
    assert planner.capacity_skill("spoken_production") == "spoken_production"
    assert planner.capacity_skill("recall") == "recall"


def test_capacity_skill_falls_back_to_the_axis_and_never_raises():
    # Una modalidad desconocida NO inventa canal: cae al propio eje.
    assert planner.capacity_skill("nope") == "nope"
    assert planner.capacity_skill("") == ""
    assert planner.capacity_skill(None) == ""
    assert planner.capacity_skill(123) == "123"


# ------------------------------------------------------------- candidatas


def test_task_candidates_require_an_admissible_reason():
    # Sin evidencia no hay directriz: la escalera de V3.35 decide.
    assert planner.task_candidates({}, {}) == []
    assert planner.task_candidates(None, None) == []
    # `error_prone` → recall.
    recall = planner.task_candidates(
        {"production": True}, {"error_types": {"wrong_word": 2}}
    )
    assert recall == [
        {
            "skill": "recall",
            "activity": "recall",
            "reason": "error_prone",
            "support_level": "cued",
        }
    ]
    # `slow_recall` → recall (misma tarea, otra razón).
    slow = planner.task_candidates(
        {"production": True},
        {
            "skill_successes": {"recall": 1},
            "skill_mean_response_time_ms": {"recall": 12000},
        },
    )
    assert slow[0]["reason"] == "slow_recall"


def test_task_candidates_order_production_gaps_spoken_first():
    # Hueco oral y escrito a la vez: el orden canónico pone primero el oral, que
    # es la preferencia histórica de V3.38.1 (`directed_production_gap`).
    candidates = planner.task_candidates(
        {"production": True}, {"skill_successes": {"recall": 1}}
    )
    assert [candidate["activity"] for candidate in candidates] == [
        "sentence",
        "write",
    ]
    assert [candidate["reason"] for candidate in candidates] == [
        "skill_gap",
        "skill_gap",
    ]
    # Sin `production` declarado en la matriz no hay hueco accionable.
    assert planner.task_candidates({}, {"skill_successes": {"recall": 1}}) == []


def test_task_candidates_include_transfer_only_with_its_own_gate():
    evidence = {
        "skill_successes": {"recall": 1},
        "contexts": {"c1": {"successes": 2}},
        "context_attempts": 2,
        "transfer_state": "emerging",
    }
    candidates = planner.task_candidates({"production": True}, evidence)
    assert "spontaneous_use" in [candidate["skill"] for candidate in candidates]


def test_task_candidates_never_raise_on_garbage():
    garbage = {
        "skill_successes": ["recall"],
        "error_types": 3,
        "skill_mean_response_time_ms": "slow",
    }
    assert planner.task_candidates(None, garbage) == []
    assert planner.task_candidates("nope", garbage) == []
    # Basura en el ledger: no se inventa hueco, el planner nunca rompe la cola.
    assert planner.task_candidates({"production": True}, garbage) == []


# ------------------------------------------- degradación neutra EXACTA


NO_STATE_CASES = [
    (None, None),
    ({}, {}),
    ({"production": True}, {}),
    ({"production": True}, {"error_types": {"wrong_word": 2}}),
    ({"production": True}, {"skill_successes": {"recall": 1}}),
    ({"production": True}, {"skill_successes": {"recall": 1, "spoken_production": 1}}),
    ({"production": True}, PRODUCTION_EVIDENCE),
]


@pytest.mark.parametrize("matrix,evidence", NO_STATE_CASES)
def test_select_task_by_elv_without_capacity_is_exactly_select_task(matrix, evidence):
    signals = planner.planned_signals(evidence, matrix)
    expected = planner.select_task(matrix, evidence, signals)
    assert (
        planner.select_task_by_elv(matrix, evidence, signals) == expected
    )
    assert (
        planner.select_task_by_elv(
            matrix, evidence, signals, capacity_by_skill={}
        )
        == expected
    )


def test_select_task_by_elv_without_comparable_margin_falls_back():
    matrix = {"production": True}
    evidence = {"error_types": {"wrong_word": 2}}
    signals = planner.planned_signals(evidence, matrix)
    # Capacidad de OTRA modalidad: la única candidata (recall) no tiene margen
    # comparable, así que no compite y la decisión cae a la cascada.
    fallback = planner.select_task_by_elv(
        matrix,
        evidence,
        signals,
        capacity_by_skill={"written_production": {"lexical": 5}},
    )
    assert fallback == planner.select_task(matrix, evidence, signals)


# ----------------------------------------------------------------- argmax


def test_select_task_by_elv_prefers_the_desirable_difficulty():
    matrix = {"production": True}
    evidence = PRODUCTION_EVIDENCE
    signals = _signals(recall=0.5, written_production=0.5)
    difficulty_vector = {"lexical": 3}
    # Recall por ENCIMA de la capacidad (margen -2) vs escritura en la ZONA
    # (margen 0): gana la escritura aunque su prioridad no sea mayor.
    chosen = planner.select_task_by_elv(
        matrix,
        evidence,
        signals,
        capacity_by_skill={
            "recall": {"lexical": 1},
            "written_production": {"lexical": 3},
        },
        task_difficulty=difficulty_vector,
    )
    assert chosen["skill"] == "written_production"
    assert chosen["activity"] == "write"
    # Simétrico: con el recall en la zona, la escritura por encima pierde.
    chosen = planner.select_task_by_elv(
        matrix,
        evidence,
        signals,
        capacity_by_skill={
            "recall": {"lexical": 3},
            "written_production": {"lexical": 1},
        },
        task_difficulty=difficulty_vector,
    )
    assert chosen["skill"] == "recall"
    assert chosen["activity"] == "recall"


def test_select_task_by_elv_uses_the_per_skill_priority_as_value():
    # Deuda 1: `skill_priorities` alimenta la decisión. Con capacidades idénticas
    # (misma deseabilidad), el valor por modalidad decide; el empate lo rompe el
    # orden canónico (oral antes que escrita).
    matrix = {"production": True}
    evidence = {"skill_successes": {"recall": 2}}
    capacity = {
        "spoken_production": {"lexical": 3},
        "written_production": {"lexical": 3},
    }
    tie = planner.select_task_by_elv(
        matrix,
        evidence,
        _signals(spoken_production=0.5, written_production=0.5),
        capacity_by_skill=capacity,
        task_difficulty={"lexical": 3},
    )
    assert tie["activity"] == "sentence"
    win = planner.select_task_by_elv(
        matrix,
        evidence,
        _signals(spoken_production=0.1, written_production=0.9),
        capacity_by_skill=capacity,
        task_difficulty={"lexical": 3},
    )
    assert win["activity"] == "write"
    assert win["skill"] == "written_production"


# --------------------------------------------------- doble conteo (deuda 2)


def test_transfer_success_feeds_capacity_but_not_the_written_axis_priority():
    rows = [
        {
            "success": True,
            "skill": "spontaneous_use",
            "assessed_skill": "written_production",
            "served_difficulty": "lexical:3",
            "observed_task_difficulty": "lexical:3",
            "support_level": "spontaneous",
            "occurred_at": "2026-09-10T10:00:00+00:00",
        }
    ]
    # El CANAL evaluado acredita la capacidad de producción escrita...
    capacity = evidence_svc.observed_signals(rows)["observed_capacity"]
    assert capacity == {"written_production": {"lexical": 3}}
    assert "spontaneous_use" not in capacity
    # ...y el EJE conserva la segmentación histórica: el éxito NO se cuenta
    # también como `written_production`, de modo que su prioridad no se infla.
    summary = evidence_svc.summarize_evidence(rows)
    assert summary["skill_successes"] == {"spontaneous_use": 1}
    assert summary["assessed_skill_successes"] == {"written_production": 1}


def test_capacity_skill_reads_the_same_written_capacity_for_write_and_transfer():
    signals = planner.planned_signals({}, {})
    capacity = {"written_production": {"lexical": 3}}
    difficulty_vector = {"lexical": 3}
    for axis in ("written_production", "spontaneous_use"):
        payload = planner.expected_learning_value(
            signals,
            skill=axis,
            task_difficulty=difficulty_vector,
            learner_capacity=capacity[planner.capacity_skill(axis)],
            capacity_skill=planner.capacity_skill(axis),
        )
        assert payload["capacity_skill"] == "written_production"
        assert payload["margin"] == 0


# ------------------------------------------------------- ítem de cola


def test_learning_value_reports_the_capacity_skill_without_state():
    item = lexicon.review_queue_item(_row(), _card(), now=NOW, evidence={})
    # Sin estado la predicción es neutra: se declara el CANAL del eje de la tarea
    # (informativo) pero no hay margen ni descuento por deseabilidad.
    assert item["learning_value"]["capacity_skill"] == "recall"
    assert item["learning_value"]["margin"] is None
    assert item["expected_learning_value"] == item["priority"]


def test_review_queue_item_without_state_keeps_the_cascade_task():
    item = lexicon.review_queue_item(
        _row(), _card(), now=NOW, evidence=PRODUCTION_EVIDENCE
    )
    assert item["task"]["reason"] == "error_prone"
    assert item["task"]["activity"] == "recall"
    assert item["task"]["activity"] == item["activity"]


def test_review_queue_item_uses_the_argmax_with_learner_state():
    baseline = lexicon.review_queue_item(
        _row(), _card(), now=NOW, evidence=PRODUCTION_EVIDENCE
    )
    assert baseline["task"]["activity"] == "recall"
    tuned = lexicon.review_queue_item(
        _row(),
        _card(),
        now=NOW,
        evidence=PRODUCTION_EVIDENCE,
        learner_state=_learner_state(
            observed={
                # Recall por encima de la capacidad; escritura en la zona.
                "recall": {"lexical": 1},
                "written_production": {"lexical": 3},
            }
        ),
    )
    assert tuned["task"]["activity"] == "write"
    assert tuned["task"]["reason"] == "skill_gap"
    # La actividad del ítem y su `task` NO pueden divergir (V3.39).
    assert tuned["task"]["activity"] == tuned["activity"]
    assert tuned["learning_value"]["capacity_skill"] == "written_production"
    assert tuned["learning_value"]["margin"] == 0


# ------------------------------------------------------------------- HTTP


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _due_lexicon_card(uid: str, word: str, *, stability: float, days_ago: int) -> None:
    now = datetime.now(timezone.utc)
    card = {
        **fsrs.empty_card(target_type="lexicon", target_id=word, label=word),
        "state": "review",
        "reps": 2,
        "stability": stability,
        "due_at": (now - timedelta(days=1)).isoformat(),
        "last_review_at": (now - timedelta(days=days_ago)).isoformat(),
        "last_grade": fsrs.GRADE_GOOD,
    }
    assert academy_repo.upsert_fsrs_card(uid, card) is not None


def _seed_word(uid: str, word: str, *, cefr: str = "B1") -> None:
    """Siembra la palabra en el léxico con su CEFR (dificultad declarada)."""
    vocabulary_repo.seed_curriculum_items(
        uid,
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
    vocabulary_repo.record_exposures(uid, [word])


def test_http_queue_with_profile_picks_the_task_by_elv(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    # La caché del Student Model declara el recall observado MUY por encima del
    # ítem (léxico 5 vs B1 = 3); la escritura se queda en el suelo A2.
    profile_repo.set_level_state(
        uid,
        estimated_level="",
        demonstrated_level="A2",
        observed_skill_capacity=json.dumps({"recall": {"lexical": 5}}),
    )
    _seed_word(uid, "river", cefr="B1")
    vocabulary_repo.record_production(uid, ["river"], channel="writing")
    vocabulary_repo.record_recalls(uid, ["river"])
    for _ in range(2):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            skill="recall",
            success=False,
            error_type="wrong_word",
        )
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        skill="spoken_production",
        success=True,
        support_level="independent",
    )
    _due_lexicon_card(uid, "river", stability=5.0, days_ago=3)

    with TestClient(app) as client:
        body = client.get("/api/learning/review", params={"user_id": uid}).json()

    item = body["items"][0]
    assert item["task"]["activity"] == "write"
    assert item["task"]["activity"] == item["activity"]
    assert item["task"]["reason"] == item["reason"]
    assert item["learning_value"]["capacity_skill"] == "written_production"
    assert item["learning_value"]["margin"] == -1


def test_http_queue_without_profile_keeps_the_cascade(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    _seed_word(uid, "river", cefr="B1")
    vocabulary_repo.record_production(uid, ["river"], channel="writing")
    vocabulary_repo.record_recalls(uid, ["river"])
    for _ in range(2):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            skill="recall",
            success=False,
            error_type="wrong_word",
        )
    evidence_repo.record_evidence(
        uid,
        target_type="lexicon",
        target_id="river",
        skill="spoken_production",
        success=True,
        support_level="independent",
    )
    _due_lexicon_card(uid, "river", stability=5.0, days_ago=3)

    with TestClient(app) as client:
        body = client.get("/api/learning/review", params={"user_id": uid}).json()

    item = body["items"][0]
    assert item["task"]["activity"] == "recall"
    assert item["task"]["reason"] == "error_prone"
    assert item["learning_value"]["capacity_skill"] == "recall"
    assert item["learning_value"]["margin"] is None


def test_declared_difficulty_is_the_lexical_vector_of_the_item():
    # El argmax compara TODAS las candidatas contra la MISMA dificultad declarada
    # del ítem (`difficulty.declared_difficulty`), en su única dimensión léxica.
    assert difficulty.declared_difficulty(lexicon.cefr_difficulty(_row())) == {
        "lexical": 3
    }
