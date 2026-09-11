"""Adecuación SEMÁNTICA determinista de un uso léxico (V3.44, pura).

La auditoría de V3.43.0 (P1-01) señaló el problema central del proxy semántico:
usaba la `pos` **global** de la entrada como sustituto de sentido. Palabras que
son legítimamente sustantivo y verbo según el contexto (`travel`, `water`,
`plan`, `work`, `change`, `answer`, `phone`, `email`) podían marcar
`semantic_mismatch` en usos correctos (`I plan my trip` con la entrada `plan =
noun`) e impedir un clean success.

V3.44 introduce el modelo `lexical_unit → SENSE → POS`: el ítem declara sus
SENTIDOS (cada uno con su categoría y su glosa, generados como CONTENIDO por el
modelo local en `services.dictionary_content`), y la adecuación se decide
comparando la FUNCIÓN de la ocurrencia en la frase con las FAMILIAS POS de esos
sentidos. Sigue siendo un proxy determinista y advisory (premisa 21): no hay
LLM en el camino de la evidencia.

Taxonomía (`SEMANTIC_ADEQUACIES`):

- `fit` — la ocurrencia encaja con alguno de los sentidos declarados;
- `incorrect` — contradice TODAS las familias con una pista FUERTE (p. ej. un
  sustantivo conjugado como verbo: `I bank yesterday`). Es el ÚNICO valor que
  bloquea un clean success (guarda `error_type="semantic_mismatch"`);
- `suspect` — contradice, pero con una pista DÉBIL (p. ej. un verbo tras
  determinante: `The take was long`). Advisory: NO bloquea, solo advierte
  (`error_type="semantic_doubt"`);
- `unknown` — no hay datos suficientes (sin sentidos/POS, sin la unidad en el
  texto o sin pista reconocible). Nunca bloquea.

Conservador por diseño: solo se emite `incorrect` con una contradicción clara y
ante ausencia TOTAL de una interpretación válida. Un proxy semántico no debe
destruir evidencia léxica objetiva; como mucho, matizarla.
"""

from __future__ import annotations

import re

# Valores de adecuación (vocabulario canónico, orden declarado).
SENSE_FIT = "fit"
SENSE_SUSPECT = "suspect"
SENSE_INCORRECT = "incorrect"
SENSE_UNKNOWN = "unknown"

SEMANTIC_ADEQUACIES: tuple[str, ...] = (
    SENSE_FIT,
    SENSE_SUSPECT,
    SENSE_INCORRECT,
    SENSE_UNKNOWN,
)

# Fuerza de la pista sintáctica que sostiene el rol detectado. `strong` puede
# declarar `incorrect`; `weak` solo `suspect` (nunca bloquea).
_STRONG = "strong"
_WEAK = "weak"

# Pronombres sujeto: delante de una unidad de una palabra sugieren uso VERBAL
# ("I bank", "they plan"). Pista fuerte.
_SUBJECT_PRONOUNS = frozenset({"i", "you", "he", "she", "it", "we", "they"})

# Determinantes/posesivos: delante de la unidad sugieren uso NOMINAL ("the
# bank", "my plan"). Pista DÉBIL: en inglés un verbo puede nominalizarse
# ("the take", "a run"), así que contradice pero no demuestra.
_DETERMINERS = frozenset(
    {
        "the", "a", "an", "my", "your", "his", "her", "its", "our", "their",
        "this", "that", "these", "those", "some", "any", "no", "every",
    }
)

# Auxiliares y `to` delante de la unidad: sugieren infinitivo/conjugación
# ("to travel", "will plan", "can work"). Pista FUERTE de uso verbal.
_AUXILIARIES = frozenset(
    {
        "to", "can", "could", "will", "would", "shall", "should", "must",
        "may", "might", "do", "does", "did", "have", "has", "had", "am",
        "is", "are", "was", "were", "be", "been", "being",
    }
)

# Sufijos de flexión verbal inequívocos (pista fuerte) y ambiguos (pista débil:
# `-s`/`-ies` también son plural nominal).
_VERB_STRONG_SUFFIXES = ("ed", "ing")
_VERB_WEAK_SUFFIXES = ("ies", "s")

_TOKEN_RE = re.compile(r"[a-z]+(?:'[a-z]+)?")


def pos_family(pos: object) -> str:
    """Familia gramatical relevante para el scoring (`noun`/`verb`/"").

    El orden importa: "phrasal verb" contiene "verb". Se comparan PALABRAS (no
    subcadenas), de modo que un valor fuera de la taxonomía canónica —p. ej.
    "adverbio"— no se confunde con "verb". Una categoría que no sea nominal ni
    verbal (adjetivo, adverbio…) no participa en el proxy y devuelve "": no se
    inventa una contradicción con lo que el proxy no sabe juzgar.
    """
    words = re.findall(r"[a-z]+", str(pos or "").strip().lower())
    if "verb" in words:
        return "verb"
    if "noun" in words:
        return "noun"
    return ""


