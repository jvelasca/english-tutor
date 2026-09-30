"""Sense Resolver del puente Listening → evidencia (SENSE-CONTEXT-01, DISEÑO).

**Estado: PURO, ENFORCE desde V3.94.** `domain/listening.py` lo consulta al registrar
evidencia y **decide** con `allows_difficulty_evidence`: un `mismatch` PROBADO no sube
la dificultad de la acepción aprendida (se registra como `new_sense_exposure`); todo lo
demás conserva la evidencia de V3.92. La frontera del dark launch (V3.93) queda cerrada
en `tests/test_sense_enforce_v394.py`.

El problema que resuelve, medido en V3.92: `listening_bridge` empareja por
`word`/`lemma`, así que una frase de «orilla» genera evidencia de dificultad sobre
una acepción «financiera» de `bank`. La capacidad de resolver el sentido existe
(`semantics.select_sense`/`sense_fit`), pero no se consulta.

Por qué NO se mete el Sense Engine dentro de `listening_bridge`: el puente debe
seguir siendo una frontera mínima. El resolver vive en su propio módulo puro y se
compone ENCIMA; el puente recibe un veredicto, no un motor. Sin BD, sin reloj, sin
FastAPI, sin LLM y sin diccionario en runtime (PREMISAS §2 y §21).

Taxonomía (`MATCHES`), conservadora por diseño:

- `matched` — hay evidencia LÉXICA de que el contexto expresa la acepción
  aprendida → la evidencia de dificultad es válida.
- `mismatch` — hay evidencia FUERTE de un sentido DISTINTO (o ≥2 tokens de la
  alternativa, o un desempate gramatical fuerte) → NO se penaliza la acepción
  aprendida; el fallo se registra como `new_sense_exposure` (V3.94).
- `ambiguous` — no se puede decidir, **incluida la señal DÉBIL a favor de otra
  acepción** (un solo token: `gloss:other:weak`) → **CONSERVA la evidencia**
  (decisión de V3.94): la duda no RESTA evidencia igual que no la FABRICA, y en
  `declared:none` / `alternatives:none` no hay NADA que contradecir.

Regla dura: `matched` EXIGE solapamiento léxico positivo o un desempate
gramatical con alternativas declaradas. `mismatch` NO se declara con una señal
débil (V3.94.1): la resolución de sentido es ASIMÉTRICA —un `matched` tolera
incertidumbre, pero un `mismatch` SUPRIME evidencia y exige PRUEBA—. Nunca se
fabrica un «coincide» por defecto, así que dos sentidos del MISMO POS sin pistas
léxicas son `ambiguous` (el caso real: «The bank was closed»).
"""

from __future__ import annotations

from services.semantics import (
    context_window,
    normalize_sense_text,
    occurrence_role,
    pos_family,
    sense_key,
    sense_overlap,
    tokens_of,
    unit_positions,
)

# Resultados posibles del resolver, en orden declarado.
SENSE_MATCHED = "matched"
SENSE_MISMATCH = "mismatch"
SENSE_AMBIGUOUS = "ambiguous"

MATCHES: tuple[str, ...] = (SENSE_MATCHED, SENSE_MISMATCH, SENSE_AMBIGUOUS)

# Fuerza mínima para que una contradicción gramatical sola pueda declarar
# `mismatch` (misma escala que `semantics`: "strong" > "weak" > "").
_STRONG = "strong"

# Umbral de PRUEBA para declarar un `mismatch` por solapamiento léxico (V3.94.1).
# Un único token en la ventana puede ser casual (`water` en «The bank was close to
# the water»); con dos la señal es fuerte. Por debajo NO se declara mismatch: la
# regla es ASIMÉTRICA porque un mismatch SUPRIME evidencia (no penaliza la carta
# aprendida), así que exige más prueba que un `matched`, que solo tolera duda.
PROVEN_OTHER_OVERLAP = 2

# Fuerza declarada del veredicto de sentido. Solo `proven` suprime evidencia; un
# `possible` es una señal débil a favor de otra acepción, que NO se convierte en
# `new_sense_exposure` (se conserva la evidencia, como en `ambiguous`).
MISMATCH_PROVEN = "proven"
MISMATCH_POSSIBLE = "possible"

# Un veredicto sin señal (`reason`) se declara siempre para poder depurarlo.
REASON_DECLARED_NONE = "declared:none"
REASON_OCCURRENCE_NONE = "occurrence:none"
REASON_GLOSS_DECLARED = "gloss:declared"
REASON_GLOSS_OTHER = "gloss:other"
REASON_GLOSS_OTHER_WEAK = "gloss:other:weak"
REASON_ROLE_DECLARED = "role:declared"
REASON_ROLE_OTHER = "role:other"
REASON_TIE = "tie"
REASON_NO_ALTERNATIVES = "alternatives:none"


def _sense_gloss(sense: object) -> str:
    if not isinstance(sense, dict):
        return ""
    return str(sense.get("gloss") or "")


def _sense_family(sense: object) -> str:
    if not isinstance(sense, dict):
        return ""
    return pos_family(sense.get("pos"))


