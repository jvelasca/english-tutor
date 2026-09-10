"""Pregunta de RECALL del drill (V3.34 → V3.37, cues graduados).

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

V3.37 (cues graduados y automaticidad): la escalera deja de ser un FALLBACK
(traducción y, si no, definición) y pasa a ser una PROGRESIÓN de peldaños
declarados:

    translation (cued) < definition (cued) < cloze (guided)

`recall_prompt_for` sirve el peldaño PEDIDO (o el de V3.34 cuando no se pide
ninguno, para no romper clientes antiguos); `next_recall_rung` decide el peldaño
siguiente a partir de los ÉXITOS ya registrados en el ledger por peldaño
(`drill:recall:<peldaño>`); y `resolve_recall_cue` separa la decisión pedagógica
de la disponibilidad real de contenido, degradando SIEMPRE hacia más apoyo
(nunca al revés). Todo se deriva de contenido que ya existe (caché del
diccionario + banco de pronunciación): no se inventa contenido.
"""

from __future__ import annotations

import re

from services.phonetics import tokenize, unit_produced

# Peldaños soportados, ordenados de MAYOR a MENOR apoyo. El orden ES la
# hipótesis pedagógica declarada (`translation < definition < cloze`), y V3.37
# deja los datos (`recall_rungs` por `activity_id`) para corregirla si el
# corpus demuestra lo contrario.
RECALL_CUES: tuple[str, ...] = ("translation", "definition", "cloze")

# Apoyo que declara cada peldaño en el ledger. Vive junto a la escalera, en la
# capa pura, para que dominio, repositorio y tests no puedan divergir.
RECALL_CUE_SUPPORT: dict[str, str] = {
    "translation": "cued",
    "definition": "cued",
    "cloze": "guided",
}

# Tokenizador alineado con `services.phonetics.tokenize` (mismo patrón, sin
# bajar el texto: se normaliza cada token por separado conservando los índices
# reales de la frase original para poder blanquear el hueco).
_TOKEN_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)


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


def blank_out(phrase: str, word: str) -> str | None:
    """Frase con la unidad léxica sustituida por un hueco `_____`, o `None`.

    Función pura y testeable del blanqueo del cue `cloze`. Reutiliza la MISMA
    alineación que acredita la producción del drill (`unit_produced`, V20-01)
    para confirmar que la unidad está de verdad en la frase; después localiza
    sus tokens en el texto ORIGINAL (conservando puntuación y mayúsculas) y los
    sustituye por el hueco.

    Reglas de honestidad:
    - si tras blanquear queda CUALQUIER otra aparición de la palabra, el cue se
      descarta (`None`): sería un spoiler;
    - si la frase no contiene la unidad o falta alguno de los dos, `None`
      (nunca se inventa una frase).
    """
    phrase = (phrase or "").strip()
    word = (word or "").strip()
    if not phrase or not word or not unit_produced(word, phrase):
        return None
    word_tokens = tokenize(word)
    if not word_tokens:
        return None
    spans = [
        (match.group(0).lower(), match.start(), match.end())
        for match in _TOKEN_RE.finditer(phrase)
    ]
    size = len(word_tokens)
    start = end = None
    for i in range(len(spans) - size + 1):
        if [token for token, _s, _e in spans[i : i + size]] == word_tokens:
            start, end = spans[i][1], spans[i + size - 1][2]
            break
    if start is None or end is None:
        return None
    blanked = f"{phrase[:start]}_____{phrase[end:]}"
    if _definition_leaks_word(blanked, word):
        return None
    return blanked


