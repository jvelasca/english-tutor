from repositories import conversations as conversations_repo
from repositories import db
from repositories import users as users_repo


def test_store_crud(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")

    db.init_db()

    user = users_repo.list_users()[0]
    uid = user["id"]

    conv = conversations_repo.create_conversation(uid)
    cid = conv["id"]
    assert cid
    assert conv["user_id"] == uid

    saved = conversations_repo.save_conversation(
        cid, uid, "Mi clase", [{"role": "user", "content": "Hello"}]
    )
    assert saved["title"] == "Mi clase"
    assert saved["user_id"] == uid

    got = conversations_repo.get_conversation(cid, uid)
    assert got is not None
    assert got["title"] == "Mi clase"
    assert got["messages"][0]["content"] == "Hello"

    assert any(c["id"] == cid for c in conversations_repo.list_conversations(uid))

    assert conversations_repo.delete_conversation(cid, uid) is True
    assert conversations_repo.get_conversation(cid, uid) is None
