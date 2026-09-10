"""Tests de V3.35 — cola de repaso propia (P1-2).

V3.34 usaba FSRS para programar el recall, pero la cola real de repaso pasaba
por `get_drill_candidates()` (la cola histórica del micro-drill de SPEAKING):
dos conceptos distintos mezclados. V3.35 los separa:

- `GET /api/learning/review` → repaso espaciado del léxico (carta FSRS vencida
  + actividad óptima por hueco de competencia: reconocer / recuperar / producir);
- `GET /api/vocabulary/drill/candidates` → solo huecos de producción ORAL
  pendiente, sin priorización por FSRS.

Se cubren: mapeo de actividad por hueco, orden por urgencia del scheduler,
retención de la forma esperada fuera del payload y la retirada del acople FSRS
del speaking drill.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from main import app
from repositories import academy as academy_repo
from repositories import db
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services import fsrs, lexicon


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _due_lexicon_card(uid: str, word: str, *, stability: float, days_ago: int) -> None:
    """Carta FSRS `lexicon` ya revisada y VENCIDA (due ayer)."""
    now = datetime.now(timezone.utc)
    last = (now - timedelta(days=days_ago)).isoformat()
    card = {
        **fsrs.empty_card(target_type="lexicon", target_id=word, label=word),
        "state": "review",
        "reps": 2,
        "stability": stability,
        "due_at": (now - timedelta(days=1)).isoformat(),
        "last_review_at": last,
        "last_grade": fsrs.GRADE_GOOD,
    }
    assert academy_repo.upsert_fsrs_card(uid, card) is not None


def _review_queue(client: TestClient, uid: str) -> dict:
    res = client.get("/api/learning/review", params={"user_id": uid})
    assert res.status_code == 200, res.text
    return res.json()


# --- Decisión pura de actividad por hueco de competencia --------------------


def test_recommend_review_activity_maps_gap():
    weak = {"exposure_count": 0, "production_count": 0}
    assert lexicon.recommend_review_activity(weak)["activity"] == "recognition"
    assert lexicon.recommend_review_activity(weak)["reason"] == "weak_recognition"

    recognized = {
        "exposure_count": 3,
        "production_count": 0,
        "last_exposed_at": datetime.now(timezone.utc).isoformat(),
    }
    assert lexicon.recommend_review_activity(recognized)["activity"] == "recall"
    assert (
        lexicon.recommend_review_activity(recognized)["reason"]
        == "no_recall_evidence"
    )

    recalled = {**recognized, "recall_successes": 2, "recall_days": 2}
    assert lexicon.recommend_review_activity(recalled)["activity"] == "sentence"
    assert lexicon.recommend_review_activity(recalled)["reason"] == "production_gap"

    produced = {
        **recalled,
        "production_count": 3,
        "production_days": 2,
        "context_tags": "speaking:drill,writing:task",
        "speaking_prod": 2,
        "writing_prod": 1,
    }
    assert lexicon.recommend_review_activity(produced)["activity"] == "recall"
    assert lexicon.recommend_review_activity(produced)["reason"] == "maintenance"


# --- Cola HTTP --------------------------------------------------------------


def test_review_queue_recommends_activity_by_gap(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    # Nunca expuesta (solo recall por texto) → falta base receptiva.
    vocabulary_repo.record_recalls(uid, ["quokka"])
    # Reconocida pero sin recall → recuperar por texto.
    vocabulary_repo.record_exposures(uid, ["river"])
    # Recuperada pero sin producir → producir en contexto.
    vocabulary_repo.record_exposures(uid, ["apple"])
    vocabulary_repo.record_recalls(uid, ["apple"])

    for word in ("quokka", "river", "apple"):
        _due_lexicon_card(uid, word, stability=5.0, days_ago=3)

    with TestClient(app) as client:
        body = _review_queue(client, uid)

    by_word = {item["word"]: item for item in body["items"]}
    assert body["due_count"] == 3
    assert body["fsrs_version"] == fsrs.FSRS_VERSION
    assert by_word["quokka"]["activity"] == "recognition"
    assert by_word["river"]["activity"] == "recall"
    assert by_word["apple"]["activity"] == "sentence"


def test_review_queue_orders_by_fsrs_urgency(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(uid, ["urgent", "calm"])
    # `urgent`: estabilidad baja y mucho tiempo → retrievability menor.
    _due_lexicon_card(uid, "urgent", stability=1.0, days_ago=12)
    # `calm`: estabilidad alta y revisada hace poco → retrievability mayor.
    _due_lexicon_card(uid, "calm", stability=30.0, days_ago=1)

    with TestClient(app) as client:
        body = _review_queue(client, uid)

    assert [item["word"] for item in body["items"]][:2] == ["urgent", "calm"]
    assert body["items"][0]["retrievability"] < body["items"][1]["retrievability"]


def test_review_queue_item_never_exposes_expected_form(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(uid, ["river"])
    _due_lexicon_card(uid, "river", stability=5.0, days_ago=3)

    with TestClient(app) as client:
        body = _review_queue(client, uid)

    item = body["items"][0]
    # La cola informa de la palabra (es la diana del repaso) pero NUNCA sirve el
    # cue ni la respuesta esperada de un peldaño: eso lo sirve el GET del paso.
    assert item["word"] == "river"
    assert "expected" not in item
    assert "cue" not in item
    # Snapshot de competencia y evidencia disponibles (señal, no puerta).
    assert item["competence"]["recognition"] is True
    assert item["evidence"]["attempts"] == 0


def test_review_queue_isolated_between_users(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    other = users_repo.create_user("B")["id"]
    vocabulary_repo.record_exposures(uid, ["river"])
    _due_lexicon_card(uid, "river", stability=5.0, days_ago=3)

    with TestClient(app) as client:
        assert _review_queue(client, uid)["due_count"] == 1
        assert _review_queue(client, other)["due_count"] == 0


# --- El speaking drill ya NO prioriza por FSRS ------------------------------


def test_drill_candidates_ignore_fsrs_due(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    # "forgotten": menos producción → recuerdo actual más bajo (va primero).
    vocabulary_repo.record_exposures(uid, ["forgotten"])
    vocabulary_repo.record_production(uid, ["forgotten"], channel="speaking")
    # "due_recent": más producción (score mayor) pero con carta FSRS vencida.
    vocabulary_repo.record_exposures(uid, ["due_recent"])
    for _ in range(3):
        vocabulary_repo.record_production(uid, ["due_recent"], channel="writing")
    _due_lexicon_card(uid, "due_recent", stability=1.0, days_ago=10)

    with TestClient(app) as client:
        res = client.get(
            "/api/vocabulary/drill/candidates",
            params={"user_id": uid, "limit": 10},
        )
        assert res.status_code == 200, res.text
        words = res.json()["words"]

    # V3.35: el orden es por recuerdo (más olvidada primero), no por FSRS due.
    assert words == ["forgotten", "due_recent"]
