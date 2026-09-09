"""Frase de ejemplo determinista para el diccionario de consulta (V3.30).

El diccionario de consulta muestra, junto a la definición generada (Fase B) y a
la marca de uso, una frase real de la app que contiene la palabra buscada. Para
mantenerla **determinista y sin LLM** se reutiliza el banco oficial de read-aloud
del nivel (`curriculum/pronunciation_corpus.json`) a través de
`services.pronunciation_routes.sentence_context_for`, que ya localiza la primera
frase que contiene la unidad léxica con la misma alineación `unit_produced` del
micro-drill (V20-01).

Diferencia clave con el micro-drill: aquí la plantilla neutra «Say the word …»
(que el drill usa cuando el banco no contiene la palabra) **no es un ejemplo** y
nunca se devuelve; si no hay frase real, `example_for` devuelve `None`.
"""

from __future__ import annotations

from services.pronunciation_routes import sentence_context_for


def example_for(word: str) -> dict | None:
    """Frase real del banco de la app que contiene `word` (None si no existe).

    Devuelve `{"phrase": str, "source": "pronunciation_corpus", "level": str}`.
    Fuente pura y determinista: delega en `sentence_context_for` sobre todo el
    banco (`level=None`) y descarta el fallback de plantilla.
    """
    result = sentence_context_for(word, level=None)
    if result["source"] != "route":
        return None
    return {
        "phrase": result["phrase"],
        "source": "pronunciation_corpus",
        "level": result.get("level", ""),
    }
