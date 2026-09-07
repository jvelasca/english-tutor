"""Tests de GET /api/models: excluye los modelos marcados como no utilizables
(config.UNUSABLE_MODELS) para que el selector de Ajustes → IA no ofrezca un
modelo que no se puede usar (instalado en Ollama pero demasiado lento)."""
from fastapi.testclient import TestClient

import config
from main import app


def _ollama_models(*names):
    async def fake():
        return list(names)

    return fake


def test_models_excludes_unusable(monkeypatch):
    installed = [
        "llama3.1:8b",
        "qwen3-coder:30b",
        "qwen3.5:9b",  # marcado como no utilizable
        "qwen2.5-coder:1.5b",
    ]
    monkeypatch.setattr("routers.models.list_ollama_models", _ollama_models(*installed))
    with TestClient(app) as client:
        r = client.get("/api/models")
    assert r.status_code == 200
    models = r.json()["models"]
    assert config.UNUSABLE_MODELS.isdisjoint(models)
    assert set(models) == {"llama3.1:8b", "qwen3-coder:30b", "qwen2.5-coder:1.5b"}


def test_models_empty_when_all_unusable(monkeypatch):
    monkeypatch.setattr(
        "routers.models.list_ollama_models", _ollama_models(*config.UNUSABLE_MODELS),
    )
    with TestClient(app) as client:
        r = client.get("/api/models")
    assert r.status_code == 200
    assert r.json()["models"] == []


def test_unusable_models_are_subset_of_installed_default_policy():
    # Guardia de coherencia: el modelo por defecto nunca debe estar bloqueado.
    assert config.DEFAULT_MODEL not in config.UNUSABLE_MODELS


def test_models_exposes_default_model(monkeypatch):
    """V3.21 (V20-05): /api/models expone `default_model` (fuente única) para
    que el frontend no duplique la constante del modelo por defecto."""
    installed = [config.DEFAULT_MODEL, "qwen3-coder:30b"]
    monkeypatch.setattr(
        "routers.models.list_ollama_models", _ollama_models(*installed)
    )
    with TestClient(app) as client:
        r = client.get("/api/models")
    assert r.status_code == 200
    body = r.json()
    assert body["default_model"] == config.DEFAULT_MODEL
    assert config.DEFAULT_MODEL in body["models"]
