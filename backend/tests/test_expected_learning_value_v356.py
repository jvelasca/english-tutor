"""V3.56 — Planner 2.0: valor esperado de aprendizaje (`expected_learning_value`).

El planner de V3.38–V3.55 sabía cuánto URGE repasar algo (suma ponderada de
olvido, hueco, debilidad, apoyo y latencia) pero NO predecía si el alumno podrá
con la tarea. V3.56 añade las dos mitades que faltaban:

    P(éxito)   ← margen entre la dificultad declarada de la TAREA y la capacidad
                 del alumno en la MODALIDAD que la tarea evalúa;
    V(valor)   ← el `priority_score` ya existente (mismos pesos declarados);
    ELV        = dificultad_deseable(P) × V   (máximo en P ≈ 0.5).

Se cubre el núcleo puro (tabla `SUCCESS_BY_MARGIN` declarada y acotada, mínimo
por dimensión comparable, degradación neutra exacta en `p = 0.5`), el cableado
en el ítem de cola (`expected_learning_value`/`learning_value` aditivos), el
orden de la cola por ELV con `priority` como primer desempate y la NO-regresión
exhaustiva del orden sin estado del alumno (`ELV == priority`, misma secuencia
que V3.55.0).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from domain import learner_state as learner_state_domain
from domain import review as review_domain
from domain import vocabulary as vocabulary_domain
from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import profile as profile_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs, lexicon, planner

NOW = "2026-09-13T10:00:00+00:00"
SKILLS = (
    "recall",
    "written_production",
    "spoken_production",
    "spontaneous_use",
)


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


def _row(**overrides) -> dict:
    row = {
        "word": "river",
        "cefr": "B1",
        "exposure_count": 3,
        "production_count": 1,
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


FULL_C2 = {
    "lexical": 5,
    "syntax": 5,
    "discourse": 5,
    "interaction": 5,
}


# --------------------------------------------------------------- núcleo puro


def test_success_probability_table_is_monotone_and_bounded():
    margins = sorted(planner.SUCCESS_BY_MARGIN)
    values = [planner.SUCCESS_BY_MARGIN[margin] for margin in margins]
    assert values == sorted(values), "la tabla debe ser monótona no decreciente"
    assert all(0.0 < value < 1.0 for value in values)
    assert planner.P_SUCCESS_UNKNOWN == 0.5
    assert planner.success_probability(None) == 0.5


def test_success_probability_clamps_out_of_range_and_never_raises():
    low = planner.SUCCESS_BY_MARGIN[min(planner.SUCCESS_BY_MARGIN)]
    high = planner.SUCCESS_BY_MARGIN[max(planner.SUCCESS_BY_MARGIN)]
    assert planner.success_probability(-99) == low
    assert planner.success_probability(99) == high
    # Entradas no numéricas (incluido bool-as-int) degradan al neutro.
    assert planner.success_probability("nope") == 0.5
    assert planner.success_probability(True) == 0.5


def test_desirability_peaks_at_half_and_is_zero_at_extremes():
    assert planner.desirability(0.5) == 1.0
    assert planner.desirability(0.0) == 0.0
    assert planner.desirability(1.0) == 0.0
    assert planner.desirability(0.55) == 0.99
    assert planner.desirability(0.15) == 0.51
    assert planner.desirability(0.9) == 0.36


def test_capacity_margin_is_the_minimum_of_comparable_dimensions():
    assert (
        planner.capacity_margin(
            {"lexical": 3, "syntax": 2}, {"lexical": 4, "syntax": 2}
        )
        == 0
    )
    assert planner.capacity_margin({"lexical": 3}, {"lexical": 5}) == 2
    assert planner.capacity_margin({"lexical": 5}, {"lexical": 4}) == -1


def test_capacity_margin_ignores_dimensions_without_capacity():
    # Una dimensión declarada por la tarea pero ausente en la capacidad NO se
    # cuenta como 0: no se inventa un margen negativo sin evidencia.
    assert planner.capacity_margin({"lexical": 3, "discourse": 5}, {"lexical": 4}) == 1


def test_capacity_margin_is_none_without_comparable_dimensions():
    assert planner.capacity_margin({}, {"lexical": 3}) is None
    assert planner.capacity_margin({"lexical": 3}, {}) is None
    assert planner.capacity_margin({"lexical": 3}, {"syntax": 5}) is None
    assert planner.capacity_margin(None, None) is None


def test_expected_learning_value_degrades_to_priority_without_state():
    signals = {
        "forgetting": 1.0,
        "gap": 1.0,
        "weakness": 1.0,
        "support": 0.0,
        "latency": 0.0,
    }
    payload = planner.expected_learning_value(signals)
    assert payload["margin"] is None
    assert payload["p_success"] == planner.P_SUCCESS_UNKNOWN
    assert payload["desirability"] == 1.0
    assert payload["value"] == planner.priority_score(signals)
    assert payload["expected_learning_value"] == payload["value"]
    assert payload["skill"] == ""


def test_expected_learning_value_combines_desirability_and_value():
    signals = {"forgetting": 1.0}
    payload = planner.expected_learning_value(
        signals,
        skill="recall",
        task_difficulty={"lexical": 3},
        learner_capacity={"lexical": 1},
    )
    assert payload["skill"] == "recall"
    assert payload["margin"] == -2
    assert payload["p_success"] == 0.15
    assert payload["desirability"] == 0.51
    assert payload["expected_learning_value"] == round(0.51 * payload["value"], 4)


def test_expected_learning_value_prefers_the_desirable_difficulty():
    signals = {"forgetting": 1.0}
    near = planner.expected_learning_value(
        signals, task_difficulty={"lexical": 3}, learner_capacity={"lexical": 3}
    )
    hard = planner.expected_learning_value(
        signals, task_difficulty={"lexical": 3}, learner_capacity={"lexical": 1}
    )
    easy = planner.expected_learning_value(
        signals, task_difficulty={"lexical": 3}, learner_capacity={"lexical": 5}
    )
    assert near["expected_learning_value"] > hard["expected_learning_value"]
    assert near["expected_learning_value"] > easy["expected_learning_value"]


# --------------------------------------------- ítem de cola (cableado)


def test_review_queue_item_without_learner_state_keeps_v355_values():
    item = lexicon.review_queue_item(_row(), _card(), now=NOW, evidence={})
    assert item["expected_learning_value"] == item["priority"]
    assert item["learning_value"]["margin"] is None
    assert item["learning_value"]["p_success"] == 0.5
    assert item["learning_value"]["desirability"] == 1.0
    assert item["learning_value"]["expected_learning_value"] == item["priority"]


def test_review_queue_item_predicts_with_the_skill_floor():
    without = lexicon.review_queue_item(_row(), _card(), now=NOW, evidence={})
    with_state = lexicon.review_queue_item(
        _row(),
        _card(),
        now=NOW,
        evidence={},
        learner_state=_learner_state(floor="C1"),
    )
    # El ítem declara `lexical` B1 (3) y el suelo C1 tiene léxico 4 → margen 1.
    assert with_state["learning_value"]["margin"] == 1
    assert with_state["learning_value"]["p_success"] == 0.75
    assert with_state["learning_value"]["desirability"] == 0.75
    assert with_state["learning_value"]["expected_learning_value"] == round(
        0.75 * with_state["priority"], 4
    )
    # El estado del alumno NO cambia la prioridad previa ni el resto del payload.
    assert with_state["priority"] == without["priority"]
    assert with_state["task"] == without["task"]


def test_observed_capacity_raises_the_success_probability():
    declared = lexicon.review_queue_item(
        _row(),
        _card(),
        now=NOW,
        evidence={},
        learner_state=_learner_state(floor="A2"),
    )
    observed = lexicon.review_queue_item(
        _row(),
        _card(),
        now=NOW,
        evidence={},
        learner_state=_learner_state(
            floor="A2",
            observed={skill: dict(FULL_C2) for skill in SKILLS},
        ),
    )
    assert (
        observed["learning_value"]["margin"] > declared["learning_value"]["margin"]
    )
    assert (
        observed["learning_value"]["p_success"]
        > declared["learning_value"]["p_success"]
    )


def test_explain_priority_adds_capacity_phrases_only_when_predicted():
    signals = {"forgetting": 1.0}
    assert "expected success" not in planner.explain_priority(signals, "maintenance")

    above = planner.expected_learning_value(
        signals, task_difficulty={"lexical": 3}, learner_capacity={"lexical": 1}
    )
    assert "above your observed capacity" in planner.explain_priority(
        signals, "maintenance", above
    )

    near = planner.expected_learning_value(
        signals, task_difficulty={"lexical": 3}, learner_capacity={"lexical": 3}
    )
    assert "challenging but achievable (about 55% expected success)" in (
        planner.explain_priority(signals, "maintenance", near)
    )

    within = planner.expected_learning_value(
        signals, task_difficulty={"lexical": 3}, learner_capacity={"lexical": 5}
    )
    assert "well within your observed capacity" in planner.explain_priority(
        signals, "maintenance", within
    )


# --------------------------------------------------------------- orden


def test_queue_sort_key_orders_by_elv_then_priority():
    # Mismo `priority` (mismas señales) y distinto MARGEN de capacidad:
    # margen 0 (p ≈ 0.55, deseabilidad ≈ 0.99) → margen −2 (0.51) → margen +2 (0.36).
    signals = {"forgetting": 1.0}
    priority = planner.priority_score(signals)
    items = [
        {
            "word": word,
            "priority": priority,
            "expected_learning_value": planner.expected_learning_value(
                signals,
                task_difficulty={"lexical": 3},
                learner_capacity={"lexical": capacity},
            )["expected_learning_value"],
            "retrievability": 0.5,
        }
        for word, capacity in (("near", 3), ("over", 1), ("far", 5))
    ]
    ordered = sorted(items, key=review_domain._queue_sort_key)
    assert [item["word"] for item in ordered] == ["near", "over", "far"]


def test_queue_sort_key_falls_back_to_priority_then_scheduler_then_word():
    items = [
        {
            "word": "b",
            "priority": 0.4,
            "expected_learning_value": 0.4,
            "retrievability": 0.1,
        },
        {
            "word": "a",
            "priority": 0.4,
            "expected_learning_value": 0.4,
            "retrievability": 0.1,
        },
        {
            "word": "c",
            "priority": 0.4,
            "expected_learning_value": 0.4,
            "retrievability": 0.2,
        },
        {
            "word": "d",
            "priority": 0.6,
            "expected_learning_value": 0.4,
            "retrievability": 1.0,
        },
    ]
    ordered = sorted(items, key=review_domain._queue_sort_key)
    assert [item["word"] for item in ordered] == ["d", "a", "b", "c"]


def test_queue_sort_key_legacy_item_without_elv_uses_priority():
    legacy = {"word": "x", "priority": 0.9, "retrievability": 1.0}
    other = {
        "word": "y",
        "priority": 0.1,
        "expected_learning_value": 0.1,
        "retrievability": 1.0,
    }
    ordered = sorted([other, legacy], key=review_domain._queue_sort_key)
    assert ordered[0]["word"] == "x"


# ----------------------------------------------------------- estado del alumno


def test_learner_state_read_has_a_single_implementation(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    profile_repo.set_level_state(uid, estimated_level="B1", demonstrated_level="")
    direct = asyncio.run(learner_state_domain.learner_level_state(uid))
    delegated = asyncio.run(vocabulary_domain._learner_level_state(uid))
    assert delegated == direct


# ----------------------------------------------------------------- HTTP


def test_http_queue_without_profile_keeps_v355_order(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(uid, ["urgent", "calm"])
    _due_lexicon_card(uid, "urgent", stability=1.0, days_ago=12)
    _due_lexicon_card(uid, "calm", stability=30.0, days_ago=1)

    with TestClient(app) as client:
        body = client.get(
            "/api/learning/review", params={"user_id": uid}
        ).json()

    assert [item["word"] for item in body["items"]][:2] == ["urgent", "calm"]
    for item in body["items"]:
        assert item["expected_learning_value"] == item["priority"]
        assert item["learning_value"]["margin"] is None
        assert item["learning_value"]["p_success"] == 0.5


def test_http_queue_with_profile_serves_the_learning_value(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    profile_repo.set_level_state(uid, estimated_level="C1", demonstrated_level="")
    _seed_word(uid, "river", cefr="B1")
    _due_lexicon_card(uid, "river", stability=5.0, days_ago=3)

    with TestClient(app) as client:
        body = client.get(
            "/api/learning/review", params={"user_id": uid}
        ).json()

    assert body["due_count"] == 1
    item = body["items"][0]
    assert item["learning_value"]["margin"] == 1
    assert item["learning_value"]["expected_learning_value"] == item[
        "expected_learning_value"
    ]
    assert item["expected_learning_value"] > 0.0
    assert item["why"]
