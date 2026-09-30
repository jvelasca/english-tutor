"""Puente Listening → FSRS como EVIDENCIA DE DIFICULTAD (V3.92).

Cierra el circuito entre subsistemas **sin mezclar objetos pedagógicos**, que es
la frontera que V3.89 dejó escrita y esta release respeta:

- la **frase** fallada sigue siendo un EJERCICIO y vive en su propia cola
  (`listening_review_queue`, V3.89). No entra en FSRS;
- la **palabra** que el alumno ya tiene en su léxico y que aparecía en esa frase
  recibe EVIDENCIA DE DIFICULTAD en su carta FSRS: sube su `difficulty` y vuelve
  a estar debida hoy. No se finge una recuperación que no ha ocurrido (`reps`,
  `stability` y `state` no se tocan: eso lo mueve `fsrs.schedule()` cuando el
  alumno de verdad recupera la palabra).

**Invariante que no se cruza:** este puente NUNCA crea vocabulario. Solo mira
palabras que el alumno ya tiene en `vocabulary`; si alguna no tiene carta, se le
crea la carta de repaso (que es suya desde el alta), pero jamás una palabra.

Este módulo es **puro**: no toca la BD, no lee el reloj y no importa FastAPI. El
emparejamiento usa el mismo lematizador declarado que el Sense Engine
(`services.semantics`), de modo que `banks`/`banking` encuentran `bank` sin
diccionario, sin LLM y sin dependencias nuevas (PREMISAS §2 y §21).
"""
from __future__ import annotations

from services.semantics import GLOSS_STOPWORDS, lemma_of, lemma_variants

# Etiqueta del origen de la evidencia. Viaja en `fsrs_cards.why` y en la tabla
# `listening_difficulty_evidence`, y es la clave de traducción de la UI
# (`fsrs.whyReason.listening-evidence`).
SOURCE = "listening-evidence"

# Unidades mínimas/máximas por frase. El tope existe para que una frase larga no
# convierta un fallo en una avalancha de cartas tocadas: la evidencia más fuerte
# es la de las primeras palabras, y el resto ya se beneficia del repaso de frase.
MIN_UNIT_CHARS = 2
MAX_MATCHES = 8

# Una carta está «débil» si está sin empezar, en aprendizaje/reaprendizaje o si
# su dificultad ya es alta. Una carta dominada (review, dificultad baja) NO
# recibe evidencia de dificultad por no entender una frase: sería castigar un
# dominio ya demostrado con una señal de otra destreza.
WEAK_STATES = ("new", "learning", "relearning")
WEAK_DIFFICULTY = 6.0


def phrase_units(text: object) -> list[str]:
    """Unidades léxicas candidatas de una frase, en orden de aparición.

    Tokeniza a minúsculas, descarta lo que no es alfabético (puntuación, cifras)
    y las palabras vacías (`GLOSS_STOPWORDS`: `the`, `of`, `is`…). Deduplica
    conservando el orden. Puro y total: cualquier entrada rara devuelve `[]`.
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in str(text or "").lower().replace("'", " ").split():
        token = "".join(ch for ch in raw if ch.isalpha())
        if len(token) < MIN_UNIT_CHARS or token in GLOSS_STOPWORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def unit_index(known: object) -> dict[str, str]:
    """Índice `forma → palabra canónica` del léxico del alumno.

    `known` es cualquier iterable de filas con `word` (y opcionalmente `lemma`).
    Cada palabra se indexa por su superficie, su lema y las variantes que el
    lematizador declarado reconoce, así que `banks` encuentra `bank`. La primera
    palabra que reclama una forma gana (orden de entrada): estable y sin
    sorpresas.
    """
    index: dict[str, str] = {}
    for row in known or ():
        if isinstance(row, str):
            word, lemma = row, ""
        else:
            word = str((row or {}).get("word") or "")
            lemma = str((row or {}).get("lemma") or "")
        canonical = word.strip().lower()
        if not canonical:
            continue
        forms = {canonical}
        if lemma:
            forms.add(lemma.strip().lower())
        for form in (canonical, lemma):
            for variant in lemma_variants(form):
                forms.add(variant)
        for form in forms:
            if form and form not in index:
                index[form] = canonical
    return index


def match_units(text: object, known: object) -> list[dict]:
    """Palabras del léxico del alumno presentes en la frase, en orden.

    Devuelve `[{"word": <canónica>, "surface": <token oído>}]`, deduplicado por
    palabra canónica. Vacío si la frase no toca nada del léxico: un fallo de
    comprensión sobre vocabulario que el alumno no tiene no es evidencia de
    dificultad de NINGUNA de sus palabras.
    """
    index = unit_index(known)
    if not index:
        return []
    found: list[dict] = []
    claimed: set[str] = set()
    for token in phrase_units(text):
        canonical = index.get(token)
        if canonical is None:
            lemma = lemma_of(token)
            canonical = index.get(lemma) if lemma else None
        if canonical is None:
            continue
        if canonical in claimed:
            continue
        claimed.add(canonical)
        found.append({"word": canonical, "surface": token})
        if len(found) >= MAX_MATCHES:
            break
    return found


def sense_index(known: object) -> dict[str, object]:
    """`{palabra canónica: acepción declarada}` del léxico del alumno (V3.93, pura).

    La acepción es la que el alumno eligió al dar de alta la palabra
    (`sense_json`). Puede NO constar: en ese caso la palabra no aparece en el
    índice y el Sense Resolver responde `ambiguous` (`declared:none`) en vez de
    inventarle un sentido. Es la entrada honesta, y la razón de que el dark
    launch mida cuánta evidencia se apoya en una acepción que nadie declaró.
    """
    index: dict[str, object] = {}
    for row in known or ():
        if not isinstance(row, dict):
            continue
        word = str(row.get("word") or "").strip().lower()
        sense = row.get("sense")
        if word and isinstance(sense, dict) and sense and word not in index:
            index[word] = sense
    return index


def is_weak_card(card: object) -> bool:
    """¿La carta admite evidencia de dificultad? (ausente = sí, no hay dominio).

    Una carta sin datos (`None`) cuenta como débil: la palabra está en el léxico
    del alumno y no hay dominio demostrado que proteger. Una carta en `review`
    con dificultad baja NO: su dominio es evidencia más fuerte que no entender
    una frase concreta.
    """
    if not isinstance(card, dict):
        return True
    state = str(card.get("state") or "new")
    difficulty = float(card.get("difficulty") or 5.0)
    return state in WEAK_STATES or difficulty >= WEAK_DIFFICULTY


def select_targets(matches: list[dict], cards: dict | None) -> list[dict]:
    """De las palabras emparejadas, las que admiten evidencia de dificultad.

    `cards` es `{palabra: carta}` (lo que devuelve `fsrs_cards_by_ids`). Una
    palabra sin entrada se considera débil, pero el llamador decide si le crea
    carta: aquí no se inventa nada.
    """
    known_cards = cards or {}
    return [
        {
            "word": match["word"],
            "surface": match["surface"],
            "card": known_cards.get(match["word"]),
        }
        for match in matches
        if is_weak_card(known_cards.get(match["word"]))
    ]
