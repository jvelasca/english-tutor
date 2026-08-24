from fastapi.testclient import TestClient

from main import app
from services import store


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")
    store.init_db()
    a = store.create_user("A")["id"]
    b = store.create_user("B")["id"]
    cid = store.create_conversation(a)["id"]
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
            data={"expected": "Hello world", "user_id": "no-existe"},
            files={"file": ("a.webm", b"fake", "audio/webm")},
        )
        assert r.status_code == 404


def test_pronunciation_records_only_for_declared_user(monkeypatch, tmp_path):
    a, b, _cid = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "routers.pronunciation.transcribe_audio",
        lambda audio, language="en": "Hello world",
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/pronunciation",
            data={"expected": "Hello world", "user_id": a},
            files={"file": ("a.webm", b"fake", "audio/webm")},
        )
        assert r.status_code == 200
    assert store.get_progress(a)["pronunciation"]["attempts"] == 1
    assert store.get_progress(b)["pronunciation"]["attempts"] == 0
