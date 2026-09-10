"""Pregunta de RECALL del drill (V3.34, Recall 2.0).

Tercer eslabón del Dictionary → Learning Bridge: el peldaño "Recall" de la
escalera compartida de drill. Frente a Recognition (elegir el significado de la
palabra), aquí el alumno hace el camino INVERSO: ve el SIGNIFICADO (cue) y debe
RECUPERAR y teclear la palabra. Es recuperación productiva por texto, sin
micrófono, y por eso no comparte la evidencia de Recognition (informativa) ni la
de Sentence (producción oral).

Reglas de honestidad (puras y deterministas, sin LLM):
- El cue es la traducción de la diana si existe; si no, su definición, pero
  SOLO si esa definición no contiene ya la palabra diana (evitar filtrar la
  respuesta con un cue circular: "bank: a bank is ...").
- Si no hay cue utilizable (palabra sin entrada, sin traducción ni definición
  válida), la pregunta NO está disponible (`None`): el peldaño degrada con
  aviso en lugar de forzar una pregunta que revele la respuesta.
- La función NUNCA devuelve la forma esperada como respuesta: el servidor la
  re-deriva al puntuar y solo la revela tras el intento.
"""

from __future__ import annotations

import re


def _normalize(text: str) -> str:
    """Minúsculas y espacios colapsados (comparación de superficies)."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _definition_leaks_word(definition: str, word: str) -> bool:
    """True si la definición ya contiene la palabra diana como token.

    Un cue que contiene la respuesta la regala (p. ej. definición "a bank is a
    place where..."), así que se descarta. Para unidades de una sola palabra se
    exige coincidencia de palabra completa (evita falsos positivos por
    subcadenas: `run` dentro de `running` no cuenta); para unidades
    multi-palabra se comprueba la subcadena normalizada.
    """
    norm_def = _normalize(definition)
    norm_word = _normalize(word)
    if not norm_def or not norm_word:
        return False
    if " " in norm_word:
        return norm_word in norm_def
    return re.search(rf"\b{re.escape(norm_word)}\b", norm_def) is not None


def recall_prompt_for(word: str, entries: list[dict]) -> dict | None:
    """Cue `{word, cue, cue_kind}` del recall de la palabra, o `None`.

    - Busca la entrada de la diana en la caché global `dictionary_entries`
      (comparación por superficie normalizada).
    - `cue` = `translation` si existe; si no, `definition` siempre que no
      contenga la palabra diana (si la contiene, se descarta: es un spoiler).
    - `cue_kind` es `"translation"` o `"definition"`.
    - `None` si la diana no existe o no hay cue válido (el peldaño degrada con
      aviso, sin evento).
    """
    target_word = _normalize(word)
    if not target_word:
        return None
    target = next(
        (e for e in entries if _normalize(e.get("word") or "") == target_word),
        None,
    )
    if target is None:
        return None

    translation = (target.get("translation") or "").strip()
    if translation:
        return {
            "word": target_word,
            "cue": translation,
            "cue_kind": "translation",
        }

    definition = (target.get("definition") or "").strip()
    if definition and not _definition_leaks_word(definition, target_word):
        return {
            "word": target_word,
            "cue": definition,
            "cue_kind": "definition",
        }
    return None
