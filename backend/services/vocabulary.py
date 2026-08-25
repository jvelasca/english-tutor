"""Extracción de vocabulario del texto del alumno (puro, determinista)."""
from __future__ import annotations

import re

# Palabras funcionales inglesas que no aportan valor como "vocabulario".
EN_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "but", "so", "for", "nor", "yet",
        "of", "in", "on", "at", "to", "by", "with", "from", "into", "over",
        "under", "about", "between", "through", "during", "without",
        "is", "am", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "can",
        "could", "shall", "should", "may", "might", "must",
        "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
        "us", "them", "my", "your", "his", "its", "our", "their", "mine",
        "yours", "hers", "ours", "theirs", "this", "that", "these", "those",
        "what", "which", "who", "whom", "whose", "when", "where", "why",
        "how", "not", "no", "yes", "if", "then", "than", "as", "there",
        "here", "just", "very", "too", "also", "only",
    }
)


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s']", "", text.lower()).strip()


def extract_words(text: str) -> list[str]:
    """Devuelve las palabras únicas (normalizadas, sin stopwords ni tokens de 1
    carácter) ordenadas alfabéticamente."""
    tokens = _normalize(text).split()
    words = {t for t in tokens if len(t) > 1 and t not in EN_STOPWORDS}
    return sorted(words)


# Umbrales de dominio: una palabra se considera "dominada" cuando el alumno la
# ha producido varias veces y en días distintos (producción espaciada).
MASTERY_MIN_PRODUCTIONS = 3
MASTERY_MIN_DAYS = 2


def classify(appearances: int, production_days: int) -> str:
    """Estado de dominio de una palabra según producción.

    - "exposed": nunca producida por el alumno (solo exposición del tutor).
    - "learning": producida al menos una vez, aún sin consolidar.
    - "mastered": producida repetidas veces en días distintos.
    """
    if appearances == 0:
        return "exposed"
    if appearances >= MASTERY_MIN_PRODUCTIONS and production_days >= MASTERY_MIN_DAYS:
        return "mastered"
    return "learning"
