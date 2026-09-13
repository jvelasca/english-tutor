"""Adecuación SEMÁNTICA determinista de un uso léxico (V3.44 → V3.58, pura).

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

V3.58 (Sense Engine 2.0) cierra la mitad que V3.44 dejó abierta: los sentidos se
declaraban `[{pos, gloss}]` pero la decisión comparaba FAMILIAS POS y la glosa no
la leía nadie. Con `bank` declarando dos sentidos de la MISMA familia
(«financial place» / «river side») el motor no podía separarlos: era un límite
del CONTRATO, no de los datos. Ahora `surface → lemma → sense` resuelve QUÉ
sentido expresa la ocurrencia (`lemma_of`, `lemma_variants`, `select_sense`,
`sense_fit`). La frontera es deliberada y está probada: la glosa decide el
SENTIDO, nunca el VEREDICTO (`_adequacy` es la regla literal de V3.44), porque la
AUSENCIA de solapamiento no demuestra incompatibilidad y ampliar `incorrect`
destruiría evidencia léxica correcta.
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


# ---------------------------------------------------------------------------
# V3.58 (Sense Engine 2.0): `surface → lemma → sense → semantic_fit`.
#
# V3.44 dejó el modelo a medias: los sentidos se declaran `[{pos, gloss}]`, pero
# la decisión compara FAMILIAS POS y la glosa no la lee nadie. Con dos sentidos de
# la MISMA familia (`bank` = «financial place» y «river side») el motor no puede
# separarlos: es un límite de CONTRATO, no de datos.
#
# V3.58 añade las dos patas que faltan. `lemma_of`/`lemma_variants` hacen que el
# parecido léxico no se rompa con la flexión; `select_sense` elige el sentido por
# (función sintáctica, solapamiento con la glosa, orden declarado).
#
# FRONTERA (invariante conservador, probado en `test_semantics_sense_engine_v358`):
# la glosa decide el SENTIDO, no el VEREDICTO. `semantic_adequacy` mantiene la
# adecuación de V3.44 EXACTA —solo `incorrect` bloquea y no se amplía— porque una
# glosa corta no demuestra incompatibilidad: la AUSENCIA de solapamiento no es una
# prueba (`"The bank is closed"` no comparte una palabra con «a financial place» y
# es un uso correcto). La resolución del sentido es, por tanto, ADITIVA y
# explicable; su consumo entra por el contrato del intento de transferencia.
# ---------------------------------------------------------------------------

# Ventana de contexto (en tokens, a cada lado) que se compara con la glosa.
CONTEXT_WINDOW = 4

# Pesos DECLARADOS de la resolución de sentido. La función sintáctica MANDA
# (`role_family_match`); el solapamiento con la glosa DESEMPATA dentro de la misma
# familia (es el caso que V3.44 no podía ver) y queda expuesto como `score`.
SENSE_ROLE_MAJOR = "role"
SENSE_GLOSS_MAJOR = "gloss"

# Palabras vacías que no aportan sentido a una glosa-etiqueta corta. Se declaran
# para que el solapamiento mida CONTENIDO: «a place for money and loans» aporta
# `place`/`money`/`loans`, no `a`/`for`/`and`.
GLOSS_STOPWORDS = frozenset(
    {
        "a", "about", "all", "also", "am", "an", "and", "any", "are", "as", "at",
        "be", "been", "being", "but", "by", "can", "could", "did", "do", "does",
        "each", "every", "for", "from", "had", "has", "have", "he", "her", "here",
        "hers", "him", "his", "how", "i", "if", "in", "into", "is", "it", "its",
        "may", "me", "might", "more", "most", "much", "must", "my", "no", "not",
        "of", "on", "one", "or", "other", "our", "out", "over", "shall", "she",
        "should", "so", "some", "someone", "something", "such", "than", "that",
        "the", "their", "them", "then", "there", "these", "they", "this", "those",
        "to", "under", "up", "us", "very", "was", "we", "were", "what", "when",
        "where", "which", "who", "whom", "whose", "will", "with", "would", "you",
        "your",
    }
)

# Sibilantes que sí forman plural en `-es` (`box`→`boxes`, `watch`→`watches`).
# La `s` se excluye a propósito: `closes` es `close` (3ª persona), no `clos`.
_PLURAL_ES_TAILS = ("ches", "shes", "xes", "zes")

_VOWELS = frozenset("aeiou")
_ALPHA_RE = re.compile(r"[a-z]+")
_LEMMA_MIN_CHARS = 4  # por debajo no se toca: `go`, `was`, `is`…


def lemma_of(token: object) -> str:
    """Forma base declarada de un token inglés (V3.58, pura).

    Morfología REGULAR declarada —sin diccionario, sin lematizador y sin LLM
    (premisa 21)— con las reparaciones ortográficas habituales: plural/3ª persona
    (`-s`, `-ies`), sibilantes (`-ches`/`-shes`/`-xes`/`-zes`), pasado
    (`-ed`) y gerundio (`-ing`, incluida la consonante doble `running`→`run`).

    Es deliberadamente PARCIAL: los verbos con `e` muda necesitan la variante que
    aporta `lemma_variants` (por eso existe), y las formas irregulares
    (`went`/`gone`) no se tocan. Solo alimenta el solapamiento con la glosa, que
    es una señal SUAVE: no decide el veredicto, así que una forma no reconocida
    no puede contaminar la evidencia. Nunca lanza.
    """
    text = _ALPHA_RE.fullmatch(str(token or "").strip().lower())
    if text is None:
        return ""
    base = text.group(0)
    if len(base) < _LEMMA_MIN_CHARS:
        return base
    if base.endswith("ies"):
        return base[:-3] + "y"
    if base.endswith("ing"):
        return _undouble(base[:-3])
    if base.endswith("ed"):
        return _undouble(base[:-2])
    if base.endswith(_PLURAL_ES_TAILS):
        return base[:-2]
    if base.endswith("s"):
        return base[:-1]
    return base


def _undouble(stem: str) -> str:
    """Deshace la consonante doble antes de `-ing`/`-ed` (`runn`→`run`)."""
    if len(stem) >= 3 and stem[-1] == stem[-2] and stem[-1] not in _VOWELS:
        return stem[:-1]
    return stem


def lemma_variants(token: object) -> frozenset[str]:
    """Formas comparables de un token frente a una glosa (V3.58, pura).

    Devuelve la superficie, su lema y —cuando la flexión pudo comerse una `e`
    muda (`making`→`mak`) — la variante con `e` restaurada (`make`). Es lo que
    permite que «to make» solape con `making` sin lematizador. Nunca lanza.
    """
    text = _ALPHA_RE.fullmatch(str(token or "").strip().lower())
    if text is None:
        return frozenset()
    base = text.group(0)
    stem = lemma_of(base)
    variants = {base}
    if stem:
        variants.add(stem)
        if stem != base and base.endswith(("ing", "ed")):
            variants.add(stem + "e")
    return frozenset(variants)


def gloss_tokens(gloss: object) -> list[str]:
    """Tokens de CONTENIDO de una glosa, en orden y sin repetir (V3.58, pura).

    Descarta las palabras vacías (`GLOSS_STOPWORDS`): una glosa-etiqueta corta
    («a place for money and loans») aporta sus sustantivos, no su gramática.
    Nunca lanza.
    """
    found: list[str] = []
    for token in _tokens(gloss):
        if token in GLOSS_STOPWORDS or token in found:
            continue
        found.append(token)
    return found


def context_window(
    tokens: list[str], index: int, *, size: int = CONTEXT_WINDOW
) -> list[str]:
    """Ventana de contexto alrededor de una ocurrencia (V3.58, pura).

    Recorta en los bordes (no inventa) y con `tokens` vacío devuelve `[]`.
    Nunca lanza.
    """
    if not tokens:
        return []
    span = max(0, int(size))
    start = max(0, index - span)
    end = min(len(tokens), index + span + 1)
    if start >= end:
        return []
    return list(tokens[start:end])


def sense_overlap(window_tokens: object, gloss: object) -> int:
    """Nº de tokens de CONTENIDO de la glosa presentes en la ventana (V3.58).

    El parecido se mide entre VARIANTES de lema de las dos partes, así que la
    flexión no lo rompe (`decides` vs «to decide» → 1). Es la CONFIANZA del
    desempate: 0 no significa contradicción (ver la frontera del módulo). Nunca
    lanza.
    """
    if not isinstance(window_tokens, (list, tuple)):
        return 0
    window_variants: set[str] = set()
    for token in window_tokens:
        window_variants |= lemma_variants(token)
    if not window_variants:
        return 0
    matched = 0
    for token in gloss_tokens(gloss):
        if lemma_variants(token) & window_variants:
            matched += 1
    return matched


def _valid_senses(senses: object) -> list[dict]:
    """Sentidos utilizables como `[{index, pos, gloss}]` (V3.58, pura).

    Acepta la lista cruda de la caché y descarta lo que no sirva, conservando el
    ÍNDICE ORIGINAL para que el desempate estable sea el orden declarado. Nunca
    lanza.
    """
    items = senses if isinstance(senses, (list, tuple)) else ()
    valid: list[dict] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        gloss = " ".join(str(item.get("gloss") or "").split())
        valid.append(
            {
                "index": index,
                "pos": str(item.get("pos") or "").strip().lower(),
                "gloss": gloss,
            }
        )
    return valid


def select_sense(word: object, tokens: object, index: object, senses: object) -> dict:
    """Sentido que expresa la ocurrencia `index` de la unidad (V3.58, pura).

    Clave de orden DECLARADA y determinista:

    1. `role_family_match` — la función sintáctica de la ocurrencia pertenece a la
       familia del sentido (señal MAYOR: la gramática manda);
    2. `score` — tokens de contenido de la glosa presentes en la ventana de
       contexto (señal que DESEMPATA dentro de la misma familia: el hueco que
       V3.44 no podía cubrir);
    3. orden declarado — empate real: gana el primer sentido (`estable`).

    Devuelve `{index, pos, gloss, score, role, strength, reasons}`; sin sentidos
    `index` es `None` y la glosa `""`. Nunca lanza.
    """
    valid = _valid_senses(senses)
    role, strength = ("", "")
    if isinstance(tokens, (list, tuple)) and isinstance(index, int):
        role, strength = occurrence_role(tokens, index, word)
    window = context_window(tokens, index) if isinstance(tokens, (list, tuple)) else []
    if not valid:
        return {
            "index": None,
            "pos": "",
            "gloss": "",
            "score": 0,
            "role": role,
            "strength": strength,
            "reasons": _sense_reasons(role, strength, "", 0),
        }
    best: dict | None = None
    best_key: tuple[int, int, int] | None = None
    for sense in valid:
        family = pos_family(sense["pos"])
        matches = int(bool(role) and family == role)
        score = sense_overlap(window, sense["gloss"])
        key = (matches, score, -sense["index"])
        if best_key is None or key > best_key:
            best_key = key
            best = {**sense, "score": score, "matches": matches}
    assert best is not None  # `valid` no está vacío
    return {
        "index": best["index"],
        "pos": best["pos"],
        "gloss": best["gloss"],
        "score": best["score"],
        "role": role,
        "strength": strength,
        "reasons": _sense_reasons(role, strength, best["pos"], best["score"]),
    }


def _sense_reasons(role: str, strength: str, pos: str, score: int) -> tuple[str, ...]:
    """Razones legibles y deterministas de la resolución del sentido (V3.58)."""
    reasons = [f"role:{role}/{strength}" if role else "role:none"]
    if pos:
        reasons.append(f"sense:{pos}")
    if score:
        reasons.append(f"gloss:{score}")
    return tuple(reasons)


def _adequacy(
    word: object, text: object, *, senses: object = (), pos: object = ""
) -> str:
    """Adecuación de V3.44, literal (extraída sin cambios de comportamiento).

    Es la ÚNICA autoridad del veredicto: V3.58 no la toca. Vive aquí para que
    `semantic_adequacy` y `sense_fit` no puedan divergir.
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


