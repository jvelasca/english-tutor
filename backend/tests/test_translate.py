"""Tests de la traducción de apoyo EN→ES: servicio (caché por frase) y endpoint.

La traducción es una ayuda a demanda que no registra evidencia ni cuenta como
intento: el servicio es una llamada best-effort al modelo local.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

import services.translate as translate_service
from main import app
from schemas.chat import ChatResponse


@pytest.fixture(autouse=True)
def _clear_cache():
    """La caché por frase es global; se limpia para que cada test sea hermético."""
    translate_service._cache.clear()
    yield
    translate_service._cache.clear()


def _fake_chat_once(calls):
    async def fake(messages, model, temperature, mode="default", system_prompt=None):
        calls.append((model, messages[-1].content))
        return ChatResponse(
            model=model,
            content="Un banco",
            total_duration_ms=10,
            prompt_eval_count=1,
            eval_count=1,
        )

    return fake


# --- Servicio -----------------------------------------------------------------


def test_translate_text_returns_spanish(monkeypatch):
    calls = []
    monkeypatch.setattr(translate_service, "chat_once", _fake_chat_once(calls))
    result = asyncio.run(
        translate_service.translate_text("Where is the bank?", "qwen3.5:9b")
    )
    assert result == "Un banco"
    assert len(calls) == 1
    assert calls[0][0] == "qwen3.5:9b"


def test_translate_text_cache_avoids_second_call(monkeypatch):
    calls = []
    monkeypatch.setattr(translate_service, "chat_once", _fake_chat_once(calls))
    asyncio.run(translate_service.translate_text("How many people are there?", "qwen3.5:9b"))
    asyncio.run(translate_service.translate_text("How many people are there?", "qwen3.5:9b"))
    assert len(calls) == 1  # la segunda vez sale de la caché, sin llamada LLM


def test_translate_text_ignores_whitespace_for_cache(monkeypatch):
    calls = []
    monkeypatch.setattr(translate_service, "chat_once", _fake_chat_once(calls))
    asyncio.run(translate_service.translate_text("Nice to meet you.", "qwen3.5:9b"))
    asyncio.run(translate_service.translate_text("  Nice to meet you.  ", "qwen3.5:9b"))
    assert len(calls) == 1


def test_translate_text_empty_raises():
    with pytest.raises(ValueError):
        asyncio.run(translate_service.translate_text("   ", "qwen3.5:9b"))


# --- Endpoint -----------------------------------------------------------------


def test_translate_endpoint_returns_translation(monkeypatch):
    calls = []
    monkeypatch.setattr(translate_service, "chat_once", _fake_chat_once(calls))
    with TestClient(app) as client:
        r = client.post("/api/translate", json={"text": "Where is the bank?"})
    assert r.status_code == 200
    assert r.json() == {"translation": "Un banco"}


def test_translate_endpoint_empty_text_422():
    with TestClient(app) as client:
        r = client.post("/api/translate", json={"text": "  "})
    assert r.status_code == 422


def test_translate_endpoint_llm_down_502(monkeypatch):
    async def broken(messages, model, temperature, mode="default", system_prompt=None):
        raise RuntimeError("ollama caído")

    monkeypatch.setattr(translate_service, "chat_once", broken)
    with TestClient(app) as client:
        r = client.post("/api/translate", json={"text": "Where is the bank?"})
    assert r.status_code == 502
