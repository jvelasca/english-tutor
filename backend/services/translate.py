"""Traducción EN→ES a demanda con el modelo local.

Es una ayuda de apoyo en pantallas de práctica (listening): el alumno traduce
solo cuando duda. Por diseño NO registra evidencia, no cuenta como intento y no
mueve ninguna métrica ni puerta de dominio.

Usa el modelo Ollama del chat (config.DEFAULT_MODEL por defecto) y mantiene una
caché en memoria por frase: los textos de práctica se repiten mucho (repaso,
rutas, dictados) y la primera traducción de una frase es la única que paga la
latencia del modelo.
"""

from __future__ import annotations

from schemas.chat import ChatMessage
from services.llm import chat_once

MAX_SOURCE_CHARS = 800

_SYSTEM_PROMPT = (
    "You are a professional translator from English into Spanish. "
    "The user sends a short English phrase that appears in a language-learning "
    "app (a question, a listening transcript or a reference sentence). "
    "Reply with ONLY its natural translation into neutral Spanish. "
    "Do not add explanations, notes, quotation marks or the original text."
)

# Frase exacta (normalizada en mayúsculas no; simplemente texto recortado) → ES.
_cache: dict[str, str] = {}


async def translate_text(text: str, model: str) -> str:
    """Devuelve la traducción al español de `text` (con caché por frase)."""
    source = text.strip()
    if not source:
        raise ValueError("text vacío")
    if len(source) > MAX_SOURCE_CHARS:
        source = source[:MAX_SOURCE_CHARS]

    cached = _cache.get(source)
    if cached is not None:
        return cached

    reply = await chat_once(
        messages=[ChatMessage(role="user", content=source)],
        model=model,
        temperature=0.0,
        system_prompt=_SYSTEM_PROMPT,
    )
    translation = reply.content.strip()
    if not translation:
        raise RuntimeError("el modelo devolvió una traducción vacía")

    _cache[source] = translation
    return translation