def sense_fit(
    word: object,
    text: object,
    *,
    senses: object = (),
    pos: object = "",
) -> dict:
    """Adecuación + SENTIDO resuelto del uso de la unidad (V3.58, puro).

    Devuelve `{adequacy, sense_index, sense_pos, sense_gloss, sense_score,
    reasons}`:

    - `adequacy` — EXACTAMENTE el veredicto de V3.44 (`_adequacy`), para que la
      resolución del sentido sea ADITIVA y no pueda cambiar la evidencia;
    - `sense_*` — el sentido que la ocurrencia expresa, elegido entre TODAS las
      ocurrencias por (familia que encaja, solapamiento con la glosa, orden
      declarado). Sin sentidos, `sense_index` es `None` y la glosa `""`.

    Nunca lanza.
    """
    adequacy = _adequacy(word, text, senses=senses, pos=pos)
    tokens = _tokens(text)
    positions = unit_positions(tokens, word)
    best: dict | None = None
    best_key: tuple[int, int, int] | None = None
    for index in positions:
        picked = select_sense(word, tokens, index, senses)
        if picked["index"] is None:
            continue
        key = (
            int(picked["pos"] != "" and pos_family(picked["pos"]) == picked["role"]),
            picked["score"],
            -index,
        )
        if best_key is None or key > best_key:
            best_key = key
            best = picked
    if best is None:
        return {
            "adequacy": adequacy,
            "sense_index": None,
            "sense_pos": "",
            "sense_gloss": "",
            "sense_score": 0,
            "reasons": (),
        }
    return {
        "adequacy": adequacy,
        "sense_index": best["index"],
        "sense_pos": best["pos"],
        "sense_gloss": best["gloss"],
        "sense_score": best["score"],
        "reasons": best["reasons"],
    }


def semantic_adequacy(
    word: str,
    text: str,
    *,
    senses: object = (),
    pos: object = "",
) -> str:
    """Adecuación semántica del uso de la unidad en `text` (V3.44 → V3.58, pura).

    Compara la FUNCIÓN de cada ocurrencia con las FAMILIAS POS declaradas por
    los sentidos (con fallback a la `pos` global). Reglas, en orden:

    1. sin familias o sin ocurrencias reconocibles → `unknown`;
    2. ALGUNA ocurrencia encaja con las familias → `fit` (si hay un uso válido,
       no se declara contradicción: conservador);
    3. ninguna encaja y hay una contradicción FUERTE → `incorrect`;
    4. ninguna encaja y solo hay contradicción DÉBIL → `suspect`;
    5. en cualquier otro caso → `unknown`.

    V3.58 delega en `_adequacy` (la regla literal de V3.44) y deja la resolución
    del sentido a `sense_fit`: la firma, la taxonomía y la decisión NO cambian.
    Nunca lanza.
    """
    return _adequacy(word, text, senses=senses, pos=pos)

