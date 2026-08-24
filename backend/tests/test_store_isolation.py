from repositories import conversations as conversations_repo
from repositories import db
from repositories import pronunciation as pronunciation_repo
from repositories import users as users_repo


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


def test_get_conversation_other_user_returns_none(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    cid = conversations_repo.create_conversation(a)["id"]
    assert conversations_repo.get_conversation(cid, a) is not None
    assert conversations_repo.get_conversation(cid, b) is None


def test_save_conversation_other_user_returns_none(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    cid = conversations_repo.create_conversation(a)["id"]
    conversations_repo.save_conversation(
        cid, a, "Original", [{"role": "user", "content": "hello"}]
    )
    assert (
        conversations_repo.save_conversation(
            cid, b, "Hacked", [{"role": "user", "content": "x"}]
        )
        is None
    )
    got = conversations_repo.get_conversation(cid, a)
    assert got["title"] == "Original"
    assert got["messages"][0]["content"] == "hello"


def test_delete_conversation_other_user_returns_false(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    a = users_repo.create_user("A")["id"]
    b = users_repo.create_user("B")["id"]
    cid = conversations_repo.create_conversation(a)["id"]
    assert conversations_repo.delete_conversation(cid, b) is False
    assert conversations_repo.get_conversation(cid, a) is not None
    assert conversations_repo.delete_conversation(cid, a) is True


def test_record_pronunciation_unknown_user_returns_false(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert (
        pronunciation_repo.record_pronunciation("no-existe", "Hi", "Hi", 90, "good")
        is False
    )


def test_record_pronunciation_known_user_returns_true(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    a = users_repo.create_user("A")["id"]
    assert pronunciation_repo.record_pronunciation(a, "Hi", "Hi", 90, "good") is True
