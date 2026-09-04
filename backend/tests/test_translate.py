"""Tests de la traducción de apoyo EN→ES: servicio (modelo rápido + caché) y
endpoint.

La traducción es una ayuda a demanda que no registra evidencia ni cuenta como
intento: el servicio es una llamada best-effort al modelo local.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

import config
import services.translate as translate_service
from main import app
from schemas.chat import ChatResponse


@pytest.fixture(autouse=True)
def _clear_state():
    """La caché de frases y la de modelos instalados son globales; se limpian
    para que cada test sea hermético."""
    translate_service._cache.clear()
    translate_service._installed = None
    translate_service._installed_at = 0.0
    yield
    translate_service._cache.clear()
    translate_service._installed = None
    translate_service._installed_at = 0.0


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


def _fake_list_models(*names):
    async def fake():
        return list(names)

    return fake


# --- Selección de modelo ------------------------------------------------------


def test_pick_model_uses_explicit(monkeypatch):
    # Con modelo explícito no consulta la lista de instalados.
    assert asyncio.run(translate_service.pick_model("qwen3.5:9b")) == "qwen3.5:9b"


def test_pick_model_prefers_fastest_installed(monkeypatch):
    monkeypatch.setattr(
        translate_service.llm, "list_models",
        _fake_list_models("qwen3.5:9b", "llama3.1:8b"),
    )
    assert asyncio.run(translate_service.pick_model(None)) == "llama3.1:8b"


def test_pick_model_never_picks_unusable_when_only_that_installed(monkeypatch):
    # qwen3.5:9b está marcado como no utilizable (config.UNUSABLE_MODELS):
    # aunque sea lo único instalado, la traducción no lo elige → default.
    monkeypatch.setattr(
        translate_service.llm, "list_models", _fake_list_models("qwen3.5:9b"),
    )
    assert asyncio.run(translate_service.pick_model(None)) == config.DEFAULT_MODEL


def test_pick_model_picks_first_usable_installed(monkeypatch):
    # Sin modelos preferidos, usa el primer modelo instalado y utilizable.
    monkeypatch.setattr(
        translate_service.llm, "list_models", _fake_list_models("qwen3-coder:30b"),
    )
    assert asyncio.run(translate_service.pick_model(None)) == "qwen3-coder:30b"


def test_pick_model_no_models_returns_default(monkeypatch):
    monkeypatch.setattr(
        translate_service.llm, "list_models", _fake_list_models(),
    )
    assert asyncio.run(translate_service.pick_model(None)) == config.DEFAULT_MODEL


def test_pick_model_ollama_down_returns_default(monkeypatch):
    async def broken():
        raise RuntimeError("ollama caído")

    monkeypatch.setattr(translate_service.llm, "list_models", broken)
    assert asyncio.run(translate_service.pick_model(None)) == config.DEFAULT_MODEL


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


def test_translate_text_auto_picks_fast_model(monkeypatch):
    calls = []
    monkeypatch.setattr(translate_service, "chat_once", _fake_chat_once(calls))
    monkeypatch.setattr(
        translate_service.llm, "list_models",
        _fake_list_models("qwen3.5:9b", "llama3.1:8b"),
    )
    asyncio.run(translate_service.translate_text("Where is the bank?"))
    assert calls[0][0] == "llama3.1:8b"


def test_translate_text_cache_avoids_second_call(monkeypatch):
    calls = []
    monkeypatch.setattr(translate_service, "chat_once", _fake_chat_once(calls))
    asyncio.run(
        translate_service.translate_text("How many people are there?", "qwen3.5:9b")
    )
    asyncio.run(
        translate_service.translate_text("How many people are there?", "qwen3.5:9b")
    )
    assert len(calls) == 1  # la segunda vez sale de la caché, sin llamada LLM


def test_translate_text_ignores_whitespace_for_cache(monkeypatch):
    calls = []
    monkeypatch.setattr(translate_service, "chat_once", _fake_chat_once(calls))
    asyncio.run(
        translate_service.translate_text("Nice to meet you.", "qwen3.5:9b")
    )
    asyncio.run(
        translate_service.translate_text("  Nice to meet you.  ", "qwen3.5:9b")
    )
    assert len(calls) == 1


def test_translate_text_empty_raises():
    with pytest.raises(ValueError):
        asyncio.run(translate_service.translate_text("   "))


# --- Endpoint -----------------------------------------------------------------


def test_translate_endpoint_returns_translation(monkeypatch):
    calls = []
    monkeypatch.setattr(translate_service, "chat_once", _fake_chat_once(calls))
    monkeypatch.setattr(
        translate_service.llm, "list_models",
        _fake_list_models("qwen3.5:9b", "llama3.1:8b"),
    )
    with TestClient(app) as client:
        r = client.post("/api/translate", json={"text": "Where is the bank?"})
    assert r.status_code == 200
    assert r.json() == {"translation": "Un banco"}
    # Sin modelo explícito el servidor elige el modelo rápido instalado.
    assert calls[0][0] == "llama3.1:8b"


def test_translate_endpoint_with_explicit_model(monkeypatch):
    calls = []
    monkeypatch.setattr(translate_service, "chat_once", _fake_chat_once(calls))
    with TestClient(app) as client:
        r = client.post(
            "/api/translate",
            json={"text": "Where is the bank?", "model": "qwen3.5:9b"},
        )
    assert r.status_code == 200
    assert calls[0][0] == "qwen3.5:9b"


def test_translate_endpoint_empty_text_422():
    with TestClient(app) as client:
        r = client.post("/api/translate", json={"text": "  "})
    assert r.status_code == 422


def test_translate_endpoint_llm_down_502(monkeypatch):
    async def broken(messages, model, temperature, mode="default", system_prompt=None):
        raise RuntimeError("ollama caído")

    monkeypatch.setattr(translate_service, "chat_once", broken)
    monkeypatch.setattr(
        translate_service.llm, "list_models",
        _fake_list_models("qwen3.5:9b", "llama3.1:8b"),
    )
    with TestClient(app) as client:
        r = client.post("/api/translate", json={"text": "Where is the bank?"})
    assert r.status_code == 502
