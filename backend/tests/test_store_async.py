import asyncio

from services import store, store_async


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.db")
    store.init_db()


def test_async_wrappers_match_store(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    a = asyncio.run(store_async.create_user("A"))
    b = asyncio.run(store_async.create_user("B"))
    assert a["name"] == "A" and b["name"] == "B"

    names = {u["name"] for u in asyncio.run(store_async.list_users())}
    assert {"Usuario", "A", "B"} <= names

    cid = asyncio.run(store_async.create_conversation(a["id"]))["id"]
    assert asyncio.run(store_async.get_conversation(cid, a["id"]))["user_id"] == a["id"]
    assert asyncio.run(store_async.get_conversation(cid, b["id"])) is None

    saved = asyncio.run(
        store_async.save_conversation(
            cid, a["id"], "T", [{"role": "user", "content": "hi"}]
        )
    )
    assert saved["title"] == "T"

    ok = asyncio.run(
        store_async.record_pronunciation(a["id"], "x", "y", 90, "good")
    )
    assert ok is True
    ok = asyncio.run(
        store_async.record_pronunciation("no-existe", "x", "y", 90, "good")
    )
    assert ok is False

    prog = asyncio.run(store_async.get_progress(a["id"]))
    assert prog["pronunciation"]["attempts"] == 1

    assert asyncio.run(store_async.delete_conversation(cid, a["id"])) is True
    assert asyncio.run(store_async.get_conversation(cid, a["id"])) is None
