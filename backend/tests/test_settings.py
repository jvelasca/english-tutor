from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import settings as settings_repo
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("Ana")["id"]


def test_get_settings_empty(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    assert settings_repo.get_settings(uid) == {}


def test_set_and_get_settings(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    settings_repo.set_settings(uid, {"model": "qwen3.5:9b", "layout": '{"w":300}'})
    got = settings_repo.get_settings(uid)
    assert got["model"] == "qwen3.5:9b"
    assert got["layout"] == '{"w":300}'


def test_set_settings_merges_keys(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    settings_repo.set_settings(uid, {"model": "a"})
    settings_repo.set_settings(uid, {"mode": "grammar"})
    assert settings_repo.get_settings(uid) == {"model": "a", "mode": "grammar"}


def test_settings_isolated_between_users(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    b = users_repo.create_user("Bob")["id"]
    settings_repo.set_settings(a, {"model": "x"})
    assert settings_repo.get_settings(b) == {}


def test_api_get_settings(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    settings_repo.set_settings(uid, {"model": "qwen3.5:9b"})
    with TestClient(app) as client:
        r = client.get("/api/settings", params={"user_id": uid})
        assert r.status_code == 200
        assert r.json()["settings"]["model"] == "qwen3.5:9b"


def test_api_save_settings(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.put(
            "/api/settings",
            json={"user_id": uid, "settings": {"model": "llama3.1:8b"}},
        )
        assert r.status_code == 200
        assert r.json()["settings"]["model"] == "llama3.1:8b"


def test_api_save_settings_unknown_user(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.put(
            "/api/settings",
            json={"user_id": "no-existe", "settings": {"model": "x"}},
        )
        assert r.status_code == 404
