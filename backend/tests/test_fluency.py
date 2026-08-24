"""Tests de fluidez oral: compute_fluency (puro) y endpoint."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo
from services.fluency import compute_fluency


def test_compute_fluency_empty():
    r = compute_fluency("", 5.0)
    assert r["word_count"] == 0
    assert r["wpm"] is None
    assert r["level"] == "—"


def test_compute_fluency_good():
    r = compute_fluency("Hello world how are you", 5.0)  # 5 palabras / 5s = 60 wpm
    assert r["word_count"] == 5
    assert r["wpm"] == 60.0
    assert r["level"] == "good"


def test_compute_fluency_fluent():
    r = compute_fluency("one two three four five six seven eight nine ten", 3.0)
    assert r["wpm"] == 200.0
    assert r["level"] == "fluent"


def test_compute_fluency_slow():
    r = compute_fluency("hello world", 10.0)  # 2 palabras / 10s = 12 wpm
    assert r["wpm"] == 12.0
    assert r["level"] == "slow"


def test_compute_fluency_no_duration():
    r = compute_fluency("hello world", None)
    assert r["wpm"] is None
    assert r["duration_seconds"] is None
    assert r["level"] == "—"


def test_pronunciation_endpoint_returns_fluency(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    uid = users_repo.create_user("A")["id"]
    monkeypatch.setattr(
        "routers.pronunciation.transcribe_with_timing",
        lambda audio, language="en": {"text": "Hello world", "duration": 2.0},
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/pronunciation",
            data={"expected": "Hello world", "user_id": uid},
            files={"file": ("a.webm", b"fake", "audio/webm")},
        )
    assert r.status_code == 200
    fluency = r.json()["fluency"]
    assert fluency["word_count"] == 2
    assert fluency["wpm"] == 60.0
