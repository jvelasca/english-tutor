"""Pista de la lección de Estudiar.

Si la ficha o la palabra no tienen recordatorio, el modelo escribe una pista
corta en español. No es la traducción ni la palabra inglesa, y no cierra la
lección ni agenda FSRS. En ES→EN el alumno ya ve el español y la pista no
puede decir la palabra inglesa. Quien llama decide si la guarda.
"""
from __future__ import annotations

import json
import re

from config import DEFAULT_MODEL
from schemas.chat import ChatMessage
from services.llm import chat_once

MAX_HINT_CHARS = 160
_TEMPERATURE = 0.4
_ATTEMPTS = 2
_WORD_RE = re.compile(r"^[A-Za-z][A-Za-z'\- ]{0,79}$")
_SYSTEM = (
    "You write one short study hint in Spanish for an English learner. "
    'Reply with JSON only: {"hint": "..."}. '
    "The hint helps them deduce the word. "
    "Do not include the English word. Do not include the Spanish translation. "
    "Do not give the answer."
)
_SYSTEM_REVERSE = (
    "You write one short study hint in Spanish for an English learner. "
    'Reply with JSON only: {"hint": "..."}. '
    "The learner already sees the Spanish word and must recall the English word. "
    "Do not include the English word. Do not repeat the Spanish word. "
    "Do not give the answer."
)


class HintUnavailable(RuntimeError):
    """El modelo no respondió o la pista no cumple el contrato."""


def _mentions(text: str, banned: str) -> bool:
    needle = " ".join((banned or "").split()).casefold()
    if len(needle) < 3:
        return False
    return needle in text.casefold()


def parse_hint(raw: str, *, word: str, translation: str) -> str | None:
    """Pista válida, o None si el texto revela la respuesta o no es JSON."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    hint = " ".join(str(obj.get("hint") or "").split())
    if len(hint) < 8 or len(hint) > MAX_HINT_CHARS:
        return None
    if _mentions(hint, word) or _mentions(hint, translation):
        return None
    return hint


def hint_request(
    word: str, translation: str, direction: str = "en-es"
) -> tuple[str, str]:
    """Consigna del modelo: sistema y mensaje, según el sentido de la lección."""
    if direction == "es-en":
        seen = translation.strip() or "(unknown)"
        user = "\n".join(
            [
                f"The learner already sees this Spanish word: {seen}",
                f"They must recall this English word. Do not write it: {word}",
            ]
        )
        return _SYSTEM_REVERSE, user
    lines = [f"English word: {word}"]
    if translation.strip():
        lines.append(f"Do not write this Spanish translation: {translation.strip()}")
    return _SYSTEM, "\n".join(lines)


async def _ask(
    word: str,
    translation: str,
    model: str | None,
    direction: str = "en-es",
) -> str:
    system, user = hint_request(word, translation, direction)
    reply = await chat_once(
        [ChatMessage(role="user", content=user)],
        model or DEFAULT_MODEL,
        _TEMPERATURE,
        system_prompt=system,
    )
    return reply.content


async def fresh_hint(
    word: str,
    translation: str = "",
    *,
    direction: str = "en-es",
    model: str | None = None,
    chat=None,
) -> str | None:
    """Una pista. None si la palabra no es válida.

    Lanza `HintUnavailable` si las dos tentativas fallan.
    """
    cleaned = " ".join((word or "").split())
    if not _WORD_RE.fullmatch(cleaned):
        return None
    meaning = " ".join((translation or "").split())

    async def _call() -> str:
        if chat is not None:
            return await chat(cleaned, meaning, model)
        return await _ask(cleaned, meaning, model, direction)

    for _attempt in range(_ATTEMPTS):
        try:
            raw = await _call()
        except HintUnavailable:
            raise
        except Exception as exc:
            raise HintUnavailable("Modelo no disponible") from exc
        parsed = parse_hint(raw, word=cleaned, translation=meaning)
        if parsed:
            return parsed
    raise HintUnavailable("La pista no cumple el contrato")
