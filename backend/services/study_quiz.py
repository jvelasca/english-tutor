"""Opciones de «¿Cuál es?» para la lección de Estudiar.

Las falsas salen del diccionario entero, no de las otras palabras de la
sesión: en un mazo temático esas delatan la respuesta. Se prefieren las de
un número de sílabas parecido al de la respuesta correcta. EN→ES responde
con traducciones; ES→EN responde con lemas ingleses. No escribe léxico,
FSRS ni la lección.
"""
from __future__ import annotations

import hashlib

from repositories import dictionary as dictionary_repo
from services.phonemes import syllables

_NEED = 5
_BANDS = (6, 16, 80)
_ACCENTS = str.maketrans("áéíóúüÁÉÍÓÚÜ", "aeiouuAEIOUU")


def _syllables(text: str) -> int:
    return syllables(text.translate(_ACCENTS))


def rank_distractors(
    correct: str,
    pool: list[str],
    exclude: list[str],
    *,
    need: int = _NEED,
) -> list[str]:
    """Hasta `need` traducciones distintas, las más cercanas en sílabas primero.

    Si no hay bastantes tan parecidas, se rellena con el resto del banco.
    """
    target = " ".join((correct or "").split())
    if not target:
        return []
    banned = {target.casefold()}
    for text in exclude:
        key = " ".join(str(text or "").split()).casefold()
        if key:
            banned.add(key)
    seen: set[str] = set()
    unique: list[str] = []
    for raw in pool:
        text = " ".join(str(raw or "").split())
        key = text.casefold()
        if not text or key in banned or key in seen:
            continue
        seen.add(key)
        unique.append(text)
    target_syllables = _syllables(target)
    target_length = len(target)
    unique.sort(
        key=lambda text: (
            abs(_syllables(text) - target_syllables),
            abs(len(text) - target_length),
            text.casefold(),
        )
    )
    close = [text for text in unique if abs(_syllables(text) - target_syllables) <= 1]
    chosen = close[:need]
    if len(chosen) < need:
        for text in unique:
            if text in chosen:
                continue
            chosen.append(text)
            if len(chosen) >= need:
                break
    return chosen


def _shuffle(values: list[str], seed: str) -> list[str]:
    out = list(values)
    state = int.from_bytes(hashlib.sha256(seed.encode("utf-8")).digest()[:8], "big")
    for index in range(len(out) - 1, 0, -1):
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        swap = state % (index + 1)
        out[index], out[swap] = out[swap], out[index]
    return out


def _pool_for(correct: str, *, english: bool) -> list[str]:
    length = max(len(correct), 1)
    found: list[str] = []
    seen: set[str] = set()
    near = dictionary_repo.words_near if english else dictionary_repo.translations_near
    for band in _BANDS:
        for text in near(length, band=band):
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            found.append(text)
        if len(found) >= 40:
            break
    return found


def quiz_choices(
    word: str,
    translation: str,
    exclude: list[str] | None = None,
    direction: str = "en-es",
) -> list[str] | None:
    """Seis textos (la correcta y cinco falsas), o None si no hay respuesta.

    Con un diccionario corto puede devolver menos de seis, nunca solo la correcta.
    `es-en` usa lemas ingleses; cualquier otro valor sigue con traducciones.
    """
    reverse = direction == "es-en"
    correct = " ".join(((word if reverse else translation) or "").split())
    if not correct:
        return None
    distractors = rank_distractors(
        correct, _pool_for(correct, english=reverse), list(exclude or [])
    )
    if not distractors:
        return None
    seed = (translation if reverse else word) or correct
    return _shuffle([correct, *distractors], seed)
