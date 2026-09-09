"""Contenido Bottom-Up derivado del corpus (V3.28, Listening Engine 4.0, Fase 2).

La auditoría V3.27 (P1-02/P1-03) pedía práctica auditiva de abajo-arriba sin
re-etiquetar ni re-autorar el banco: los 490 ítems de `curriculum/
listening_corpus.json` (y el banco heredado) ya son audibles y tienen
transcripción, así que este módulo **deriva determinísticamente** de cada ítem
tareas de decodificación:

- `cloze` (MCQ): el alumno oye la frase y elige la palabra que falta en un hueco.
  El hueco se siembra en un token de contenido único y audible de la frase; las
  opciones son la palabra oída + 2 distractores de un pequeño banco por nivel.
- `partial_dictation` (producción): se ocultan 2-4 tokens de contenido contiguos
  y el alumno teclea exactamente las palabras que oyó en el hueco (puntuación
  determinista por token, patrón de `dictation`).
- `segmentation` (MCQ): el alumno decide cuál de varias grafías oyó (pares
  contraído/reducido vs. expandido) **solo donde el propio audio las contiene**
  (`transcript` las escribe literalmente). Si no hay reducción fiable, el ítem no
  se emite: nunca se inventa audio.

Desde V3.28.1 (P1-01) `derived_catalog` expone dos pools servibles por el
selector: el de `recognition` (cloze + segmentación, sesiones Caso A) y el de
`production` (`partial_dictation`, solo en sesiones Caso A con señal de
`dictation` débil, intercalado tras agotar cloze/segmentación del nivel). Las
reducciones se detectan por **token/frontera de palabra** (P1-03): una grafía
concatenada no canónica tipo `Gonnago` no es la reducción `gonna`.

Regla de integración (plan V3.28, Bloque C): los ítems derivados **no entran en
la puerta de ruta/certificación** (la puerta solo evalúa ids del banco curado) y
se marcan `derived=True` para que `route_questions`/`level_items` los excluyan de
forma defensiva. Reutilizan el audio del ítem padre (mismo `audio_id`, mismo
texto audible), por lo que no se regeneran WAV duplicados (el dominio cachea bajo
el id del padre).

Regla de honestidad: la derivación es puramente textual y determinista (sin LLM,
sin alineación acústica). Todo lo que el alumno oye ya estaba en el audio del
banco; el módulo solo selecciona qué pedir y con qué distractores.
"""
from __future__ import annotations

import re

# Prefijo de los ids de los ítems derivados (los del banco usan `l`/`c` y los de
# práctica extra generada `g-`). Permite resolver el payload en el dominio
# (submit_answer/submit_production/get_audio/level_items) sin confundirlos.
DERIVED_ID_PREFIX = "d-"

# Tipos de tarea derivados (se persisten como `task_type` en el intento).
DERIVED_TASK_TYPES: tuple[str, ...] = (
    "cloze",
    "partial_dictation",
    "segmentation",
)

# Tipos de tarea derivados que el selector puede servir en una práctica de capa
# `recognition` (volumen extra de decodificación, perfil Caso A). El dictado
# parcial es producción escrita y no pertenece a esta lista: se sirve vía el
# pool de producción (ver `PRODUCTION_SERVED_TASKS`, V3.28.1 P1-01).
RECOGNITION_SERVED_TASKS: tuple[str, ...] = ("cloze", "segmentation")

# Tipos de tarea derivados de producción escrita que el selector puede servir en
# una sesión bottom-up con señal de dictation débil (V3.28.1, P1-01): dictados
# parciales (`partial_dictation`, skill `dictation`) sobre el audio del padre.
PRODUCTION_SERVED_TASKS: tuple[str, ...] = ("partial_dictation",)

# Skills de producción del banco (de un ítem así no se deriva cloze: el alumno ya
# lo practica tecleando/repitiendo; sí puede dar dictado parcial y segmentación).
_PRODUCTION_SKILLS: frozenset[str] = frozenset({"dictation", "shadowing"})

