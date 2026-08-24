"""Tests de listening: banco, puntuación, dominio, repositorio y endpoints."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services.listening import (
    QUESTION_BANK,
    get_question,
    pick_next_question,
    score_answer,
)


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def test_score_answer_correct():
    assert score_answer(1, 1) is True


def test_score_answer_incorrect():
    assert score_answer(0, 1) is False


def test_get_question_found():
    q = get_question(QUESTION_BANK[0]["id"])
    assert q is not None
    assert q["script"]


def test_get_question_missing():
    assert get_question("nope") is None


def test_pick_next_unseen():
    assert pick_next_question(set())["id"] == QUESTION_BANK[0]["id"]
    assert pick_next_question({QUESTION_BANK[0]["id"]})["id"] == QUESTION_BANK[1]["id"]


def test_pick_next_wraps_around():
    seen = {q["id"] for q in QUESTION_BANK}
    assert pick_next_question(seen)["id"] == QUESTION_BANK[0]["id"]


def test_bank_shape_valid():
    assert len(QUESTION_BANK) >= 3
    for q in QUESTION_BANK:
        assert q["id"]
        assert q["script"]
        assert q["question"]
        assert len(q["options"]) >= 2
        assert 0 <= q["answer_index"] < len(q["options"])


def test_next_question_endpoint(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.get("/api/listening/question", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert body["script"]
    assert body["question"]
    assert isinstance(body["options"], list) and len(body["options"]) >= 2
    assert "answer_index" not in body


def test_answer_correct(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["correct"] is True
    assert body["correct_index"] == q["answer_index"]


def test_answer_wrong(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    wrong = (q["answer_index"] + 1) % len(q["options"])
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": wrong},
        )
    assert r.status_code == 200
    assert r.json()["correct"] is False


def test_answer_unknown_question_404(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": "nope", "answer_index": 0},
        )
    assert r.status_code == 404


def test_answer_unknown_user_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        r = client.post(
            "/api/listening/answer",
            params={"user_id": "no-existe"},
            json={"question_id": q["id"], "answer_index": 0},
        )
    assert r.status_code == 404


def test_stats_endpoint(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    q = QUESTION_BANK[0]
    with TestClient(app) as client:
        client.post(
            "/api/listening/answer",
            params={"user_id": uid},
            json={"question_id": q["id"], "answer_index": q["answer_index"]},
        )
        r = client.get("/api/listening/stats", params={"user_id": uid})
    assert r.status_code == 200
    body = r.json()
    assert body["attempts"] == 1
    assert body["correct"] == 1
    assert body["accuracy"] == 100.0
