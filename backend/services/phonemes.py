"""Conversión grapheme→phoneme (ARPAbet) y precisión de fonemas (puro, determinista).

Diccionario local compacto de inglés + fallback letra-a-letra para palabras fuera
de vocabulario, de modo que `to_phonemes` nunca falla. La precisión de fonemas
compara la secuencia de fonemas de lo esperado y lo oído con distancia de edición
(Levenshtein). Es un proxy de la pronunciación real, sin audio: mantiene el score
compuesto existente como señal principal.
"""
from __future__ import annotations

from difflib import SequenceMatcher

# Diccionario grapheme→phoneme (ARPAbet) compacto. Cubre el vocabulario de uso
# frecuente del currículum A1/A2; para palabras fuera de vocabulario se usa el
# fallback letra-a-letra, así que `to_phonemes` nunca falla.
G2P: dict[str, tuple[str, ...]] = {
    "hello": ("HH", "AH", "L", "OW"),
    "world": ("W", "ER", "L", "D"),
    "name": ("N", "EY", "M"),
    "student": ("S", "T", "UW", "D", "AH", "N", "T"),
    "live": ("L", "IH", "V"),
    "city": ("S", "IH", "T", "IY"),
    "job": ("JH", "AA", "B"),
    "family": ("F", "AE", "M", "AH", "L", "IY"),
    "hobby": ("HH", "AA", "B", "IY"),
    "i": ("AY",),
    "am": ("AE", "M"),
    "a": ("AH",),
    "the": ("DH", "AH"),
    "is": ("IH", "Z"),
    "are": ("AA", "R"),
    "was": ("W", "AH", "Z"),
    "have": ("HH", "AE", "V"),
    "has": ("HH", "AE", "Z"),
    "twenty": ("T", "W", "EH", "N", "T", "IY"),
    "years": ("Y", "IH", "R", "Z"),
    "old": ("OW", "L", "D"),
    "my": ("M", "AY"),
    "your": ("Y", "AO", "R"),
    "he": ("HH", "IY"),
    "she": ("SH", "IY"),
    "it": ("IH", "T"),
    "we": ("W", "IY"),
    "they": ("DH", "EY"),
    "and": ("AE", "N", "D"),
    "in": ("IH", "N"),
    "on": ("AA", "N"),
    "at": ("AE", "T"),
    "from": ("F", "R", "AH", "M"),
    "to": ("T", "UW"),
    "for": ("F", "AO", "R"),
    "cheap": ("CH", "IY", "P"),
    "expensive": ("IH", "K", "S", "P", "EH", "N", "S", "IH", "V"),
    "delighted": ("D", "IH", "L", "AY", "T", "IH", "D"),
    "happy": ("HH", "AE", "P", "IY"),
    "sad": ("S", "AE", "D"),
    "exam": ("IH", "G", "Z", "AE", "M"),
    "restaurant": ("R", "EH", "S", "T", "R", "AA", "N", "T"),
    "meal": ("M", "IY", "L"),
    "very": ("V", "EH", "R", "IY"),
    "only": ("OW", "N", "L", "IY"),
    "not": ("N", "AA", "T"),
    "what": ("W", "AH", "T"),
    "where": ("W", "EH", "R"),
    "when": ("W", "EH", "N"),
    "why": ("W", "AY"),
    "how": ("HH", "AW"),
    "you": ("Y", "UW"),
    "this": ("DH", "IH", "S"),
    "that": ("DH", "AE", "T"),
    "do": ("D", "UW"),
    "does": ("D", "AH", "Z"),
    "did": ("D", "IH", "D"),
    "go": ("G", "OW"),
    "goes": ("G", "OW", "Z"),
    "went": ("W", "EH", "N", "T"),
    "like": ("L", "AY", "K"),
    "likes": ("L", "AY", "K", "S"),
    "want": ("W", "AA", "N", "T"),
    "wants": ("W", "AA", "N", "T", "S"),
    "buy": ("B", "AY"),
    "bought": ("B", "AO", "T"),
    "play": ("P", "L", "EY"),
    "playing": ("P", "L", "EY", "IH", "NG"),
    "work": ("W", "ER", "K"),
    "working": ("W", "ER", "K", "IH", "NG"),
}


