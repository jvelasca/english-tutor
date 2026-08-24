from services import store


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")
    store.init_db()


def test_get_conversation_other_user_returns_none(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    a = store.create_user("A")["id"]
    b = store.create_user("B")["id"]
    cid = store.create_conversation(a)["id"]
    assert store.get_conversation(cid, a) is not None
    assert store.get_conversation(cid, b) is None


def test_save_conversation_other_user_returns_none(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    a = store.create_user("A")["id"]
    b = store.create_user("B")["id"]
    cid = store.create_conversation(a)["id"]
    store.save_conversation(cid, a, "Original", [{"role": "user", "content": "hello"}])
    assert (
        store.save_conversation(cid, b, "Hacked", [{"role": "user", "content": "x"}])
        is None
    )
    got = store.get_conversation(cid, a)
    assert got["title"] == "Original"
    assert got["messages"][0]["content"] == "hello"


def test_delete_conversation_other_user_returns_false(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    a = store.create_user("A")["id"]
    b = store.create_user("B")["id"]
    cid = store.create_conversation(a)["id"]
    assert store.delete_conversation(cid, b) is False
    assert store.get_conversation(cid, a) is not None
    assert store.delete_conversation(cid, a) is True


def test_record_pronunciation_unknown_user_returns_false(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    assert store.record_pronunciation("no-existe", "Hi", "Hi", 90, "good") is False


def test_record_pronunciation_known_user_returns_true(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    a = store.create_user("A")["id"]
    assert store.record_pronunciation(a, "Hi", "Hi", 90, "good") is True
