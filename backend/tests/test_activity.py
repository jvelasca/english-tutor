"""Tests de registro automático de eventos de aprendizaje."""
from fastapi.testclient import TestClient

from main import app
from repositories import db
from repositories import learning as learning_repo
from repositories import users as users_repo
from services import llm


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        self._it = iter(self._chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration from None


class FakeOllamaClient:
    def __init__(self, content="Hi!"):
        self.content = content
        self.calls = []

    async def chat(self, *, model, messages, options=None, stream=False):
        self.calls.append({"model": model, "messages": messages, "stream": stream})
        if stream:
            return _FakeStream([{"message": {"content": self.content}}])
        return {"message": {"content": self.content}}

    async def list(self):
        return {"models": [{"model": "qwen3.5:9b"}]}


def _setup(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return users_repo.create_user("A")["id"]


def _post_chat(client, uid=None, mode="conversation"):
    body = {"messages": [{"role": "user", "content": "Hello"}], "mode": mode}
    if uid is not None:
        body["user_id"] = uid
    return client.post("/api/chat", json=body)


def test_chat_conversation_mode_records_message_event(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(llm, "get_client", lambda: FakeOllamaClient())
    with TestClient(app) as client:
        r = _post_chat(client, uid, mode="conversation")
    assert r.status_code == 200
    assert any(e["type"] == "message" for e in learning_repo.list_events(uid))


def test_chat_exercises_mode_records_exercise_event(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(llm, "get_client", lambda: FakeOllamaClient())
    with TestClient(app) as client:
        r = _post_chat(client, uid, mode="exercises")
    assert r.status_code == 200
    assert any(e["type"] == "exercise" for e in learning_repo.list_events(uid))


def test_chat_grammar_mode_records_correction_event(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(llm, "get_client", lambda: FakeOllamaClient())
    with TestClient(app) as client:
        r = _post_chat(client, uid, mode="grammar")
    assert r.status_code == 200
    assert any(e["type"] == "correction" for e in learning_repo.list_events(uid))


def test_chat_without_user_id_records_nothing(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(llm, "get_client", lambda: FakeOllamaClient())
    with TestClient(app) as client:
        r = _post_chat(client, uid=None)
    assert r.status_code == 200
    assert learning_repo.list_events(uid) == []


def test_chat_unknown_user_id_records_nothing(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(llm, "get_client", lambda: FakeOllamaClient())
    with TestClient(app) as client:
        r = _post_chat(client, uid="no-existe")
    assert r.status_code == 200
    assert learning_repo.list_events("no-existe") == []


def test_pronunciation_records_event(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "routers.pronunciation.transcribe_with_timing",
        lambda audio, language="en": {"text": "Hello world", "duration": 2.0},
    )
    with TestClient(app) as client:
        r = client.post(
            "/api/pronunciation",
            data={"expected": "Hello world", "user_id": uid},
            files={"file": ("a.webm", b"fake", "audio/webm")},
        )
    assert r.status_code == 200
    events = learning_repo.list_events(uid)
    assert any(
        e["type"] == "pronunciation" and e["detail"] == "Hello world"
        for e in events
    )


def test_conversation_create_records_event(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    with TestClient(app) as client:
        r = client.post("/api/conversations", params={"user_id": uid})
    assert r.status_code == 200
    assert any(e["type"] == "conversation" for e in learning_repo.list_events(uid))


def test_events_isolated_per_user(monkeypatch, tmp_path):
    a = _setup(monkeypatch, tmp_path)
    b = users_repo.create_user("B")["id"]
    monkeypatch.setattr(llm, "get_client", lambda: FakeOllamaClient())
    with TestClient(app) as client:
        _post_chat(client, a, mode="conversation")
    assert learning_repo.list_events(a)
    assert learning_repo.list_events(b) == []