def to_phonemes(text: str) -> list[str]:
    """Convierte texto en la secuencia plana de fonemas ARPAbet de sus palabras.

    Tokeniza con `services.phonetics.tokenize`, mapea cada palabra con `G2P` y, para
    las fuera de vocabulario, usa cada letra como "fonema" propio (fallback)."""
    from services.phonetics import tokenize

    phonemes: list[str] = []
    for word in tokenize(text):
        phonemes.extend(G2P.get(word, tuple(word)))
    return phonemes


def levenshtein(a: list[str], b: list[str]) -> int:
    """Distancia de edición clásica (Levenshtein) entre dos secuencias."""
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            curr.append(
                min(
                    curr[j - 1] + 1,  # inserción
                    prev[j] + 1,  # borrado
                    prev[j - 1] + (0 if ca == cb else 1),  # sustitución
                )
            )
        prev = curr
    return prev[-1]


def phoneme_accuracy(expected: str, heard: str) -> float:
    """Precisión (0..1) de la secuencia de fonemas de lo oído frente a lo esperado.

    ``1 - lev / max(1, len(ep))`` clampeado a [0, 1] y redondeado a 3 decimales.
    ``ep``/``hp`` son `to_phonemes(expected)`/`to_phonemes(heard)`."""
    ep = to_phonemes(expected)
    hp = to_phonemes(heard)
    lev = levenshtein(ep, hp)
    raw = 1 - lev / max(1, len(ep))
    return round(max(0.0, min(1.0, raw)), 3)


def phoneme_alignment(expected: str, heard: str) -> dict:
    """Alinea fonema a fonema las secuencias de lo esperado y lo oído.

    Espejo de `services.phonetics.word_alignment` pero sobre las listas de fonemas
    (`to_phonemes`). Devuelve `{correct, missing, extra, substituted, total}` con
    `substituted` como lista de `{"expected": fonema, "heard": fonema}` y
    `total = len(ep)`. En un bloque `replace` de longitudes distintas, el excedente
    de `ep` va a `missing` y el de `hp` a `extra`."""
    ep = to_phonemes(expected)
    hp = to_phonemes(heard)
    correct: list[str] = []
    missing: list[str] = []
    extra: list[str] = []
    substituted: list[dict] = []
    sm = SequenceMatcher(None, ep, hp, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            correct.extend(ep[i1:i2])
        elif tag == "delete":
            missing.extend(ep[i1:i2])
        elif tag == "insert":
            extra.extend(hp[j1:j2])
        elif tag == "replace":
            es = ep[i1:i2]
            hs = hp[j1:j2]
            substituted.extend(
                {"expected": e, "heard": h} for e, h in zip(es, hs, strict=False)
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
        "total": len(ep),
    }


def syllables(word: str) -> int:
    """Cuenta grupos vocálicos (`aeiouy`) como proxy determinista de sílabas.

    No resuelve "e" muda ni diptongos; es un proxy de ritmo, no un silabeador
    exacto. Devuelve al menos 1."""
    groups = 0
    prev_vowel = False
    for ch in word.lower():
        is_vowel = ch in "aeiouy"
        if is_vowel and not prev_vowel:
            groups += 1
        prev_vowel = is_vowel
    return max(1, groups)


def prosody_score(expected: str, heard: str) -> float:
    """Ratio (0..1) de palabras esperadas cuyo patrón silábico coincide con el de
    alguna palabra oída no reutilizada (greedy, espejo de `phonetic_similarity`).

    Proxy de prosodia (ritmo silábico) sin audio: el acento de palabra y la
    entonación no son observables desde la transcripción ortográfica."""
    from services.phonetics import tokenize

    e = tokenize(expected)
    h = tokenize(heard)
    if not e:
        return 1.0 if not h else 0.0
    h_syllables = [syllables(w) for w in h]
    used = [False] * len(h_syllables)
    matched = 0
    for ew in e:
        target = syllables(ew)
        for i, hs in enumerate(h_syllables):
            if not used[i] and hs == target:
                matched += 1
                used[i] = True
                break
    return matched / len(e)