# Turnos de hablante en el texto (`Man:`, `Woman:`, `A:`, `B:`…) — marca de
# diálogo. Un cloze sobre diálogo completo con varios turnos sería ambiguo, así
# que esos ítems no emiten cloze/dictado parcial derivado.
_TURN_MARKER = re.compile(r"^\s*[A-Za-z]+:", re.MULTILINE)

# Tokenización de palabras simples (con apóstrofo interno, sin puntuación).
_TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*")

# Separación en frases: para sembrar huecos se trabaja sobre la primera frase
# del texto (la que suena primero) cuando hay varias.
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")

# Palabras de función/cerradas: nunca son el token diana de un cloze ni de un
# dictado parcial (se decodifican con la frase, no en aislamiento).
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "so", "if", "because", "although",
        "while", "when", "where", "why", "how", "what", "who", "whom", "which",
        "that", "than", "then", "there", "here", "this", "these",
        "those", "i", "you", "he", "she", "it", "we", "they", "me", "him",
        "her", "us", "them", "my", "your", "his", "its", "our", "their",
        "mine", "yours", "hers", "ours", "theirs", "myself", "yourself",
        "himself", "herself", "itself", "ourselves", "yourselves", "themselves",
        "to", "of", "in", "on", "at", "by", "for", "with", "about", "against",
        "between", "into", "through", "during", "before", "after", "above",
        "below", "from", "up", "down", "out", "off", "over", "under", "again",
        "further", "once", "am", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "having", "do", "does", "did", "doing",
        "will", "would", "shall", "should", "may", "might", "must", "can",
        "could", "not", "no", "nor", "yes", "all", "any", "both", "each",
        "few", "more", "most", "other", "some", "such", "only", "own", "same",
        "too", "very", "just", "also", "as",
    }
)

# Grafías reducidas fuertes del connected speech cuya expansión es inequívoca.
# Coinciden con `STRONG_REDUCTIONS` de services.listening (el audio las contiene
# literalmente cuando el texto las escribe). Unión reducido → forma expandida:
# es la base honesta de la segmentación (nunca se da por supuesta una reducción
# que el texto no escribe).
REDUCTION_EXPANSIONS: dict[str, str] = {
    "gonna": "going to",
    "wanna": "want to",
    "gotta": "got to",
    "gimme": "give me",
    "lemme": "let me",
    "dunno": "don't know",
    "kinda": "kind of",
    "sorta": "sort of",
    "outta": "out of",
    "shoulda": "should have",
    "woulda": "would have",
    "coulda": "could have",
    "hafta": "have to",
    "usta": "used to",
    "whaddaya": "what do you",
}
# Reducciones que también soncribe el banco pero con expansión ambigua (ain't,
# d'you/d'ya, can't…) no se usan: la opción correcta no sería única.

