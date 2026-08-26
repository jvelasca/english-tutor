"""Tests del perfil de aprendizaje: CEFR, recomendaciones, persistencia y endpoint."""
import sqlite3

from fastapi.testclient import TestClient

from main import app
from repositories import conversations as conversations_repo
from repositories import db
from repositories import grammar as grammar_repo
from repositories import profile as profile_repo
from repositories import users as users_repo
from repositories import vocabulary as vocabulary_repo
from services.cefr import estimate_cefr, recommendations
from services.grammar import find_errors


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"], users_repo.create_user("B")["id"]


def _fk_targets(table: str) -> set[tuple[str, str]]:
    conn = sqlite3.connect(db.DB_PATH)
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    finally:
        conn.close()
    return {(row[2], row[3]) for row in rows}


def test_learning_profile_table_has_user_fk(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert ("users", "user_id") in _fk_targets("learning_profile")


def test_estimate_cefr_low_is_a1(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert (
        estimate_cefr({"vocab_size": 0, "pronunciation_avg": None, "exercises": 0})
        == "A1"
    )


def test_estimate_cefr_medium_is_b1(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    # Sin intentos de pronunciación, solo el vocabulario (B1) cuenta como evidencia.
    assert (
        estimate_cefr({"vocab_size": 200, "pronunciation_avg": 75, "exercises": 10})
        == "B1"
    )


def test_estimate_cefr_high_is_c1(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    # Vocabulario C1 evidenciado; pronunciación sin muestras no limita el nivel.
    assert (
        estimate_cefr(
            {"vocab_size": 1000, "pronunciation_avg": 95, "exercises": 100}
        )
        == "C1"
    )


def test_recommendations_grammar_error(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    recs = recommendations(
        {
            "recurring_errors": [
                {"rule": "he_she_it_s", "message": "Falta la -s.", "count": 5}
            ],
            "pronunciation_avg": 80,
            "vocab_size": 100,
        }
    )
    assert len(recs) == 1
    assert "Falta la -s" in recs[0]


def test_recommendations_pronunciation(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    recs = recommendations(
        {"recurring_errors": [], "pronunciation_avg": 60, "vocab_size": 100}
    )
    assert len(recs) == 1
    assert "pronunciación" in recs[0]


def test_recommendations_vocabulary(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    recs = recommendations(
        {"recurring_errors": [], "pronunciation_avg": 80, "vocab_size": 30}
    )
    assert len(recs) == 1
    assert "vocabulario" in recs[0]


def test_recommendations_default(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    recs = recommendations(
        {"recurring_errors": [], "pronunciation_avg": None, "vocab_size": 100}
    )
    assert len(recs) == 1
    assert "¡Buen trabajo!" in recs[0]


def test_set_cefr_roundtrip(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    profile_repo.set_cefr(a, "B1")
    assert profile_repo.get_profile(a)["cefr_level"] == "B1"


def test_set_cefr_unknown_user_none(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert profile_repo.set_cefr("no-existe", "B1") is None


def test_profile_endpoint_shape(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_words(a, ["cat", "dog"])
    grammar_repo.record_errors(a, find_errors("He go to school"))

    with TestClient(app) as client:
        r = client.get("/api/profile", params={"user_id": a})
        assert r.status_code == 200
        body = r.json()
        assert body["user_id"] == a
        assert body["estimated_level"] in ("A1", "A2")
        assert 0.0 <= body["estimated_confidence"] < 0.1
        assert 1.0 <= body["overall_ability"] <= 6.0
        assert set(body["estimated_bands"].keys()) == {
            "vocabulary",
            "grammar",
            "pronunciation",
            "listening",
            "speaking",
            "reading",
            "writing",
        }
        assert body["skills"]
        assert all(
            {"skill", "band", "score", "confidence", "samples", "stability"}
            <= set(s)
            for s in body["skills"]
        )
        assert body["readiness"]["target_level"]
        assert body["cefr_history"]  # primer snapshot registrado
        assert body["vocabulary_size"] == 2
        assert set(body["top_words"]) == {"cat", "dog"}
        assert body["recurring_errors"][0]["rule"] == "he_she_it_s"
        assert body["pronunciation_average"] is None
        assert body["recommendations"]


def test_profile_records_cefr_snapshot_once(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r1 = client.get("/api/profile", params={"user_id": a})
        r2 = client.get("/api/profile", params={"user_id": a})
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Sin cambio material entre peticiones idénticas, solo hay un snapshot.
    assert len(r1.json()["cefr_history"]) == 1
    assert len(r2.json()["cefr_history"]) == 1
    snap = r1.json()["cefr_history"][0]
    assert snap["level"] == "A1"
    assert snap["instrument_version"]
    assert snap["curriculum_version"]


def test_profile_endpoint_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert (
            client.get("/api/profile", params={"user_id": "no-existe"}).status_code
            == 404
        )


def test_profile_separates_mastered_errors(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    grammar_repo.record_errors(a, find_errors("He go to school"))
    for _ in range(3):
        grammar_repo.record_correct_usage(a, "he_she_it_s", 3)

    with TestClient(app) as client:
        body = client.get("/api/profile", params={"user_id": a}).json()
    assert body["mastered_count"] == 1
    assert body["recurring_errors"] == []
    assert body["mastered_errors"][0]["rule"] == "he_she_it_s"


def test_profile_vocabulary_exposure_and_mastery(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    vocabulary_repo.record_exposures(a, ["travel"])  # solo expuesta
    for _ in range(3):
        vocabulary_repo.record_words(a, ["cat"])  # producida 3× en un solo día

    with TestClient(app) as client:
        body = client.get("/api/profile", params={"user_id": a}).json()
    assert body["vocabulary_size"] == 1  # solo "cat" cuenta como producida
    assert body["vocabulary_exposed"] == 1
    assert body["vocabulary_mastered"] == 0  # sin espaciado temporal
    assert set(body["top_words"]) == {"cat"}


def test_profile_vocabulary_mastered(monkeypatch, tmp_path):
    a, _b = _setup(monkeypatch, tmp_path)
    times = iter(
        [
            "2026-08-20T10:00:00+00:00",
            "2026-08-21T10:00:00+00:00",
            "2026-08-22T10:00:00+00:00",
        ]
    )
    monkeypatch.setattr(vocabulary_repo, "_now", lambda: next(times))
    for _ in range(3):
        vocabulary_repo.record_words(a, ["cat"])

    with TestClient(app) as client:
        body = client.get("/api/profile", params={"user_id": a}).json()
    assert body["vocabulary_size"] == 1
    assert body["vocabulary_mastered"] == 1
    assert body["vocabulary_exposed"] == 0


def test_profile_grammar_band_defaults_to_a1_without_academy_evidence(
    monkeypatch, tmp_path
):
    a, _b = _setup(monkeypatch, tmp_path)
    cid = conversations_repo.create_conversation(a)["id"]
    conversations_repo.save_conversation(
        cid,
        a,
        "Clase",
        [
            {"role": "user", "content": "He go to school", "mode": "grammar"},
            {"role": "assistant", "content": "You mean goes"},
            {"role": "user", "content": "She like coffee", "mode": "grammar"},
            {"role": "assistant", "content": "You mean likes"},
        ],
    )
    grammar_repo.record_errors(a, find_errors("He go to school"))

    with TestClient(app) as client:
        r = client.get("/api/profile", params={"user_id": a})
        assert r.status_code == 200
        # Sin evidencia de Academy, la banda de gramática es la heurística A1.
        assert r.json()["estimated_bands"]["grammar"] == "A1"
