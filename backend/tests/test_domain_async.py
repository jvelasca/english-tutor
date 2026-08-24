import asyncio

from domain import conversations as conversation_service
from domain import pronunciation as pronunciation_service
from domain import users as user_service
from repositories import db


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


def test_domain_services_match_repositories(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    a = asyncio.run(user_service.create_user("A"))
    b = asyncio.run(user_service.create_user("B"))
    assert a["name"] == "A" and b["name"] == "B"

    names = {u["name"] for u in asyncio.run(user_service.list_users())}
    assert {"Usuario", "A", "B"} <= names

    cid = asyncio.run(conversation_service.create_conversation(a["id"]))["id"]
    assert (
        asyncio.run(conversation_service.get_conversation(cid, a["id"]))["user_id"]
        == a["id"]
    )
    assert asyncio.run(conversation_service.get_conversation(cid, b["id"])) is None

    saved = asyncio.run(
        conversation_service.save_conversation(
            cid, a["id"], "T", [{"role": "user", "content": "hi"}]
        )
    )
    assert saved["title"] == "T"

    ok = asyncio.run(
        pronunciation_service.record_pronunciation(a["id"], "x", "y", 90, "good")
    )
    assert ok is True
    ok = asyncio.run(
        pronunciation_service.record_pronunciation("no-existe", "x", "y", 90, "good")
    )
    assert ok is False

    prog = asyncio.run(pronunciation_service.get_progress(a["id"]))
    assert prog["pronunciation"]["attempts"] == 1

    assert asyncio.run(conversation_service.delete_conversation(cid, a["id"])) is True
    assert asyncio.run(conversation_service.get_conversation(cid, a["id"])) is None
