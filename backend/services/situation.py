"""Validador del enunciado situacional del peldaño `situation` (V3.38.1, puro).

El 4.º peldaño de la escalera de recall (`translation < definition < cloze <
situation`) sirve un enunciado de escenario con UN único hueco donde encaja la
palabra diana. Ese enunciado lo genera el modelo local y se cachea de forma
GLOBAL y CANÓNICA en `dictionary_entries.situation`, así que su validación debe
ser determinista y compartida por TODOS los que lo leen:

- la GENERACIÓN (`services.dictionary_content`), que decide si se persiste;
- la LECTURA (`services.recall`), que decide si se sirve un valor ya cacheado
  (una situación inválida de una versión previa no debe colarse);
- la DISPONIBILIDAD (`domain.review._available_recall_cues`), que decide si el
  peldaño aparece como recomendable.

Reglas (puras, sin LLM ni I/O):

- exactamente UN hueco, normalizado a `_____`;
- UNA sola frase: como mucho un signo de cierre (`.!?`) y, si existe, al final;
- longitud acotada (`MAX_SITUATION_CHARS`);
- sin FUGA de la diana: ni la forma textual ni las variantes morfológicas
  regulares (plural, 3.ª persona, pasado, gerundio, adverbio, posesivo).

Honestidad sobre la limitación: las formas IRREGULARES (`go`→`went`, `run`→
`ran`) no se detectan por reglas; el prompt pide no escribir "any form" de la
diana y esta validación cubre las productivas regulares. V3.39 puede ampliar el
detector si el corpus lo exige.
"""

from __future__ import annotations

import re

# Longitud máxima del enunciado situacional. El prompt pide <= 200 caracteres;
# el validador admite un margen y descarta lo que supere este tope.
MAX_SITUATION_CHARS = 240

# Hueco canónico. El modelo puede escribir una raya de guiones bajos de
# cualquier longitud; se normaliza a esta forma exacta.
SITUATION_BLANK = "_____"
_BLANK_RE = re.compile(r"_{3,}")

# Signos de cierre de frase.
_SENTENCE_END_RE = re.compile(r"[.!?]")

# Longitud mínima de la diana para generar variantes morfológicas regulares. Por
# debajo (p. ej. "I", "go") las variantes colisionan con palabras funcionales
# muy comunes ("is", "as") y generan falsos positivos que descartarían
# enunciados válidos; en esos casos solo se comprueba la forma textual.
_MORPHOLOGY_MIN_LENGTH = 3


def normalize_blank(text: str) -> str:
    """Normaliza cualquier racha de guiones bajos al hueco canónico."""
    return _BLANK_RE.sub(SITUATION_BLANK, text or "")


def _is_single_sentence(text: str) -> bool:
    """¿Es UNA sola frase: como mucho un cierre y, si lo hay, al final?"""
    body = text.replace(SITUATION_BLANK, " ").strip()
    if not body:
        return False
    endings = list(_SENTENCE_END_RE.finditer(body))
    if not endings:
        # Sin puntuación terminal: se acepta (una frase sin cierre explícito).
        return True
    if len(endings) > 1:
        return False
    return endings[0].end() == len(body)


def _regular_forms(word: str) -> set[str]:
    """Variantes morfológicas REGULARES de una palabra de una sola pieza.

    No es un lematizador: solo cubre los sufijos productivos frecuentes para
    detectar la fuga obvia. Multiplica variantes a propósito (una fuga detectada
    de más solo descarta un enunciado; una no detectada revelaría la respuesta).
    """
    w = word.strip().lower()
    forms = {w}
    if len(w) < _MORPHOLOGY_MIN_LENGTH or not w.isalpha():
        return forms
    ends_consonant_y = w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou"
    # Plural / 3.ª persona del singular.
    forms.add(w + "s")
    if w.endswith(("s", "x", "z", "ch", "sh")):
        forms.add(w + "es")
    if ends_consonant_y:
        forms.add(w[:-1] + "ies")
    # Pasado / participio.
    if w.endswith("e"):
        forms.add(w + "d")
    else:
        forms.add(w + "ed")
        if len(w) >= 2 and w[-1] not in "aeiou" and w[-2] in "aeiou":
            forms.add(w + w[-1] + "ed")  # stop -> stopped
    if ends_consonant_y:
        forms.add(w[:-1] + "ied")
    # Gerundio.
    if w.endswith("e") and not w.endswith("ee"):
        forms.add(w[:-1] + "ing")  # make -> making
    else:
        forms.add(w + "ing")
        if (
            len(w) >= 3
            and w[-1] not in "aeiou"
            and w[-2] in "aeiou"
            and w[-3] not in "aeiou"
        ):
            forms.add(w + w[-1] + "ing")  # run -> running
    # Adverbio y posesivo.
    forms.add(w + "ly")
    forms.add(w + "'s")
    return forms


def _target_pattern(word: str) -> re.Pattern[str] | None:
    """Regex que detecta la diana o sus variantes morfológicas (None sin diana)."""
    target = (word or "").strip().lower()
    if not target:
        return None
    if " " in target:
        # Unidad multi-palabra: solo la forma textual (las variantes se generan
        # para palabras de una pieza).
        variants = {re.escape(target)}
    else:
        variants = {re.escape(form) for form in _regular_forms(target) if form}
    ordered = sorted(variants, key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(ordered) + r")\b", re.IGNORECASE)


def leaks_target(text: str, word: str) -> bool:
    """¿El enunciado contiene la diana o una forma morfológica regular suya?"""
    pattern = _target_pattern(word)
    return bool(pattern and pattern.search(text or ""))


def validate_situation(raw_situation: object, word: str = "") -> str:
    """Enunciado situacional validado, o "" si no cumple el contrato (V3.38.1).

    Es la única fuente de verdad: la usan la generación (para persistir o
    descartar) y la lectura (para servir o degradar). Nunca lanza.
    """
    text = str(raw_situation or "").strip()
    if not text:
        return ""
    text = normalize_blank(text)
    if text.count(SITUATION_BLANK) != 1:
        return ""
    if len(text) > MAX_SITUATION_CHARS:
        return ""
    if not _is_single_sentence(text):
        return ""
    if leaks_target(text, word):
        return ""
    return text