# Pequeño banco de distractores por franja CEFR (palabras de contenido comunes,
# fonéticamente distinguibles entre sí). Orden fijo: la selección es posicional.
_DISTRACTOR_BANK: dict[tuple[str, ...], tuple[str, ...]] = {
    ("A1", "A2"): (
        "coffee", "morning", "evening", "kitchen", "garden", "letter", "window",
        "station", "market", "doctor", "teacher", "student", "money", "price",
        "breakfast", "dinner", "holiday", "weather", "umbrella", "suitcase",
        "ticket", "engine", "answer", "question", "brother", "sister", "mother",
        "father", "friend", "street", "bridge", "castle", "village", "minute",
        "season", "winter", "summer", "spring", "autumn", "camera", "cinema",
        "travel", "arrive", "depart", "finish", "begin", "borrow", "lend",
        "invite", "refuse", "accept", "decide", "explain", "describe",
        "remember", "forget", "follow", "belong", "contain", "compare",
    ),
    ("B1", "B2"): (
        "meeting", "deadline", "appointment", "schedule", "colleague",
        "manager", "customer", "supplier", "contract", "budget", "invoice",
        "account", "evidence", "research", "survey", "analysis", "summary",
        "interview", "candidate", "employee", "department", "equipment",
        "facility", "transport", "journey", "destination", "environment",
        "government", "population", "industry", "economy", "opportunity",
        "responsibility", "requirement", "condition", "agreement",
        "improvement", "development", "achievement", "experience", "decision",
        "suggestion", "complaint", "announcement", "advertisement",
        "performance", "audience", "rehearsal", "contract", "deadline",
        "colleague", "supervisor", "inventory", "maintenance", "purchase",
    ),
    ("C1", "C2"): (
        "circumstance", "consequence", "controversy", "implement",
        "subsequent", "thorough", "feasible", "ambiguous", "articulate",
        "apprehensive", "comprehensive", "deliberately", "demonstrate",
        "distinguish", "inevitable", "interpretation", "justification",
        "legislation", "negotiation", "participant", "perspective",
        "phenomenon", "preliminary", "prerequisite", "presumably",
        "proficiency", "proportionate", "recommendation", "representative",
        "simultaneously", "sophisticated", "substantial", "sufficient",
        "superficial", "transparent", "underestimate", "unpredictable",
        "vulnerable", "withdraw", "acknowledge",
    ),
}

# Franjas por nivel para buscar distractores.
_BAND_BY_LEVEL: dict[str, tuple[str, ...]] = {
    "A1": ("A1", "A2"),
    "A2": ("A1", "A2"),
    "B1": ("B1", "B2"),
    "B2": ("B1", "B2"),
    "C1": ("C1", "C2"),
    "C2": ("C1", "C2"),
}

# Sustituto visible del token en el hueco (cloze/dictado parcial).
_BLANK = "_" * 5


def contains_word_token(text: str, word: str) -> bool:
    """True si `word` aparece como *token completo* (no subcadena) en `text`.

    Comprobación de frontera de palabra sin distinguir mayúsculas: un token es
    `word` cuando ni antes ni después hay un carácter alfanumérico. Así
    `"Gonnago"` NO contiene `"gonna"` (la reducción debe escribirse como palabra
    para que el audio la pronuncie como tal), mientras que `"gonna,"`,
    `"Gonna"` y `"gonna"` sí lo contienen. `word` debe ir escapado (puede
    contener apóstrofos como `d'you`/`she'd`).
    """
    if not word:
        return False
    pattern = re.compile(
        rf"(?<![A-Za-z0-9]){re.escape(word)}(?![A-Za-z0-9])",
        re.IGNORECASE,
    )
    return pattern.search(text) is not None


def _stable_int(text: str) -> int:
    """Entero estable entre procesos para una cadena (hash no aleatorizado).

    `hash()` de Python está aleatorizado por proceso (`PYTHONHASHSEED`), así que
    la selección determinista usa una suma ponderada por posición: mismo texto ⇒
    mismo entero en cualquier máquina/proceso.
    """
    return sum((i + 1) * ord(ch) for i, ch in enumerate(text))


def audible_text(question: dict) -> str:
    """Texto que realmente suena en el audio del ítem padre.

    Mismo orden de preferencia que el resto del motor (`transcript` →
    `clean_transcript` → `script`): para la derivación interesa *lo que se oye*,
    que es la fuente sobre la que se siembran huecos y pares de segmentación.
    """
    return (
        (question.get("transcript") or "").strip()
        or (question.get("clean_transcript") or "").strip()
        or (question.get("script") or "").strip()
    )


def _reductions_in(text: str) -> list[str]:
    """Reducciones inequívocas presentes literalmente en el texto audible.

    Devuelve las claves de `REDUCTION_EXPANSIONS` que aparecen como **token**
    (frontera de palabra, no subcadena) del texto: el audio las pronuncia tal
    cual y no se inventa nada. Un token concatenado como `Gonnago` no es la
    reducción `gonna` y no debe contarse (V3.28.1, P1-03).
    """
    return [
        reduced
        for reduced in REDUCTION_EXPANSIONS
        if contains_word_token(text, reduced)
    ]


