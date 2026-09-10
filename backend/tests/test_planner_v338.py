"""Tests de V3.38 — planner: la siguiente tarea óptima.

V3.35-V3.37 construyeron la evidencia; V3.38 la USA para planificar. Se cubren:

- las señales puras (`planned_signals`) y la prioridad ponderada
  (`priority_score`), explicables y acotadas;
- las razones ADITIVAS dirigidas por la evidencia (`error_prone`, `skill_gap`,
  `slow_recall`), que no sustituyen a las de hueco de V3.35;
- la exposición aditiva en la cola de repaso (`priority`/`signals`/`why`/
  `automatic_skills`) y su orden por tarea óptima.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import evidence as evidence_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs, lexicon, planner


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _due_lexicon_card(uid: str, word: str, *, stability: float, days_ago: int):
    from datetime import datetime, timedelta, timezone

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


def _recalled_row(**overrides) -> dict:
    row = {
        "word": "river",
        "exposure_count": 3,
        "exposure_days": 2,
        "production_count": 1,
        "production_days": 1,
        "speaking_prod": 1,
        "recall_successes": 2,
        "recall_days": 2,
    }
    row.update(overrides)
    return row


def _card(**overrides) -> dict:
    card = {
        "target_id": "river",
        "due_at": "2026-09-09T10:00:00+00:00",
        "state": "review",
        "stability": 5.0,
        "last_review_at": "2026-09-06T10:00:00+00:00",
    }
    card.update(overrides)
    return card


# --- Señales y prioridad ----------------------------------------------------


def test_planned_signals_reads_the_evidence_dimensions():
    evidence = {
        "attempts": 4,
        "successes": 2,
        "success_rate": 0.5,
        "independent_successes": 1,
        "mean_response_time_ms": 10000.0,
        # V3.38.1 (P1-02): la fluidez se lee por modalidad (recall), no de la
        # media global.
        "skill_successes": {"recall": 2},
        "skill_attempts": {"recall": 3},
        "skill_mean_response_time_ms": {"recall": 10000.0},
    }
    signals = planner.planned_signals(
        evidence, {"production_gap": True}, retrievability=0.25
    )
    assert signals["forgetting"] == 0.75
    assert signals["gap"] == 1.0
    assert signals["weakness"] == 0.5
    # 1 de 2 éxitos fue independiente → la otra mitad dependió de apoyo.
    assert signals["support"] == 0.5
    assert signals["latency"] == 0.5
    assert signals["slow_recall"] is True
    # Segmentación por modalidad (nueva en V3.38.1).
    assert signals["skills"]["recall"]["attempts"] == 3
    assert signals["skills"]["recall"]["successes"] == 2
    assert signals["skills"]["recall"]["latency"] == 0.5
    assert signals["skills"]["spoken_production"]["attempts"] == 0


def test_planned_signals_without_evidence_is_all_zero():
    signals = planner.planned_signals(None, None)
    assert signals["forgetting"] == 0.0
    assert signals["gap"] == 0.0
    assert signals["weakness"] == 0.0
    assert signals["support"] == 0.0
    assert signals["latency"] == 0.0
    assert planner.priority_score(signals) == 0.0


def test_priority_score_is_bounded_and_weighted():
    assert planner.priority_score({}) == 0.0
    assert planner.priority_score({"forgetting": 1.0}) == 0.35
    assert planner.priority_score({"gap": 1.0, "weakness": 1.0}) == 0.5
    # Nunca supera 1 aunque las señales vengan fuera de rango.
    assert (
        planner.priority_score(
            {
                "forgetting": 5.0,
                "gap": 5.0,
                "weakness": 5.0,
                "support": 5.0,
                "latency": 5.0,
            }
        )
        == 1.0
    )


def test_transfer_gap_weighs_less_than_production_gap():
    production = planner.planned_signals({}, {"production_gap": True})
    transfer = planner.planned_signals({}, {"transfer_gap": True})
    assert production["gap"] == 1.0
    assert transfer["gap"] == 0.5


# --- Razones dirigidas por la evidencia -------------------------------------


def test_error_prone_requires_repeated_wrong_word_not_typos():
    assert planner.error_prone({"error_types": {"wrong_word": 1}}) is False
    # Una errata dice que el alumno SABE la palabra: no es "error_prone".
    assert planner.error_prone({"error_types": {"orthographic_error": 3}}) is False
    assert planner.error_prone({"error_types": {"wrong_word": 2}}) is True
    assert planner.error_prone({}) is False


def test_skill_gap_needs_production_and_no_production_modality():
    recall_only = {"skill_successes": {"recall": 2}}
    assert planner.skill_gaps(recall_only) == [
        "written_production",
        "spoken_production",
    ]
    assert planner.has_production_evidence(recall_only) is False
    with_production = {
        "skill_successes": {"recall": 2, "spoken_production": 1},
    }
    assert planner.has_production_evidence(with_production) is True
    # Sin ningún éxito no hay nada que transferir.
    assert planner.skill_gaps({}) == []


def test_slow_recall_needs_measured_latency_and_a_success():
    # V3.38.1 (P1-02): la señal es la latencia DE RECALL, no la media global.
    slow = {
        "skill_successes": {"recall": 1},
        "skill_mean_response_time_ms": {"recall": 12000},
    }
    fast = {
        "skill_successes": {"recall": 1},
        "skill_mean_response_time_ms": {"recall": 3000},
    }
    assert planner.is_slow_recall(slow) is True
    assert planner.is_slow_recall(fast) is False
    # La latencia de un fallo mide dificultad, no fluidez.
    failed = {
        "skill_successes": {"recall": 0},
        "successes": 0,
        "skill_mean_response_time_ms": {"recall": 20000},
    }
    assert planner.is_slow_recall(failed) is False
    # Sin latencia de recall medida no hay señal (aunque haya latencia global).
    assert (
        planner.is_slow_recall({"successes": 1, "mean_response_time_ms": 20000})
        is False
    )
    # Una producción oral lenta NO hace lento el recall (mezcla de modalidades).
    speaking_slow = {
        "skill_successes": {"recall": 2},
        "skill_mean_response_time_ms": {"recall": 2000, "spoken_production": 15000},
    }
    assert planner.is_slow_recall(speaking_slow) is False


def test_evidence_reason_has_a_declared_priority_order():
    matrix = {"production": True}
    both = {
        "error_types": {"wrong_word": 2},
        "skill_successes": {"recall": 2},
        "successes": 1,
        "mean_response_time_ms": 15000,
    }
    # La confusión real manda sobre el hueco de modalidad y la fluidez.
    assert planner.evidence_reason(matrix, both) == "error_prone"
    assert (
        planner.evidence_reason(matrix, {"skill_successes": {"recall": 1}})
        == "skill_gap"
    )
    assert (
        planner.evidence_reason(
            {},
            {
                "skill_successes": {"recall": 2},
                "skill_mean_response_time_ms": {"recall": 9000},
            },
        )
        == "slow_recall"
    )
    assert planner.evidence_reason({}, {}) == ""


def test_skill_gap_targets_the_partial_production_hole():
    """V3.38.1 (P1-03): `written ✓ / spoken ✗` es un hueco accionable."""
    matrix = {"production": True}
    partial = {"skill_successes": {"recall": 2, "written_production": 3}}
    assert planner.skill_gaps(partial) == ["spoken_production"]
    assert planner.evidence_reason(matrix, partial) == "skill_gap"
    # El hueco simétrico (falta escritura) se expone pero no emite razón: la
    # cola no tiene todavía un drill de escritura (V3.39).
    written_missing = {"skill_successes": {"recall": 2, "spoken_production": 3}}
    assert planner.skill_gaps(written_missing) == ["written_production"]
    assert planner.evidence_reason(matrix, written_missing) == ""


def test_evidence_reason_never_breaks_on_partial_data():
    matrix = {"production": True}
    assert planner.evidence_reason(matrix, {"error_types": "nope"}) == ""
    assert planner.evidence_reason(matrix, {"skill_successes": "nope"}) == ""


# --- Integración con la decisión de actividad -------------------------------


def test_recommend_review_activity_prefers_evidence_reasons():
    # Sin producción → `production_gap` (razón de hueco de V3.35, intacta).
    row = _recalled_row(production_count=0, speaking_prod=0)
    assert lexicon.recommend_review_activity(row)["reason"] == "production_gap"
    # Con producción y confusión real, la evidencia manda.
    produced = _recalled_row()
    assert (
        lexicon.recommend_review_activity(
            produced, evidence={"error_types": {"wrong_word": 2}}
        )["reason"]
        == "error_prone"
    )
    assert (
        lexicon.recommend_review_activity(
            produced, evidence={"skill_successes": {"recall": 2}}
        )["reason"]
        == "skill_gap"
    )
    assert (
        lexicon.recommend_review_activity(
            produced,
            evidence={
                # Producción oral cubierta (sin hueco de modalidad) + recall lento.
                "skill_successes": {"recall": 1, "spoken_production": 1},
                "skill_mean_response_time_ms": {"recall": 12000},
            },
        )["reason"]
        == "slow_recall"
    )


def test_recommend_review_activity_keeps_v335_reasons_without_new_data():
    produced = _recalled_row()
    assert lexicon.recommend_review_activity(produced)["reason"] == "maintenance"
    assert (
        lexicon.recommend_review_activity(
            produced,
            evidence={
                # V3.38.1 (P1-04): automaticidad robusta.
                "independent_successes": 3,
                "independent_success_days": 3,
                "successes": 3,
                "attempts": 3,
                "success_rate": 1.0,
            },
        )["reason"]
        == "automatic_maintenance"
    )


def test_review_queue_item_exposes_the_planner_fields():
    item = lexicon.review_queue_item(
        _recalled_row(),
        _card(),
        now="2026-09-09T10:00:00+00:00",
        evidence={
            "attempts": 4,
            "successes": 2,
            "success_rate": 0.5,
            "skill_successes": {"recall": 2},
        },
        available_cues={"translation"},
    )
    assert item["reason"] == "skill_gap"
    assert item["activity"] == "sentence"
    assert item["priority"] > 0
    assert item["signals"]["gap"] >= 0.5
    assert item["signals"]["skill_gaps"] == [
        "written_production",
        "spoken_production",
    ]
    assert "no success yet in" in item["why"]
    assert item["automatic_skills"] == []


# --- Cola HTTP: orden por tarea óptima --------------------------------------


def test_review_queue_orders_by_priority(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    # `gap`: reconocida y sin producir → hueco de producción (gap = 1.0).
    vocabulary_repo.record_exposures(uid, ["gap"])
    vocabulary_repo.record_recalls(uid, ["gap"])
    # `plain`: reconocida y ya producida → sin hueco de producción, solo urgencia.
    vocabulary_repo.record_exposures(uid, ["plain"])
    vocabulary_repo.record_production(uid, ["plain"], channel="writing")
    _due_lexicon_card(uid, "gap", stability=30.0, days_ago=1)
    _due_lexicon_card(uid, "plain", stability=30.0, days_ago=1)

    with TestClient(app) as client:
        res = client.get("/api/learning/review", params={"user_id": uid})
        assert res.status_code == 200, res.text
        items = res.json()["items"]

    assert [item["word"] for item in items] == ["gap", "plain"]
    assert items[0]["priority"] > items[1]["priority"]
    assert items[0]["why"]


def test_review_queue_route_exposes_planner_and_skill_fields(
    monkeypatch, tmp_path
):
    uid = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(uid, ["river"])
    _due_lexicon_card(uid, "river", stability=5.0, days_ago=3)
    for day in (
        "2026-09-01T10:00:00+00:00",
        "2026-09-03T10:00:00+00:00",
        # V3.38.1 (P1-04): 3 éxitos independientes en 3 días para automaticidad.
        "2026-09-05T10:00:00+00:00",
    ):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="river",
            skill="recall",
            task="recall",
            activity_id="drill:recall:translation",
            success=True,
            support_level="independent",
            occurred_at=day,
        )

    with TestClient(app) as client:
        item = client.get(
            "/api/learning/review", params={"user_id": uid}
        ).json()["items"][0]

    assert item["automatic_skills"] == ["recall"]
    assert item["signals"]["automatic"] is True
    assert item["automatic"] is True
    assert item["priority"] >= 0
    assert item["why"]


def test_review_queue_ranks_globally_not_just_the_fsrs_head(monkeypatch, tmp_path):
    """V3.38.1 (P1-01): la mejor tarjeta se elige sobre TODAS las vencidas.

    Antes el límite de PRESENTACIÓN se pasaba a `fsrs.due_queue`, así que el
    planner solo veía las 20 más urgentes del scheduler. Aquí la mejor candidata
    es la MENOS urgente (alta estabilidad): queda fuera de la cabeza de FSRS y,
    aun así, el planner debe elegirla.
    """
    uid = _setup(monkeypatch, tmp_path)
    words = [f"w{i:03d}" for i in range(100)]
    best = "w000"
    for word in words:
        vocabulary_repo.record_exposures(uid, [word])
        if word == best:
            # Reconocida, nunca producida (gap = 1.0) y con fallos (weakness =
            # 1.0): la tarea óptima... pero la menos urgente del scheduler.
            for _ in range(4):
                evidence_repo.record_evidence(
                    uid,
                    target_type="lexicon",
                    target_id=word,
                    skill="recall",
                    task="recall",
                    success=False,
                    support_level="cued",
                    occurred_at="2026-09-01T10:00:00+00:00",
                )
            _due_lexicon_card(uid, word, stability=365.0, days_ago=1)
        else:
            # Sin hueco de producción y sin debilidad, pero muy urgentes.
            vocabulary_repo.record_production(uid, [word], channel="writing")
            _due_lexicon_card(uid, word, stability=1.0, days_ago=1)

    cards = [
        card
        for card in academy_repo.list_fsrs_cards(uid)
        if (card.get("target_type") or "") == "lexicon"
    ]
    fsrs_head = {
        card["target_id"] for card in fsrs.due_queue(cards, limit=20)
    }
    assert best not in fsrs_head  # el scheduler, solo, no la vería

    with TestClient(app) as client:
        items = client.get(
            "/api/learning/review", params={"user_id": uid}
        ).json()["items"]

    assert len(items) == 20  # límite de presentación intacto
    assert items[0]["word"] == best  # ...pero el planner la encuentra y la pone 1.ª
    assert items[0]["priority"] > items[1]["priority"]


def test_review_queue_directs_a_partial_production_gap_to_speaking(
    monkeypatch, tmp_path
):
    """V3.38.1 (P1-03): `written ✓ / spoken ✗` es un hueco accionable.

    La escritura está consolidada (automática) y la oral no tiene ningún éxito:
    la siguiente tarea debe ser producción oral (`sentence`), no mantenimiento.
    """
    uid = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(uid, ["harbor"])
    vocabulary_repo.record_recalls(uid, ["harbor"])
    vocabulary_repo.record_production(uid, ["harbor"], channel="writing")
    for day in ("2026-08-01", "2026-08-03", "2026-08-05"):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="harbor",
            skill="written_production",
            task="production",
            activity_id="writing_task",
            success=True,
            support_level="independent",
            occurred_at=f"{day}T10:00:00+00:00",
        )
    for day in ("2026-08-02", "2026-08-04"):
        evidence_repo.record_evidence(
            uid,
            target_type="lexicon",
            target_id="harbor",
            skill="recall",
            task="recall",
            activity_id="drill:recall:translation",
            success=True,
            support_level="independent",
            occurred_at=f"{day}T10:00:00+00:00",
        )
    _due_lexicon_card(uid, "harbor", stability=5.0, days_ago=3)

    with TestClient(app) as client:
        item = client.get(
            "/api/learning/review", params={"user_id": uid}
        ).json()["items"][0]

    assert item["reason"] == "skill_gap"
    assert item["activity"] == "sentence"
    assert item["signals"]["skill_gaps"] == ["spoken_production"]
    assert "spoken_production" in item["why"]
    # La escritura sí está consolidada por modalidad: el hueco es solo el oral.
    assert "written_production" in item["signals"]["automatic_skills"]
