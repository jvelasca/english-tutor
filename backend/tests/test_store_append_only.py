from repositories import conversations as conversations_repo
from repositories import db
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    uid = users_repo.list_users()[0]["id"]
    cid = conversations_repo.create_conversation(uid)["id"]
    return uid, cid


def test_append_only_does_not_duplicate(monkeypatch, tmp_path):
    uid, cid = _setup(monkeypatch, tmp_path)
    conversations_repo.save_conversation(
        cid,
        uid,
        "T",
        [
            {"id": "m1", "role": "user", "content": "Hi"},
            {"id": "m2", "role": "assistant", "content": "Hello"},
        ],
    )
    conversations_repo.save_conversation(
        cid,
        uid,
        "T",
        [
            {"id": "m1", "role": "user", "content": "Hi"},
            {"id": "m2", "role": "assistant", "content": "Hello"},
            {"id": "m3", "role": "user", "content": "Bye"},
        ],
    )
    conv = conversations_repo.get_conversation(cid, uid)
    assert [m["id"] for m in conv["messages"]] == ["m1", "m2", "m3"]
    assert len(conv["messages"]) == 3


def test_legacy_save_without_ids_replaces(monkeypatch, tmp_path):
    uid, cid = _setup(monkeypatch, tmp_path)
    conversations_repo.save_conversation(
        cid,
        uid,
        "T",
        [{"role": "user", "content": "one"}, {"role": "user", "content": "two"}],
    )
    conversations_repo.save_conversation(
        cid, uid, "T", [{"role": "user", "content": "only"}]
    )
    conv = conversations_repo.get_conversation(cid, uid)
    assert [m["content"] for m in conv["messages"]] == ["only"]


def test_get_conversation_returns_message_id(monkeypatch, tmp_path):
    uid, cid = _setup(monkeypatch, tmp_path)
    conversations_repo.save_conversation(
        cid, uid, "T", [{"id": "abc", "role": "user", "content": "Hi"}]
    )
    conv = conversations_repo.get_conversation(cid, uid)
    assert conv["messages"][0]["id"] == "abc"