def _sentence(text: str) -> str | None:
    """Primera frase del texto sin marcadores de turno, o None si es diálogo.

    Un hueco de cloze necesita una frase de un solo hablante: sobre un diálogo
    con varios turnos no se sabe qué voz llena el hueco. También se descartan
    frases demasiado cortas (sin cuerpo donde sembrar).
    """
    if _TURN_MARKER.search(text):
        return None
    first = _SENTENCE_END_RE.split(text.strip())[0]
    tokens = _TOKEN_RE.findall(first)
    if len(tokens) < 6:
        return None
    return first


def _word_tokens_with_span(sentence: str) -> list[tuple[str, int, int]]:
    """Tokens `(palabra, inicio, fin)` de la frase, en orden."""
    return [
        (m.group(0), m.start(), m.end())
        for m in _TOKEN_RE.finditer(sentence)
    ]


def _is_eligible_token(word: str) -> bool:
    """Token candidato a ser diana de cloze/dictado parcial.

    Palabra de contenido (no función), sin apóstrofo interno, de 3+ letras y sin
    reducción fuerte escrita como token exacto (una palabra reducida no debe
    mostrarse como hueco de una palabra que no se deletrea así en la
    transcripción limpia). Solo se excluye el token idéntico a una reducción:
    la frontera de palabra evita descartar grafías normales que la contengan
    como subcadena (`Gonnago` no es `gonna`, pero es contenido no canónico que
    se corrige en el banco, no en el tokenizador).
    """
    lower = word.lower()
    if len(lower) < 3 or "'" in lower or lower in _STOP_WORDS:
        return False
    return lower not in REDUCTION_EXPANSIONS


def _blank_sentence(sentence: str, spans_to_blank: list[tuple[int, int]]) -> str:
    """Frase con los huecos `(inicio, fin)` sustituidos por `_BLANK`."""
    parts: list[str] = []
    cursor = 0
    for start, end in sorted(spans_to_blank):
        parts.append(sentence[cursor:start])
        parts.append(_BLANK)
        cursor = end
    parts.append(sentence[cursor:])
    return "".join(parts)


def derived_id(parent_id: str, task: str, slot: int) -> str:
    """Id determinista de un ítem derivado: `d-<padre>-<tarea>-<n>`."""
    return f"{DERIVED_ID_PREFIX}{parent_id}-{task}-{slot}"


# ---------------------------------------------------------------------------
# Fábricas por tarea. Todas devuelven `None` cuando el ítem padre no permite una
# derivación fiable (regla del plan: si no hay candidato, no se emite).
# ---------------------------------------------------------------------------

def _distractors(
    level: str, target: str, sentence_words: set[str], count: int = 2
) -> list[str]:
    """`count` distractores de la franja del nivel, distintos del hueco y del
    resto de la frase (evita opciones que el alumno ve escritas en la pregunta).
    Si no hay suficientes, devuelve los que haya (puede ser < count); el llamador
    decide emitir o no según lo que necesita."""
    band = _BAND_BY_LEVEL.get(level, ("A1", "A2"))
    pool = [
        w
        for band_key, words in _DISTRACTOR_BANK.items()
        if band_key == band
        for w in words
    ]
    chosen: list[str] = []
    for word in pool:
        if word in chosen or word.lower() == target.lower():
            continue
        if word.lower() in sentence_words:
            continue
        chosen.append(word)
        if len(chosen) == count:
            break
    return chosen


def _place_options(question_id: str, options: list[str]) -> tuple[list[str], int]:
    """Ordena las opciones de forma estable y devuelve el índice de la correcta.

    Se barajan con una permutación determinista derivada del id del ítem
    derivado, de modo que cada ítem tiene un orden fijo entre servidos y el hueco
    no queda siempre en la primera posición.
    """
    n = len(options)
    shift = _stable_int(question_id) % n
    ordered = [options[(i - shift) % n] for i in range(n)]
    return ordered, shift % n  # la correcta (índice 0 pre-barajado) acaba en `shift`


