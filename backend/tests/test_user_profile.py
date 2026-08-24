from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("Ana")["id"]


def test_create_user_has_default_avatar_fields(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    user = users_repo.get_user(uid)
    assert user["avatar_color"] == ""
    assert user["avatar_emoji"] == ""
    assert user["avatar_image"] == ""


def test_update_user_avatar(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    updated = users_repo.update_user(
        uid, name="Ana M", avatar_emoji="🎧", avatar_color="#6366f1"
    )
    assert updated["name"] == "Ana M"
    assert updated["avatar_emoji"] == "🎧"
    assert updated["avatar_color"] == "#6366f1"
    assert updated["avatar_image"] == ""


def test_update_user_partial_preserves_others(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    users_repo.update_user(uid, avatar_emoji="🎧")
    updated = users_repo.update_user(uid, name="Otro")
    assert updated["name"] == "Otro"
    assert updated["avatar_emoji"] == "🎧"


def test_update_user_unknown_returns_none(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert users_repo.update_user("no-existe", name="x") is None


def test_api_patch_user(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.patch(
            f"/api/users/{uid}", json={"name": "Ana 2", "avatar_emoji": "🚀"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Ana 2"
        assert body["avatar_emoji"] == "🚀"


def test_api_patch_user_unknown(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert (
            client.patch("/api/users/no-existe", json={"name": "x"}).status_code
            == 404
        )
