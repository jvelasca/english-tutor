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


def test_estimate_cefr_medium_is_b2(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert (
        estimate_cefr({"vocab_size": 200, "pronunciation_avg": 75, "exercises": 10})
        == "B2"
    )


def test_estimate_cefr_high_is_c2(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert (
        estimate_cefr(
            {"vocab_size": 1000, "pronunciation_avg": 95, "exercises": 100}
        )
        == "C2"
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
        assert body["vocabulary_size"] == 2
        assert set(body["top_words"]) == {"cat", "dog"}
        assert body["recurring_errors"][0]["rule"] == "he_she_it_s"
        assert body["pronunciation_average"] is None
        assert body["recommendations"]


def test_profile_endpoint_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert (
            client.get("/api/profile", params={"user_id": "no-existe"}).status_code
            == 404
        )


def test_profile_grammar_rate_uses_user_messages(monkeypatch, tmp_path):
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
        # 2 mensajes de usuario y 1 error → ratio 0.5 → banda A1 (no A2).
        assert r.json()["estimated_bands"]["grammar"] == "A1"