def build_cloze(parent: dict, slot: int = 0) -> dict | None:
    """Cloze auditivo MCG de un ítem: hueco en un token de contenido único.

    - Toma la primera frase audible del ítem padre (sin marcadores de turno).
    - Candidatos: tokens de contenido elegibles que aparecen una sola vez en la
      frase (un hueco repetido sería ambiguo).
    - Selección determinista por el id del padre + slot.
    - Opciones: palabra oída + 2 distractores del banco del nivel (nunca escritos
      en la frase). Si no hay frase, token único ni 2 distractores → no se emite.
    """
    text = audible_text(parent)
    sentence = _sentence(text)
    if sentence is None:
        return None
    tokens = _word_tokens_with_span(sentence)
    lower_counts: dict[str, int] = {}
    for word, _, _ in tokens:
        lower_counts[word.lower()] = lower_counts.get(word.lower(), 0) + 1
    candidates = [
        (word, start, end)
        for word, start, end in tokens
        if _is_eligible_token(word) and lower_counts[word.lower()] == 1
    ]
    if not candidates:
        return None
    base = _stable_int(parent.get("id", "") + f":cloze:{slot}")
    word, start, end = candidates[base % len(candidates)]
    sentence_words = {w.lower() for w, _, _ in tokens}
    distractors = _distractors(parent.get("level", ""), word, sentence_words, 2)
    if len(distractors) < 2:
        return None
    options = [word] + distractors
    ordered_options, answer_index = _place_options(
        derived_id(parent["id"], "cloze", slot), options
    )
    gap_sentence = _blank_sentence(sentence, [(start, end)])
    item = dict(parent)
    item.update(
        {
            "id": derived_id(parent["id"], "cloze", slot),
            "skill": "word_recognition",
            "question": f'Listen and choose the word you heard: "{gap_sentence}"',
            "options": ordered_options,
            "answer_index": answer_index,
            "topic": parent.get("topic", ""),
            "derived": True,
            "derived_from": parent["id"],
            "task_type": "cloze",
        }
    )
    return item


def _contiguous_eligible_runs(
    tokens: list[tuple[str, int, int]],
) -> list[list[tuple[str, int, int]]]:
    """Runs de tokens elegibles contiguos (>=2) para el dictado parcial."""
    runs: list[list[tuple[str, int, int]]] = []
    current: list[tuple[str, int, int]] = []
    for token in tokens:
        word = token[0]
        if _is_eligible_token(word):
            current.append(token)
        else:
            if len(current) >= 2:
                runs.append(current)
            current = []
    if len(current) >= 2:
        runs.append(current)
    return runs


def build_partial_dictation(parent: dict, slot: int = 0) -> dict | None:
    """Dictado parcial: se ocultan 2-4 tokens de contenido contiguos.

    El alumno oye la frase completa (audio del padre) y teclea exactamente las
    palabras del hueco. La referencia de puntuación (`partial_reference`) son los
    tokens ocultos; `production_reference`/scoring del dominio la usan en lugar
    del `transcript` completo. No se emite si no hay un run fiable.
    """
    text = audible_text(parent)
    sentence = _sentence(text)
    if sentence is None:
        return None
    tokens = _word_tokens_with_span(sentence)
    runs = _contiguous_eligible_runs(tokens)
    if not runs:
        return None
    base = _stable_int(parent.get("id", "") + f":partial:{slot}")
    run = runs[base % len(runs)]
    masked = run[:4]  # 2-4 tokens contiguos, nunca más de 4
    reference = " ".join(word for word, _, _ in masked)
    spans = [(start, end) for _, start, end in masked]
    blanked_sentence = _blank_sentence(sentence, spans)
    item = dict(parent)
    item.update(
        {
            "id": derived_id(parent["id"], "partial_dictation", slot),
            "skill": "dictation",
            "question": f'Type the words you heard: "{blanked_sentence}"',
            "options": [],
            "answer_index": -1,
            "topic": parent.get("topic", ""),
            "derived": True,
            "derived_from": parent["id"],
            "task_type": "partial_dictation",
            "partial_reference": reference,
        }
    )
    return item


