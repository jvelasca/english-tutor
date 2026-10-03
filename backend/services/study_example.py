"""Otra frase para la lección de Estudiar.

No escribe léxico, FSRS, repasos ni `study_lesson_items`. Si el modelo no
responde o la frase no cumple el contrato, se avisa y la tarjeta anterior
se queda.
"""
from __future__ import annotations

import json
import re

from config import DEFAULT_MODEL
from schemas.chat import ChatMessage
from services.llm import chat_once

MAX_PHRASE_CHARS = 240
MAX_TRANSLATION_CHARS = 200
_TEMPERATURE = 0.8
_ATTEMPTS = 2
_WORD_RE = re.compile(r"^[A-Za-z][A-Za-z'\- ]{0,79}$")
_SYSTEM = (
    "You write one short example sentence for an English learner. "
    'Reply with JSON only: {"phrase": "...", "translation": "..."}. '
    "phrase is one English sentence that contains the given word. "
    "translation is that same sentence in Spanish."
)


class ExampleUnavailable(RuntimeError):
    """El modelo no respondió o ninguna frase cumplió el contrato."""


def _contains_word(phrase: str, word: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(word.strip()) + r"(?!\w)"
    return re.search(pattern, phrase, re.IGNORECASE) is not None


def _avoid_set(avoid: list[str] | None) -> set[str]:
    out: set[str] = set()
    for phrase in avoid or []:
        key = " ".join(str(phrase or "").split()).casefold()
        if key:
            out.add(key)
    return out


def parse_example(
    raw: str, *, word: str, avoid: list[str] | None = None
) -> dict | None:
    """Frase válida, o None si el texto no cumple el contrato."""
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
    phrase = " ".join(str(obj.get("phrase") or "").split())
    translation = " ".join(str(obj.get("translation") or "").split())
    if not phrase or not translation:
        return None
    if len(phrase) > MAX_PHRASE_CHARS or len(translation) > MAX_TRANSLATION_CHARS:
        return None
    if not _contains_word(phrase, word):
        return None
    if phrase.casefold() in _avoid_set(avoid):
        return None
    return {"word": word.strip(), "phrase": phrase, "translation": translation}


async def _ask(word: str, avoid: list[str], model: str | None) -> str:
    lines = [f"Word: {word}"]
    if avoid:
        lines.append("Do not repeat these sentences:")
        lines.extend(f"- {phrase}" for phrase in avoid)
    reply = await chat_once(
        [ChatMessage(role="user", content="\n".join(lines))],
        model or DEFAULT_MODEL,
        _TEMPERATURE,
        system_prompt=_SYSTEM,
    )
    return reply.content


async def fresh_example(
    word: str,
    avoid: list[str] | None = None,
    *,
    model: str | None = None,
    chat=None,
) -> dict | None:
    """Una frase nueva. None si la palabra no es válida.

    Lanza `ExampleUnavailable` si las dos tentativas fallan.
    """
    cleaned = " ".join((word or "").split())
    if not _WORD_RE.fullmatch(cleaned):
        return None
    banned = [phrase for phrase in (avoid or []) if str(phrase or "").strip()][:12]
    caller = chat or _ask
    for _attempt in range(_ATTEMPTS):
        try:
            raw = await caller(cleaned, banned, model)
        except ExampleUnavailable:
            raise
        except Exception as exc:
            raise ExampleUnavailable("Modelo no disponible") from exc
        parsed = parse_example(raw, word=cleaned, avoid=banned)
        if parsed:
            return parsed
    raise ExampleUnavailable("La frase no cumple el contrato")
