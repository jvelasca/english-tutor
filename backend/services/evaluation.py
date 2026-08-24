"""Evaluación objetiva del tutor (puro, determinista, sin LLM-juez).

Puntúa la respuesta del tutor con señales medibles: `correction` (contiene el
fragmento corregido esperado), `english` (fracción de palabras no españolas),
`conciseness` (longitud) y `engagement` (invita a seguir). No usa un LLM como juez
(premisa 12).
"""
from __future__ import annotations

import re

# Solo palabras inequívocamente españolas (evita falsos positivos con "a", "no",
# "me", "son", etc., que también existen en inglés).
SPANISH_WORDS: set[str] = {
    "porque", "cuando", "donde", "usted", "nosotros", "ellos", "ellas",
    "también", "tiene", "tienen", "hace", "hacer", "puede", "pueden", "pero",
    "muy", "bien", "hay", "ser", "estar", "tener", "más", "está", "están",
    "sí", "cómo", "qué", "cuál", "quién", "dónde", "cuándo", "después",
    "antes", "ahora", "aquí", "allí", "gracias", "hola", "adiós", "buenos",
    "buenas", "días", "noches", "mañana", "noche", "día", "año", "años",
}

FRIENDLY_MARKERS: tuple[str, ...] = (
    "great", "good", "nice", "well done", "excellent", "perfect", "correct",
    "almost", "try again", "let's", "keep going", "awesome", "fantastic",
)

EVAL_CASES: list[dict] = [
    {
        "id": "age",
        "level": "A2",
        "mode": "grammar",
        "student": "I have twenty years old.",
        "expected_fragments": ["am twenty", "am 20 years old"],
    },
    {
        "id": "third_person",
        "level": "A1",
        "mode": "grammar",
        "student": "He go to school every day.",
        "expected_fragments": ["goes to school"],
    },
    {
        "id": "negation",
        "level": "A2",
        "mode": "grammar",
        "student": "She don't like coffee.",
        "expected_fragments": ["doesn't like", "does not like"],
    },
    {
        "id": "article",
        "level": "A1",
        "mode": "grammar",
        "student": "I have a apple.",
        "expected_fragments": ["an apple"],
    },
    {
        "id": "for_since",
        "level": "B1",
        "mode": "grammar",
        "student": "I am here since five years.",
        "expected_fragments": ["for five years"],
    },
    {
        "id": "past_question",
        "level": "B1",
        "mode": "conversation",
        "student": "What you do yesterday?",
        "expected_fragments": ["did you do"],
    },
    {
        "id": "past_tense",
        "level": "A2",
        "mode": "conversation",
        "student": "Yesterday I go to the cinema.",
        "expected_fragments": ["went to the cinema"],
    },
    {
        "id": "modal",
        "level": "A2",
        "mode": "conversation",
        "student": "She can to swim very fast.",
        "expected_fragments": ["can swim"],
    },
]


def normalize(text: str) -> str:
    """Minúsculas y sin puntuación (para comparar fragmentos)."""
    return re.sub(r"[^a-z0-9áéíóúñü ]", " ", text.lower())


def _words(text: str) -> list[str]:
    return re.findall(r"[a-záéíóúñü]+", text.lower())


def contains_fragment(reply: str, fragment: str) -> bool:
    """True si la respuesta contiene el fragmento (sin mayúsculas/puntuación)."""
    return normalize(fragment).strip() in normalize(reply)


def contains_any_fragment(reply: str, fragments: list[str]) -> bool:
    return any(contains_fragment(reply, f) for f in fragments)


def spanish_word_ratio(text: str) -> float:
    words = _words(text)
    if not words:
        return 0.0
    spanish = sum(1 for w in words if w in SPANISH_WORDS)
    return round(spanish / len(words), 2)


def english_word_ratio(text: str) -> float:
    return round(1.0 - spanish_word_ratio(text), 2)


def conciseness_score(word_count: int) -> int:
    if word_count <= 0:
        return 0
    if word_count < 10:
        return 50
    if word_count <= 180:
        return 100
    if word_count <= 400:
        return 70
    return 40


def engagement_score(reply: str) -> int:
    if "?" in reply:
        return 100
    normalized = normalize(reply)
    if any(marker in normalized for marker in FRIENDLY_MARKERS):
        return 70
    return 0


def evaluate_tutor_reply(reply: str, case: dict | None = None) -> dict:
    """Puntúa una respuesta del tutor (0..100 por señal y total).

    Si hay `case` con `expected_fragments`, añade la señal `correction` y `case_id`.
    Sin case, puntúa solo las señales libres de contexto (english, conciseness,
    engagement).
    """
    english = round(english_word_ratio(reply) * 100)
    conciseness = conciseness_score(len(_words(reply)))
    engagement = engagement_score(reply)

    signals: dict = {
        "english": english,
        "conciseness": conciseness,
        "engagement": engagement,
    }
    correction: int | None = None
    if case and case.get("expected_fragments"):
        correction = (
            100 if contains_any_fragment(reply, case["expected_fragments"]) else 0
        )
        signals["correction"] = correction

    if correction is not None:
        total = round(
            0.5 * correction + 0.2 * english + 0.15 * conciseness + 0.15 * engagement
        )
    else:
        total = round(0.5 * english + 0.25 * conciseness + 0.25 * engagement)

    result = {**signals, "total": total}
    if case:
        result["case_id"] = case["id"]
    return result


def summarize(results: list[dict]) -> dict:
    """Agrega los resultados de una tanda: medias por señal y total."""
    if not results:
        return {
            "cases": 0,
            "avg_total": None,
            "avg_correction": None,
            "avg_english": None,
            "avg_conciseness": None,
            "avg_engagement": None,
        }

    def _avg(key: str) -> float | None:
        vals = [r[key] for r in results if r.get(key) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    return {
        "cases": len(results),
        "avg_total": _avg("total"),
        "avg_correction": _avg("correction"),
        "avg_english": _avg("english"),
        "avg_conciseness": _avg("conciseness"),
        "avg_engagement": _avg("engagement"),
    }