def build_segmentation(parent: dict, slot: int = 0) -> dict | None:
    """Segmentación: ¿qué grafía oíste? (reducida vs. expandida).

    Solo se emite si el `transcript` audible contiene literalmente una reducción
    inequívoca (`gonna`, `wanna`, …). Opciones: la grafía reducida oída +
    su forma expandida + la expansión de otra reducción del mismo banco
    (distractor). Sin reducción en el audio, el ítem no se emite.
    """
    text = audible_text(parent)
    reductions = _reductions_in(text)
    if not reductions:
        return None
    reduced = reductions[slot % len(reductions)]
    expansions = sorted(REDUCTION_EXPANSIONS.values())
    distractors = [
        expansion
        for expansion in expansions
        if expansion != REDUCTION_EXPANSIONS[reduced]
    ]
    if not distractors:
        return None
    alt = distractors[
        _stable_int(parent.get("id", "") + f":seg:{slot}") % len(distractors)
    ]
    options = [reduced, REDUCTION_EXPANSIONS[reduced], alt]
    ordered_options, answer_index = _place_options(
        derived_id(parent["id"], "segmentation", slot), options
    )
    item = dict(parent)
    item.update(
        {
            "id": derived_id(parent["id"], "segmentation", slot),
            "skill": "phrase_recognition",
            "question": 'Which phrase did you hear?',
            "options": ordered_options,
            "answer_index": answer_index,
            "topic": parent.get("topic", ""),
            "derived": True,
            "derived_from": parent["id"],
            "task_type": "segmentation",
        }
    )
    return item


_BUILDERS = {
    "cloze": build_cloze,
    "partial_dictation": build_partial_dictation,
    "segmentation": build_segmentation,
}


def derive_for_item(parent: dict) -> list[dict]:
    """Ítems derivados deterministas de un ítem del banco (posiblemente vacío).

    Se deriva cloze y dictado parcial de ítems receptivos con frase de un solo
    hablante; segmentación de cualquier ítem cuyo audio contenga una reducción.
    De los ítems de producción (dictation/shadowing) no se deriva cloze ni
    dictado parcial (el alumno ya los practica sobre el propio banco).
    """
    derived: list[dict] = []
    if parent.get("derived"):
        return derived  # nunca derivar de un derivado (sin recursión)
    skill = parent.get("skill", "")
    if skill not in _PRODUCTION_SKILLS:
        for slot, task in ((0, "cloze"), (0, "partial_dictation")):
            built = _BUILDERS[task](parent, slot)
            if built is not None:
                derived.append(built)
    for slot, task in ((0, "segmentation"), (1, "segmentation")):
        built = _BUILDERS[task](parent, slot)
        if built is not None:
            derived.append(built)
    return derived


def derived_catalog(
    bank: list[dict],
) -> tuple[dict[str, dict], list[dict], list[dict]]:
    """Catálogo derivado de un banco: `(by_id, recognition_pool, production_pool)`.

    - `by_id`: índice id → ítem derivado completo (resolución en el dominio).
    - `recognition_pool`: ítems que el selector puede servir en práctica de capa
      `recognition` (cloze + segmentación), orden estable por id.
    - `production_pool` (V3.28.1, P1-01): dictados parciales (`partial_dictation`)
      que el selector puede servir en sesiones bottom-up con señal de dictation
      débil, también orden estable por id.
    """
    by_id: dict[str, dict] = {}
    recognition_pool: list[dict] = []
    production_pool: list[dict] = []
    for parent in bank:
        for item in derive_for_item(parent):
            by_id[item["id"]] = item
            if item["task_type"] in RECOGNITION_SERVED_TASKS:
                recognition_pool.append(item)
            elif item["task_type"] in PRODUCTION_SERVED_TASKS:
                production_pool.append(item)
    return by_id, recognition_pool, production_pool
