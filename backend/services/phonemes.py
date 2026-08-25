"""Conversión grapheme→phoneme (ARPAbet) y precisión de fonemas (puro, determinista).

Diccionario local compacto de inglés + fallback letra-a-letra para palabras fuera
de vocabulario, de modo que `to_phonemes` nunca falla. La precisión de fonemas
compara la secuencia de fonemas de lo esperado y lo oído con distancia de edición
(Levenshtein). Es un proxy de la pronunciación real, sin audio: mantiene el score
compuesto existente como señal principal.
"""
from __future__ import annotations

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
