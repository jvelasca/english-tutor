"""Evaluadores fonéticos compuestos para pronunciación (puros, deterministas).

Combina precisión por palabra (alineación), similitud fonética (Soundex) y
similitud de caracteres para puntuar una lectura frente a lo esperado.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from services.phonemes import phoneme_accuracy

# Pesos del score compuesto (deben sumar 1.0).
W_WORD = 0.6
W_PHONETIC = 0.3
W_CHAR = 0.1

_SOUNDEX_MAP = {
    "b": "1", "f": "1", "p": "1", "v": "1",
    "c": "2", "g": "2", "j": "2", "k": "2", "q": "2", "s": "2", "x": "2", "z": "2",
    "d": "3", "t": "3",
    "l": "4",
    "m": "5", "n": "5",
    "r": "6",
}


def tokenize(text: str) -> list[str]:
    """Normaliza y trocea en palabras: minúsculas y sin puntuación."""
    return re.findall(r"[a-z0-9']+", text.lower())


def soundex(word: str) -> str:
    """Codificación Soundex clásica simplificada (letra + 3 dígitos).

    - Conserva la primera letra en mayúscula.
    - Mapea el resto de consonantes según `_SOUNDEX_MAP`; vocales se descartan y
      reinician el dígito anterior (evita colapsar dobles separados por vocal).
    - `h` y `w` se descartan sin reiniciar (no separan dobles).
    - Se truncan/rellenan a 3 dígitos.
    Ejemplos: hello→H400, world→W643, coffee→C100, helo→H400.
    """
    w = word.lower()
    if not w:
        return ""
    first = w[0].upper()
    digits = ""
    prev = ""
    for ch in w[1:]:
        if ch in "hw":
            continue
        code = _SOUNDEX_MAP.get(ch)
        if code is None:
            prev = ""
            continue
        if code != prev:
            digits += code
            prev = code
    return first + (digits + "000")[:3]


def word_alignment(expected: str, heard: str) -> dict:
    """Alinea palabra a palabra con SequenceMatcher sobre listas de tokens."""
    e = tokenize(expected)
    h = tokenize(heard)
    correct: list[str] = []
    missing: list[str] = []
    extra: list[str] = []
    substituted: list[dict] = []
    sm = SequenceMatcher(None, e, h, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            correct.extend(e[i1:i2])
        elif tag == "delete":
            missing.extend(e[i1:i2])
        elif tag == "insert":
            extra.extend(h[j1:j2])
        elif tag == "replace":
            es = e[i1:i2]
            hs = h[j1:j2]
            substituted.extend(
                {"expected": ew, "heard": hw}
                for ew, hw in zip(es, hs, strict=False)
            )
            if len(es) > len(hs):
                missing.extend(es[len(hs):])
            elif len(hs) > len(es):
                extra.extend(hs[len(es):])
    return {
        "correct": correct,
        "missing": missing,
        "extra": extra,
        "substituted": substituted,
        "total": len(e),
    }


def word_accuracy(expected: str, heard: str) -> float:
    """Ratio (0-1) de palabras esperadas dichas correctamente."""
    e = tokenize(expected)
    h = tokenize(heard)
    if not e:
        return 1.0 if not h else 0.0
    sm = SequenceMatcher(None, e, h, autojunk=False)
    matched = sum(i2 - i1 for tag, i1, i2, _, _ in sm.get_opcodes() if tag == "equal")
    return matched / len(e)


def phonetic_similarity(expected: str, heard: str) -> float:
    """Ratio (0-1) de palabras esperadas con Soundex coincidente (greedy, sin
    reutilizar palabras oídas)."""
    e = tokenize(expected)
    h = tokenize(heard)
    if not e:
        return 1.0 if not h else 0.0
    h_keys = [soundex(w) for w in h]
    used = [False] * len(h_keys)
    matched = 0
    for ew in e:
        key = soundex(ew)
        for i, hk in enumerate(h_keys):
            if not used[i] and hk == key:
                matched += 1
                used[i] = True
                break
    return matched / len(e)


def composite_score(expected: str, heard: str) -> dict:
    """Devuelve el score compuesto (0-100), sus componentes y el breakdown.

    Además de `score`, `word_accuracy`, `phonetic_score` y `breakdown`, incluye
    `phoneme_accuracy` (0-100): precisión de la secuencia de fonemas esperados
    frente a lo oído (proxy fonémico sin audio)."""
    wa = word_accuracy(expected, heard)
    ps = phonetic_similarity(expected, heard)
    e = tokenize(expected)
    h = tokenize(heard)
    if e or h:
        char_ratio = SequenceMatcher(None, " ".join(e), " ".join(h)).ratio()
    else:
        char_ratio = 0.0
    score = round(100 * (W_WORD * wa + W_PHONETIC * ps + W_CHAR * char_ratio))
    return {
        "score": score,
        "word_accuracy": round(wa * 100),
        "phonetic_score": round(ps * 100),
        "phoneme_accuracy": round(phoneme_accuracy(expected, heard) * 100),
        "breakdown": word_alignment(expected, heard),
    }
