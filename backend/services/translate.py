"""Traducción EN→ES a demanda con el modelo local.

Es una ayuda de apoyo en pantallas de práctica (listening, speaking,
pronunciación): el alumno traduce solo cuando duda. Por diseño NO registra
evidencia, no cuenta como intento y no mueve ninguna métrica ni puerta de
dominio.

Elección de modelo: la traducción es interactiva y debe responder en pocos
segundos, así que se prefiere un modelo ligero e instalado (llama3.1:8b o
qwen2.5-coder:1.5b) al modelo por defecto del chat (qwen3.5:9b), que en CPU
tarda decenas de segundos por frase y se descarga/recarga entre llamadas. Si no
hay ningún modelo rápido instalado, se cae al modelo por defecto.

Caché: en memoria, por frase. Los textos de práctica se repiten mucho (repaso,
rutas, dictados) y la primera traducción de una frase es la única que paga la
latencia del modelo.
"""

from __future__ import annotations

import time

from config import DEFAULT_MODEL
from schemas.chat import ChatMessage
from services import llm
from services.llm import chat_once

MAX_SOURCE_CHARS = 800

# Modelos candidatos para la traducción interactiva, en orden de preferencia.
# Deben estar instalados en Ollama; si ninguno lo está se usa DEFAULT_MODEL.
PREFERRED_TRANSLATION_MODELS = (
    "llama3.1:8b",
    "qwen2.5-coder:1.5b",
)

_SYSTEM_PROMPT = (
    "You are a professional translator from English into Spanish. "
    "The user sends a short English phrase that appears in a language-learning "
    "app (a question, a listening transcript or a reference sentence). "
    "Reply with ONLY its natural translation into neutral Spanish. "
    "Do not add explanations, notes, quotation marks or the original text."
)

# Frase exacta (texto recortado) → traducción ES.
_cache: dict[str, str] = {}

# Modelos instalados vistos la última vez (para no consultar a Ollama en cada
# frase): set[str] o None si aún no se ha consultado.
_installed: set[str] | None = None
_installed_at = 0.0
_INSTALLED_TTL_SECONDS = 300.0


async def installed_models() -> set[str]:
    """Devuelve los modelos instalados, con caché de pocos minutos."""
    global _installed, _installed_at
    now = time.monotonic()
    if _installed is None or now - _installed_at > _INSTALLED_TTL_SECONDS:
        try:
            _installed = set(await llm.list_models())
        except Exception:  # noqa: BLE001
            # Ollama caído: conserva lo que hubiera y reintenta pronto.
            _installed = _installed or set()
            _installed_at = now - (_INSTALLED_TTL_SECONDS - 60)
        else:
            _installed_at = now
    return _installed


async def pick_model(explicit: str | None) -> str:
    """Elige el modelo: el explícito si se aporta, si no el más rápido instalado."""
    if explicit:
        return explicit
    for candidate in PREFERRED_TRANSLATION_MODELS:
        if candidate in await installed_models():
            return candidate
    return DEFAULT_MODEL


async def translate_text(text: str, model: str | None = None) -> str:
    """Devuelve la traducción al español de `text` (con caché por frase)."""
    source = text.strip()
    if not source:
        raise ValueError("text vacío")
    if len(source) > MAX_SOURCE_CHARS:
        source = source[:MAX_SOURCE_CHARS]

    cached = _cache.get(source)
    if cached is not None:
        return cached

    chosen = await pick_model(model)
    reply = await chat_once(
        messages=[ChatMessage(role="user", content=source)],
        model=chosen,
        temperature=0.0,
        system_prompt=_SYSTEM_PROMPT,
    )
    translation = reply.content.strip()
    if not translation:
        raise RuntimeError("el modelo devolvió una traducción vacía")

    _cache[source] = translation
    return translation