def families_from_senses(senses: object, *, pos: object = "") -> set[str]:
    """Familias POS declaradas por los sentidos de la unidad (V3.44, pura).

    Acepta la lista `[{pos, gloss}]` de la caché. Si no hay ninguna familia
    reconocible, cae a la `pos` global (retrocompatible con el contrato de
    V3.43: una entrada sin sentidos sigue pudiendo juzgarse si declara POS).
    Nunca lanza.
    """
    families: set[str] = set()
    items = senses if isinstance(senses, (list, tuple)) else ()
    for item in items:
        raw_pos = item.get("pos") if isinstance(item, dict) else item
        family = pos_family(raw_pos)
        if family:
            families.add(family)
    if not families:
        family = pos_family(pos)
        if family:
            families.add(family)
    return families


def unit_positions(tokens: list[str], word: str) -> list[int]:
    """Posiciones donde aparece la unidad objetivo (o su flexión) (V3.44, pura).

    Reconoce la secuencia contigua de la unidad y, para unidades de UNA palabra,
    la forma flexionada (`bank` → `banked`/`banking`). Misma lógica que usaba el
    proxy de V3.43, extraída aquí como única fuente de verdad.
    """
    unit_tokens = (word or "").strip().lower().split()
    if not unit_tokens:
        return []
    size = len(unit_tokens)
    positions = [
        index
        for index in range(len(tokens) - size + 1)
        if tokens[index:index + size] == unit_tokens
    ]
    if size == 1:
        base = unit_tokens[0]
        for index, token in enumerate(tokens):
            if token == base:
                continue
            suffix = token[len(base):] if token.startswith(base) else ""
            if suffix in _VERB_STRONG_SUFFIXES or suffix in _VERB_WEAK_SUFFIXES:
                positions.append(index)
    return positions


def _tokens(text: object) -> list[str]:
    """Tokens alfabéticos normalizados del texto (mismo tokenizador que el resto)."""
    return _TOKEN_RE.findall(str(text or "").lower())


def occurrence_role(
    tokens: list[str], index: int, word: str
) -> tuple[str, str]:
    """Rol sintáctico probable de una ocurrencia y fuerza de la pista (V3.44).

    Devuelve `(rol, fuerza)` con `rol ∈ {"noun", "verb", ""}` y
    `fuerza ∈ {"strong", "weak", ""}`. Solo se pronuncia para unidades de UNA
    palabra: en unidades multi-palabra (`look after`, `take care of`) el proxy
    se abstiene (`("", "")`) porque no sabe identificar la función con fiabilidad
    y no debe arriesgar un falso `incorrect`.
    """
    unit_tokens = (word or "").strip().lower().split()
    if len(unit_tokens) != 1:
        return "", ""
    if index < 0 or index >= len(tokens):
        return "", ""
    token = tokens[index]
    base = unit_tokens[0]
    previous = tokens[index - 1] if index > 0 else ""
    if token == base:
        # Forma base: decide el contexto que la precede.
        if previous in _SUBJECT_PRONOUNS:
            return "verb", _STRONG
        if previous in _AUXILIARIES:
            return "verb", _STRONG
        if previous in _DETERMINERS:
            return "noun", _WEAK
        return "", ""
    # Forma flexionada (solo posible con unidad de una palabra).
    if not token.startswith(base):
        return "", ""
    suffix = token[len(base):]
    if suffix in _VERB_STRONG_SUFFIXES:
        return "verb", _STRONG
    if suffix in _VERB_WEAK_SUFFIXES:
        # `-s`/`-ies` son también plural nominal: pista débil.
        return "verb", _WEAK
    return "", ""


def _strongest(current: str, candidate: str) -> str:
    """Fuerza máxima entre dos pistas (`strong` > `weak` > "")."""
    order = {"": 0, _WEAK: 1, _STRONG: 2}
    return candidate if order.get(candidate, 0) > order.get(current, 0) else current


def semantic_adequacy(
    word: str,
    text: str,
    *,
    senses: object = (),
    pos: object = "",
) -> str:
    """Adecuación semántica del uso de la unidad en `text` (V3.44, pura).

    Compara la FUNCIÓN de cada ocurrencia con las FAMILIAS POS declaradas por
    los sentidos (con fallback a la `pos` global). Reglas, en orden:

    1. sin familias o sin ocurrencias reconocibles → `unknown`;
    2. ALGUNA ocurrencia encaja con las familias → `fit` (si hay un uso válido,
       no se declara contradicción: conservador);
    3. ninguna encaja y hay una contradicción FUERTE → `incorrect`;
    4. ninguna encaja y solo hay contradicción DÉBIL → `suspect`;
    5. en cualquier otro caso → `unknown`.

    Nunca lanza.
    """
    families = families_from_senses(senses, pos=pos)
    if not families:
        return SENSE_UNKNOWN
    tokens = _tokens(text)
    positions = unit_positions(tokens, word)
    if not positions:
        return SENSE_UNKNOWN
    roles = [occurrence_role(tokens, index, word) for index in positions]
    for role, _strength in roles:
        if role and role in families:
            return SENSE_FIT
    strength = ""
    for role, cue_strength in roles:
        if role and role not in families:
            strength = _strongest(strength, cue_strength)
    if strength == _STRONG:
        return SENSE_INCORRECT
    if strength == _WEAK:
        return SENSE_SUSPECT
    return SENSE_UNKNOWN