def is_new_sense_exposure(verdict: object) -> bool:
    """¿El veredicto es un `mismatch` PROBADO? (pura y total).

    Un `mismatch` es la única señal POSITIVA de que el contexto expresa una acepción
    DISTINTA a la aprendida, así que es la base de `new_sense_exposure`: el alumno no
    falló la palabra, se topó con otro de sus sentidos. La política de V3.94 es
    exactamente su negación (ver `allows_difficulty_evidence`).

    V3.94.1: el resolver SOLO emite `mismatch` cuando la prueba es fuerte (≥2 tokens
    de la alternativa, o desempate gramatical fuerte). Una señal léxica débil cae a
    `ambiguous` (`gloss:other:weak`), así que `mismatch` y «probado» coinciden.
    """
    return isinstance(verdict, dict) and verdict.get("match") == SENSE_MISMATCH


def allows_difficulty_evidence(verdict: object) -> bool:
    """¿La evidencia de dificultad se aplica a la carta? (ENFORCE V3.94; pura y total).

    La política de V3.94 suprime la evidencia **SOLO ante un `mismatch` PROBADO**: es
    la única señal positiva de que el contexto usa una acepción DISTINTA a la
    aprendida, y subir la dificultad de la acepción aprendida por un uso que no es el
    suyo sería señalar la carta equivocada. Todo lo demás **conserva** la evidencia de
    V3.92, y se declara por qué:

    - `matched`: hay evidencia léxica de que el contexto es la acepción aprendida;
    - `ambiguous` (`declared:none`, `alternatives:none`, `gloss:other:weak`, `tie`,
      `occurrence:none`): NO hay prueba de una acepción distinta. La duda no RESTA
      evidencia igual que no la FABRICA; y en `declared:none` (palabra sin acepción
      declarada) o `alternatives:none` (palabra monosémica conocida) no hay NADA que
      contradecir. En `gloss:other:weak` SÍ hay una señal a favor de otra acepción,
      pero DÉBIL (un solo token): un posible mismatch NO basta para suprimir;
    - sin veredicto (`None`): se comporta como antes de V3.94 (conserva).

    **Decisión declarada, no medición.** El diseño de SENSE-CONTEXT-01 proponía «solo
    `matched`» y advirtió de que tratar `declared:none` como `ambiguous` «apagaría la
    mayor parte del puente». Con el ledger **vacío** (0 filas) no hay datos para
    medirlo, así que V3.94 elige la política MÍNIMA —quitar solo lo que puede probar—
    y deja el instrumento (`scripts/sense_shadow_report.py`) para revisarla cuando haya
    volumen. Es **reversible**: volver al diseño estricto es `match == matched`.
    """
    return not is_new_sense_exposure(verdict)


def _evaluate_position(
    tokens: list[str],
    index: int,
    word: str,
    declared_gloss: str,
    others: list[dict],
) -> dict:
    """Señales del uso de `word` en la posición `index` (pura)."""
    role, strength = occurrence_role(tokens, index, word)
    window = context_window(tokens, index)
    declared_overlap = sense_overlap(window, declared_gloss)
    best_other_overlap = 0
    best_other_key = ""
    other_family_matches = False
    for other in others:
        score = sense_overlap(window, _sense_gloss(other))
        if score > best_other_overlap:
            best_other_overlap = score
            best_other_key = sense_key(other)
        family = _sense_family(other)
        if role and family and family == role:
            other_family_matches = True
    return {
        "role": role,
        "strength": strength,
        "declared_overlap": declared_overlap,
        "best_other_overlap": best_other_overlap,
        "best_other_key": best_other_key,
        "other_family_matches": other_family_matches,
    }


