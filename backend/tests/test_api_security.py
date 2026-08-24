from fastapi.testclient import TestClient

from main import app
from repositories import conversations as conversations_repo
from repositories import db
from repositories import pronunciation as pronunciation_repo
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    cid = conversations_repo.create_conversation(a)["id"]
    return a, b, cid


def test_cannot_read_other_user_conversation(monkeypatch, tmp_path):
    a, b, cid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert (
            client.get(f"/api/conversations/{cid}", params={"user_id": b})
            .status_code
            == 404
        )
        assert (
            client.get(f"/api/conversations/{cid}", params={"user_id": a})
            .status_code
            == 200
        )


def test_cannot_update_other_user_conversation(monkeypatch, tmp_path):
    a, b, cid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.put(
            f"/api/conversations/{cid}",
            params={"user_id": b},
            json={"title": "Hacked", "messages": [{"role": "user", "content": "x"}]},
        )
        assert r.status_code == 404
        got = client.get(f"/api/conversations/{cid}", params={"user_id": a})
        assert got.status_code == 200
        assert got.json()["title"] == "Nueva conversación"


def test_cannot_delete_other_user_conversation(monkeypatch, tmp_path):
    a, b, cid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert (
            client.delete(f"/api/conversations/{cid}", params={"user_id": b})
            .status_code
            == 404
        )
        assert (
            client.get(f"/api/conversations/{cid}", params={"user_id": a})
            .status_code
            == 200
        )


def test_conversation_crud_unknown_user_404(monkeypatch, tmp_path):
    _a, _b, cid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert (
            client.get(f"/api/conversations/{cid}", params={"user_id": "zzz"})
            .status_code
            == 404
        )
        assert (
            client.put(
                f"/api/conversations/{cid}",
                params={"user_id": "zzz"},
                json={"title": "X", "messages": []},
            ).status_code
            == 404
        )
        assert (
            client.delete(f"/api/conversations/{cid}", params={"user_id": "zzz"})
            .status_code
            == 404
        )


def test_pronunciation_unknown_user_404(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/api/pronunciation",
            params={"user_id": "no-existe"},
            data={"expected": "Hello world"},
            files={"file": ("a.webm", b"fake", "audio/webm")},
        )
        assert r.status_code == 404


def test_pronunciation_records_only_for_declared_user(monkeypatch, tmp_path):
    a, b, _cid = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "routers.pronunciation.transcribe_with_timing",
        lambda audio, language="en": {"text": "Hello world", "duration": 2.0},
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/pronunciation",
            params={"user_id": a},
            data={"expected": "Hello world"},
            files={"file": ("a.webm", b"fake", "audio/webm")},
        )
        assert r.status_code == 200
    assert pronunciation_repo.get_progress(a)["pronunciation"]["attempts"] == 1
    assert pronunciation_repo.get_progress(b)["pronunciation"]["attempts"] == 0
