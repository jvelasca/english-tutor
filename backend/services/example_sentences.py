"""Frase de ejemplo determinista para el diccionario de consulta (V3.30).

El diccionario de consulta muestra, junto a la definición generada (Fase B) y a
la marca de uso, una frase real de la app que contiene la palabra buscada. Para
mantenerla **determinista y sin LLM** se reutiliza el banco oficial de read-aloud
del nivel (`curriculum/pronunciation_corpus.json`) aplicando la misma alineación
`unit_produced` del micro-drill (V20-01) sobre el banco completo.

Diferencia clave con el micro-drill: aquí la plantilla neutra «Say the word …»
(que el drill usa cuando el banco no contiene la palabra) **no es un ejemplo** y
nunca se devuelve; si no hay frase real, `example_for` devuelve `None`.
"""

from __future__ import annotations

from services.phonetics import unit_produced
from services.pronunciation_routes import PRONUNCIATION_CORPUS


def example_for(word: str) -> dict | None:
    """Frase real del banco de la app que contiene `word` (None si no existe).

    Devuelve `{"phrase": str, "source": "pronunciation_corpus", "level": str}`.
    Fuente pura y determinista: delega en `example_for_many` sobre todo el banco
    (`level=None`) y descarta el fallback de plantilla.
    """
    cleaned = (word or "").strip()
    if not cleaned:
        return None
    return example_for_many([cleaned]).get(cleaned)


def example_for_many(words: list[str]) -> dict[str, dict | None]:
    """Frase de ejemplo de VARIAS palabras en una sola pasada al banco (V3.39).

    Misma semántica que `example_for` palabra a palabra — para cada una, la
    PRIMERA frase del banco (en su orden) que la contiene con la alineación
    `unit_produced`, y `None` si ninguna —, pero recorriendo el corpus una sola
    vez: la cola de repaso servía hasta `REVIEW_QUEUE_MAX_LIMIT` palabras y
    pagaba un recorrido completo del banco por cada una (P2 de la auditoría).

    Además CORTA en cuanto todas las palabras quedan resueltas, que en la
    práctica ocurre en las primeras frases. Claves: las palabras normalizadas
    (sin duplicados); `None` para las que no tienen ejemplo real. Pura.
    """
    wanted = sorted({(word or "").strip() for word in words if (word or "").strip()})
    if not wanted:
        return {}
    result: dict[str, dict | None] = dict.fromkeys(wanted)
    pending = list(wanted)
    for item in PRONUNCIATION_CORPUS:
        if not pending:
            break
        script = (item.get("script") or "").strip()
        if not script:
            continue
        unresolved: list[str] = []
        for word in pending:
            if unit_produced(word, script):
                result[word] = {
                    "phrase": script,
                    "source": "pronunciation_corpus",
                    "level": item.get("level", ""),
                }
            else:
                unresolved.append(word)
        pending = unresolved
    return result
