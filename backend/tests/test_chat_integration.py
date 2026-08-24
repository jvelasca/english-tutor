
from fastapi.testclient import TestClient

from config import MODE_PROMPTS
from main import app
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


class _RaisingStream:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise RuntimeError("SECRET-STREAM")


class FakeOllamaClient:
    def __init__(self, content="Hello!", chunks=None, error=None, stream_error=False):
        self.content = content
        self.chunks = chunks
        self.error = error
        self.stream_error = stream_error
        self.calls = []

    async def chat(self, *, model, messages, options=None, stream=False):
        self.calls.append(
            {"model": model, "messages": messages, "options": options, "stream": stream}
        )
        if self.error:
            raise self.error
        if stream:
            if self.stream_error:
                return _RaisingStream()
            return _FakeStream(self.chunks or [{"message": {"content": self.content}}])
        return {
            "message": {"content": self.content},
            "total_duration": 123,
            "prompt_eval_count": 1,
            "eval_count": 2,
        }

    async def list(self):
        if self.error:
            raise self.error
        return {"models": [{"model": "qwen3.5:9b"}]}


def test_chat_ok_injects_system_prompt_and_mode(monkeypatch):
    fake = FakeOllamaClient(content="Hi there!")
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "mode": "grammar",
            },
        )
    assert r.status_code == 200
    assert r.json()["content"] == "Hi there!"
    sent = fake.calls[0]["messages"]
    assert sent[0] == {"role": "system", "content": MODE_PROMPTS["grammar"]}
    assert sent[1]["role"] == "user"
    assert sent[1]["content"] == "Hello"


def test_chat_unknown_mode_falls_back_to_conversation(monkeypatch):
    fake = FakeOllamaClient()
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Hi"}], "mode": "nope"},
        )
    assert r.status_code == 200
    assert fake.calls[0]["messages"][0]["content"] == MODE_PROMPTS["conversation"]


def test_chat_stream_ok(monkeypatch):
    fake = FakeOllamaClient(
        chunks=[{"message": {"content": "Hel"}}, {"message": {"content": "lo"}}]
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/chat/stream",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
    assert r.status_code == 200
    assert '{"content": "Hel"}' in r.text
    assert '{"content": "lo"}' in r.text
    assert '"done": true' in r.text


def test_chat_invalid_role_422(monkeypatch):
    with TestClient(app) as client:
        r = client.post(
            "/api/chat", json={"messages": [{"role": "system", "content": "hack"}]}
        )
    assert r.status_code == 422


def test_chat_empty_messages_422(monkeypatch):
    with TestClient(app) as client:
        r = client.post("/api/chat", json={"messages": []})
    assert r.status_code == 422


def test_chat_ollama_unavailable_502_no_leak(monkeypatch):
    fake = FakeOllamaClient(error=RuntimeError("SECRET-INTERNAL"))
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/chat", json={"messages": [{"role": "user", "content": "Hi"}]}
        )
    assert r.status_code == 502
    assert "SECRET-INTERNAL" not in r.text


def test_chat_stream_error_emits_error_event_no_leak(monkeypatch):
    fake = FakeOllamaClient(stream_error=True)
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    with TestClient(app) as client:
        r = client.post(
            "/api/chat/stream",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
    assert r.status_code == 200
    assert '"error"' in r.text
    assert "SECRET-STREAM" not in r.text