def classify_sense_evidence(
    word: object,
    text: object,
    declared: object,
    *,
    senses: object = (),
    pos: object = "",
) -> dict:
    """Clasifica si el contexto de `text` es la acepción `declared` (V3.92+, pura).

    `declared` es la acepción que el alumno aprendió (`vocabulary.sense_json`);
    `senses` son las acepciones ALTERNATIVAS conocidas de la unidad (las de la
    ficha/caché del diccionario), sin las cuales no se puede declarar `mismatch`.
    `pos` es la POS global de la entrada, como respaldo de familia.

    Devuelve `{match, word, declared_key, declared_overlap, best_other_overlap,
    best_other_key, role, strength, mismatch_strength, reason}`. `mismatch_strength`
    es `"proven"` (único que suprime evidencia), `"possible"` o `""`. Pura y total:
    entrada rara o sin datos útiles devuelve `ambiguous`; nunca lanza.
    """
    normalized = str(word or "").strip().lower()
    declared_key = sense_key(declared)
    base = {
        "match": SENSE_AMBIGUOUS,
        "word": normalized,
        "declared_key": declared_key,
        "declared_overlap": 0,
        "best_other_overlap": 0,
        "best_other_key": "",
        "role": "",
        "strength": "",
        "mismatch_strength": "",
        "reason": REASON_DECLARED_NONE,
    }
    if not declared_key:
        return base
    tokens = tokens_of(text)
    positions = unit_positions(tokens, normalized) if normalized else []
    if not positions:
        base["reason"] = REASON_OCCURRENCE_NONE
        return base

    declared_gloss = _sense_gloss(declared)
    declared_family = _sense_family(declared) or pos_family(pos)
    declared_pos = (
        normalize_sense_text(declared.get("pos")) if isinstance(declared, dict) else ""
    )
    declared_gloss_norm = normalize_sense_text(declared_gloss)
    candidate_list = senses if isinstance(senses, (list, tuple)) else ()
    others = []
    for sense in candidate_list:
        if not isinstance(sense, dict) or sense_key(sense) == declared_key:
            continue
        # Misma acepción con distinta forma de clave (p. ej. sin `lemma`): no es
        # una alternativa, es la declarada. Se descarta para no fabricar un
        # `mismatch` contra la propia acepción aprendida.
        if (
            declared_gloss_norm
            and normalize_sense_text(sense.get("gloss")) == declared_gloss_norm
            and normalize_sense_text(sense.get("pos")) == declared_pos
        ):
            continue
        others.append(sense)

    # Se evalúa cada ocurrencia y gana la MÁS DISCRIMINATIVA (V3.93.1), no la que
    # más solapa en total. Antes pesaba `declared + other`, así que una aparición
    # ambigua (margen 0) podía empatar y ganar a otra inequívoca solo por sumar
    # más solapamiento. Peso: (¿discrimina?, margen, solape declarado, posición).
    # Así una ocurrencia con veredicto claro vence a una ambigua, y a igualdad de
    # margen se prefiere la que apoya la acepción declarada. Desempate estable:
    # la primera (orden de `unit_positions`).
    best: dict | None = None
    best_weight: tuple[int, int, int, int] | None = None
    for index in positions:
        signal = _evaluate_position(tokens, index, normalized, declared_gloss, others)
        margin = abs(signal["declared_overlap"] - signal["best_other_overlap"])
        weight = (
            1 if margin > 0 else 0,
            margin,
            signal["declared_overlap"],
            -index,
        )
        if best_weight is None or weight > best_weight:
            best_weight = weight
            best = signal
    assert best is not None  # `positions` no está vacío

    declared_overlap = best["declared_overlap"]
    best_other_overlap = best["best_other_overlap"]
    role = best["role"]
    strength = best["strength"]
    declared_family_matches = (
        bool(role) and bool(declared_family) and declared_family == role
    )
    other_family_matches = bool(best["other_family_matches"])

    mismatch_strength = ""
    if declared_overlap > best_other_overlap:
        match, reason = SENSE_MATCHED, REASON_GLOSS_DECLARED
    elif best_other_overlap >= PROVEN_OTHER_OVERLAP and (
        best_other_overlap > declared_overlap
    ):
        # Prueba FUERTE por solapamiento: dos o más tokens de la alternativa en la
        # ventana. Solo aquí un `mismatch` es PROBADO (suprime la evidencia).
        match, reason = SENSE_MISMATCH, REASON_GLOSS_OTHER
        mismatch_strength = MISMATCH_PROVEN
    elif not others:
        # Sin alternativas conocidas no se puede confirmar que el uso sea el
        # aprendido: no se fabrica un «matched».
        match, reason = SENSE_AMBIGUOUS, REASON_NO_ALTERNATIVES
    elif (
        declared_family_matches
        and not other_family_matches
        and best_other_overlap <= declared_overlap
    ):
        # Desempate gramatical a favor de la familia declarada. V3.94.1 lo exige
        # SOLO si no hay señal léxica DÉBIL a favor de otra acepción: con
        # `other_overlap > declared_overlap` el caso baja a `possible` (abajo), para
        # no etiquetar de `matched` una señal real a favor del otro sentido.
        match, reason = SENSE_MATCHED, REASON_ROLE_DECLARED
    elif other_family_matches and not declared_family_matches and strength == _STRONG:
        match, reason = SENSE_MISMATCH, REASON_ROLE_OTHER
        mismatch_strength = MISMATCH_PROVEN
    elif best_other_overlap > declared_overlap:
        # Señal DÉBIL a favor de otra acepción (un solo token): es un posible
        # mismatch, NO probado. Se declara `ambiguous` y se CONSERVA la evidencia;
        # solo el mismatch probado suprime (asimetría pedida por V3.94.1).
        match, reason = SENSE_AMBIGUOUS, REASON_GLOSS_OTHER_WEAK
        mismatch_strength = MISMATCH_POSSIBLE
    else:
        # Empate léxico y la gramática no separa (p. ej. dos sentidos nominales):
        # es exactamente el caso que NO se debe inventar.
        match, reason = SENSE_AMBIGUOUS, REASON_TIE

    return {
        "match": match,
        "word": normalized,
        "declared_key": declared_key,
        "declared_overlap": declared_overlap,
        "best_other_overlap": best_other_overlap,
        "best_other_key": best["best_other_key"],
        "role": role,
        "strength": strength,
        "mismatch_strength": mismatch_strength,
        "reason": reason,
    }
