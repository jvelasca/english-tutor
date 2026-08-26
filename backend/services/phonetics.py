"""Evaluadores fonéticos compuestos para pronunciación (puros, deterministas).

Combina precisión por palabra (alineación), precisión de fonemas (alineación
grapheme→phoneme), similitud fonética (Soundex) y prosodia proxy (ritmo silábico)
para puntuar una lectura frente a lo esperado. La señal principal es la fonémica.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from services.phonemes import phoneme_accuracy_proxy, phoneme_alignment, prosody_proxy

# Pesos del score compuesto (deben sumar 1.0). La precisión de fonemas y la de
# palabra lideran; Soundex y prosodia aportan señal secundaria. Ya no se usa la
# similitud de caracteres a nivel de texto.
W_WORD = 0.35
W_PHONEME = 0.35
W_PHONETIC = 0.15
W_PROSODY = 0.15

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
    """Devuelve el score compuesto (0-100), sus componentes y los breakdowns.

    Pondera palabra (0.35), fonemas (0.35), Soundex (0.15) y prosodia (0.15).
    Además de `score`, `word_accuracy`, `phonetic_score`, `phoneme_accuracy_proxy`
    y `breakdown` (palabras), incluye `prosody_proxy` (0-100) y `phoneme_breakdown`
    (alineación fonema a fonema). Las señales de fonemas y prosodia son un proxy
    sobre transcripción, marcado con `pronunciation_source: "transcript"`."""
    wa = word_accuracy(expected, heard)
    ps = phonetic_similarity(expected, heard)
    pa = phoneme_accuracy_proxy(expected, heard)
    pro = prosody_proxy(expected, heard)
    score = round(
        100 * (W_WORD * wa + W_PHONEME * pa + W_PHONETIC * ps + W_PROSODY * pro)
    )
    return {
        "score": score,
        "word_accuracy": round(wa * 100),
        "phonetic_score": round(ps * 100),
        "phoneme_accuracy_proxy": round(pa * 100),
        "prosody_proxy": round(pro * 100),
        "pronunciation_source": "transcript",
        "breakdown": word_alignment(expected, heard),
        "phoneme_breakdown": phoneme_alignment(expected, heard),
    }
