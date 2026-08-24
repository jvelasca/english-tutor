"""Tests de integración: el perfil del alumno entra al system prompt del chat."""
from fastapi.testclient import TestClient

from config import MODE_PROMPTS
from main import app
from repositories import db
from repositories import grammar as grammar_repo
from repositories import users as users_repo
from services import llm
from services.grammar import find_errors


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


def test_chat_with_user_id_personalizes_prompt(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    grammar_repo.record_errors(uid, find_errors("He go to school"))
    fake = FakeOllamaClient()
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Hello"}], "user_id": uid},
        )
    assert r.status_code == 200
    sent = fake.calls[0]["messages"][0]["content"]
    assert "CEFR" in sent
    assert "Falta la -s" in sent


def test_chat_without_user_id_uses_base_prompt(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    fake = FakeOllamaClient()
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/chat", json={"messages": [{"role": "user", "content": "Hello"}]}
        )
    assert r.status_code == 200
    sent = fake.calls[0]["messages"][0]["content"]
    assert sent == MODE_PROMPTS["conversation"]


def test_chat_unknown_user_id_uses_base_prompt(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    fake = FakeOllamaClient()
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "user_id": "no-existe",
            },
        )
    assert r.status_code == 200
    sent = fake.calls[0]["messages"][0]["content"]
    assert sent == MODE_PROMPTS["conversation"]


def test_chat_stream_with_user_id_personalizes(monkeypatch, tmp_path):
    uid = _setup(monkeypatch, tmp_path)
    grammar_repo.record_errors(uid, find_errors("He go to school"))
    fake = FakeOllamaClient()
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/chat/stream",
            json={"messages": [{"role": "user", "content": "Hello"}], "user_id": uid},
        )
    assert r.status_code == 200
    sent = fake.calls[0]["messages"][0]["content"]
    assert "CEFR" in sent
    assert "Falta la -s" in sent