def recall_prompt_for(
    word: str,
    entries: list[dict],
    *,
    cue: str | None = None,
    example: dict | None = None,
) -> dict | None:
    """Cue `{word, cue, cue_kind}` del recall de la palabra, o `None`.

    - Busca la entrada de la diana en la caché global `dictionary_entries`
      (comparación por superficie normalizada).
    - `cue=None` conserva EXACTAMENTE el comportamiento V3.34: `translation` si
      existe; si no, `definition` siempre que no contenga la palabra diana.
    - `cue="translation"|"definition"|"cloze"` sirve ESE peldaño o devuelve
      `None` si no tiene contenido (degradación controlada, sin evento). Un
      `cue` no soportado también devuelve `None`.
    - `cloze` construye la frase en blanco a partir de `example`
      (`{"phrase": …}` de `services.example_sentences.example_for`); si no hay
      frase real en el corpus, `None` (nunca se inventa una frase).
    - `None` si la diana no existe en la caché.

    Nunca devuelve la forma esperada como respuesta.
    """
    target_word = _normalize(word)
    if not target_word:
        return None
    if cue is not None and cue not in RECALL_CUES:
        return None
    target = next(
        (e for e in entries if _normalize(e.get("word") or "") == target_word),
        None,
    )
    if target is None:
        return None

    if cue is None:
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

    if cue == "translation":
        translation = (target.get("translation") or "").strip()
        if not translation:
            return None
        return {
            "word": target_word,
            "cue": translation,
            "cue_kind": "translation",
        }

    if cue == "definition":
        definition = (target.get("definition") or "").strip()
        if not definition or _definition_leaks_word(definition, target_word):
            return None
        return {
            "word": target_word,
            "cue": definition,
            "cue_kind": "definition",
        }

    # cue == "cloze": frase real del corpus con la unidad en blanco.
    blanked = blank_out((example or {}).get("phrase") or "", target_word)
    if blanked is None:
        return None
    return {"word": target_word, "cue": blanked, "cue_kind": "cloze"}


def next_recall_rung(row: dict, evidence: dict | None) -> str:
    """Peldaño RECOMENDADO de la escalera de recall (V3.37, puro).

    La escalera solo asciende con EVIDENCIA, no por tiempo ni por nº de
    intentos: se recorre de mayor a menor apoyo y se devuelve el primer peldaño
    que el ítem AÚN NO ha superado. Sin ningún éxito previo → `translation`; con
    `translation` superado, sin `definition` → `definition`; con `definition`
    superado, sin `cloze` → `cloze`; con los tres superados → `cloze`
    (mantenimiento espaciado: es el techo hasta que exista `situación`).

    El "éxito en el peldaño X" se lee del ledger por `activity_id`
    (`drill:recall:<peldaño>`, agregado en `recall_rungs`), no de contadores
    nuevos. `row` se recibe por simetría con el resto de la cola de repaso; el
    peldaño es una propiedad del ÍTEM y hoy la evidencia ya llega agregada.
    """
    rungs = (evidence or {}).get("recall_rungs") or {}
    for rung in RECALL_CUES:
        try:
            reached = int(rungs.get(rung, 0) or 0) > 0
        except (TypeError, ValueError):
            reached = False
        if not reached:
            return rung
    return RECALL_CUES[-1]


def resolve_recall_cue(ideal: str, available: object) -> str | None:
    """Peldaño realmente servible más cercano al ideal (V3.37, puro).

    `next_recall_rung` decide el peldaño IDEAL, pero no todos tienen contenido
    (el `cloze` exige que la palabra aparezca en el banco de pronunciación).
    Esta función separa la decisión pedagógica de la disponibilidad:

    - recorre la escalera desde `ideal` hacia ABAJO (hacia MÁS apoyo) y devuelve
      el primer peldaño disponible;
    - `None` si no hay ninguno (el peldaño degrada con `available=false`, sin
      evento, como en V3.34);
    - NUNCA degrada hacia ARRIBA: subir la exigencia sin evidencia que lo
      justifique es lo contrario de lo que V3.37 quiere.
    """
    if ideal not in RECALL_CUES:
        return None
    available_set = set(available or ())
    index = RECALL_CUES.index(ideal)
    for rung in reversed(RECALL_CUES[: index + 1]):
        if rung in available_set:
            return rung
    return None
