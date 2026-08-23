from services import store


def test_store_crud(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")

    store.init_db()

    conv = store.create_conversation()
    cid = conv["id"]
    assert cid

    saved = store.save_conversation(
        cid, "Mi clase", [{"role": "user", "content": "Hello"}]
    )
    assert saved["title"] == "Mi clase"

    got = store.get_conversation(cid)
    assert got is not None
    assert got["title"] == "Mi clase"
    assert got["messages"][0]["content"] == "Hello"

    assert any(c["id"] == cid for c in store.list_conversations())

    assert store.delete_conversation(cid) is True
    assert store.get_conversation(cid) is None
