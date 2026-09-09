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
def _clear_state(monkeypatch):
    """La caché de frases y la de modelos instalados son globales; se limpian
    para que cada test sea hermético.

    V3.31.1 (P1-01): `pick_model` consulta la lista instalada también cuando
    hay modelo explícito, así que se inyecta por defecto un parque con
    `llama3.1:8b` instalado (los tests que necesiten otro parque lo
    sobrescriben con monkeypatch)."""
    translate_service._cache.clear()
    translate_service._installed = None
    translate_service._installed_at = 0.0
    monkeypatch.setattr(
        translate_service.llm, "list_models", _fake_list_models("llama3.1:8b")
    )
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
    # Con modelo explícito UTILIZABLE E INSTALADO devuelve el explícito (el
    # parque por defecto del fixture incluye llama3.1:8b).
    assert asyncio.run(translate_service.pick_model("llama3.1:8b")) == "llama3.1:8b"


def test_pick_model_explicit_not_installed_falls_back_to_preferred(monkeypatch):
    # V3.31.1 (P1-01): un modelo explícito UTILIZABLE pero NO instalado no
    # puede llegar a Ollama: cae al modelo rápido instalado.
    monkeypatch.setattr(
        translate_service.llm, "list_models",
        _fake_list_models("qwen2.5-coder:1.5b"),
    )
    assert (
        asyncio.run(translate_service.pick_model("llama3.1:8b"))
        == "qwen2.5-coder:1.5b"
    )


def test_pick_model_explicit_not_installed_falls_back_to_first_usable(monkeypatch):
    # Sin preferidos instalados, el explícito no instalado cae al primer
    # modelo instalado y utilizable (nunca al nombre pedido).
    monkeypatch.setattr(
        translate_service.llm, "list_models", _fake_list_models("qwen3-coder:30b"),
    )
    assert (
        asyncio.run(translate_service.pick_model("llama3.1:8b")) == "qwen3-coder:30b"
    )


def test_pick_model_explicit_not_installed_and_no_models_returns_default(monkeypatch):
    # Sin ningún modelo instalado, el explícito (aunque utilizable) no se puede
    # servir: cae al modelo por defecto como cualquier otro fallback.
    monkeypatch.setattr(translate_service.llm, "list_models", _fake_list_models())
    chosen = asyncio.run(translate_service.pick_model("llama3.1:8b"))
    assert chosen == config.DEFAULT_MODEL


def test_pick_model_explicit_unusable_falls_back_to_default(monkeypatch):
    # qwen3.5:9b está marcado como no utilizable (config.UNUSABLE_MODELS): la
    # preferencia explícita no puede saltarse la política → si es lo único
    # instalado, cae al modelo por defecto.
    monkeypatch.setattr(
        translate_service.llm, "list_models",
        _fake_list_models("qwen3.5:9b"),
    )
    chosen = asyncio.run(translate_service.pick_model("qwen3.5:9b"))
    assert chosen == config.DEFAULT_MODEL


def test_pick_model_explicit_unusable_falls_back_to_preferred(monkeypatch):
    # Con un preferido utilizable instalado, el explícito no utilizable cae al
    # modelo rápido instalado (misma política que sin modelo explícito).
    monkeypatch.setattr(
        translate_service.llm, "list_models",
        _fake_list_models("qwen3.5:9b", "llama3.1:8b"),
    )
    assert asyncio.run(translate_service.pick_model("qwen3.5:9b")) == "llama3.1:8b"


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
        translate_service.translate_text("Where is the bank?", "llama3.1:8b")
    )
    assert result == "Un banco"
    assert len(calls) == 1
    assert calls[0][0] == "llama3.1:8b"


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
        translate_service.translate_text("How many people are there?", "llama3.1:8b")
    )
    asyncio.run(
        translate_service.translate_text("How many people are there?", "llama3.1:8b")
    )
    assert len(calls) == 1  # la segunda vez sale de la caché, sin llamada LLM


def test_translate_text_ignores_whitespace_for_cache(monkeypatch):
    calls = []
    monkeypatch.setattr(translate_service, "chat_once", _fake_chat_once(calls))
    asyncio.run(
        translate_service.translate_text("Nice to meet you.", "llama3.1:8b")
    )
    asyncio.run(
        translate_service.translate_text("  Nice to meet you.  ", "llama3.1:8b")
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
            json={"text": "Where is the bank?", "model": "llama3.1:8b"},
        )
    assert r.status_code == 200
    assert calls[0][0] == "llama3.1:8b"


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
