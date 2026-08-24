"""Detección de errores gramaticales comunes (puro, determinista, heurística v1).

Cada regla declara un nivel de confianza (`confidence`, 0.0–1.0). Un hallazgo con
confianza por debajo de `CONFIRMED_THRESHOLD` se considera "candidato" (no
confirmado) y no debe alimentar la personalización del tutor como si fuera un
error real. Esto deja espacio para verificación futura (p. ej. por LLM).
"""
from __future__ import annotations

import re

# Por debajo de este umbral, el hallazgo es un "candidato", no un error confirmado.
CONFIRMED_THRESHOLD = 0.8

RULES: list[dict] = [
    {
        "rule": "he_she_it_s",
        "message": "Falta la -s en la 3ª persona singular (he/she/it).",
        "confidence": 0.9,
        "pattern": re.compile(
            r"\b(he|she|it)\s+(go|do|have|like|want|need|know|work|play|say|"
            r"think|make|come|look|use|take|run|walk|eat|drink)\b",
            re.IGNORECASE,
        ),
    },
    {
        "rule": "a_an",
        "message": "Usa 'an' antes de sonido vocálico.",
        "confidence": 0.5,
        "pattern": re.compile(
            r"\ba\s+(?!(?:uni|use|one|eu))([aeiou][a-z]+)\b", re.IGNORECASE
        ),
    },
    {
        "rule": "double_negative",
        "message": "Doble negación: usa una sola negación.",
        "confidence": 0.85,
        "pattern": re.compile(
            r"\b(?:don'?t|do\s+not|can'?t|cannot|doesn'?t|does\s+not|won'?t|"
            r"isn'?t|aren'?t|ain'?t)\b[^.!?]*?\b(no|nothing|nobody|none|nowhere)\b",
            re.IGNORECASE,
        ),
    },
    {
        "rule": "there_their_theyre",
        "message": "Confusión entre there, their y they're.",
        "confidence": 0.7,
        "pattern": re.compile(
            r"\btheir\s+(?:going|coming|are|is|was|were|nice|good|happy|here|"
            r"right|wrong)\b|\bthere\s+(?:car|house|friend|book|name|job|"
            r"family|dog|cat|mother|father)\b",
            re.IGNORECASE,
        ),
    },
    {
        "rule": "your_youre",
        "message": "Confusión entre your y you're.",
        "confidence": 0.7,
        "pattern": re.compile(
            r"\byour\s+(?:going|welcome|nice|right|wrong|doing|awesome|amazing|"
            r"great|kind|correct)\b|\byoure\b",
            re.IGNORECASE,
        ),
    },
    {
        "rule": "capitalization_i",
        "message": "El pronombre 'I' va en mayúscula.",
        "confidence": 0.95,
        "pattern": re.compile(r"\bi\b"),
    },
    {
        "rule": "to_too",
        "message": "Usa 'too' para 'demasiado/también'.",
        "confidence": 0.6,
        "pattern": re.compile(
            r"\bto\s+(?:much|many|late|early|far|big|small|easy|hard|slow|fast)\b",
            re.IGNORECASE,
        ),
    },
]


def find_errors(text: str) -> list[dict]:
    """Devuelve los errores detectados, como máximo uno por regla. Cada dict:
    `{"rule", "message", "example", "confidence", "source", "confirmed"}`.
    `confirmed` es True solo si la confianza de la regla supera el umbral."""
    findings: list[dict] = []
    seen: set[str] = set()
    for rule in RULES:
        m = rule["pattern"].search(text)
        if m and rule["rule"] not in seen:
            seen.add(rule["rule"])
            findings.append(
                {
                    "rule": rule["rule"],
                    "message": rule["message"],
                    "example": m.group(0).strip(),
                    "confidence": rule["confidence"],
                    "source": "heuristic",
                    "confirmed": rule["confidence"] >= CONFIRMED_THRESHOLD,
                }
            )
    return findings
