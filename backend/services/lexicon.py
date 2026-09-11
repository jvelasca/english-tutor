"""Léxico personal (V2.3 → P1): estado, recuerdo y cobertura por unidad léxica.

Baja el modelo de evidencia de "destreza" a "unidad léxica" (palabra o frase
funcional). Convierte cada entrada de la tabla `vocabulary` en un ítem léxico
de primer nivel con:

- `item_mastery`  — dominio 0..1 combinando producción (espaciada) y reconocimiento
  (V3.23: el reconocimiento pondera días de exposición, no solo volumen).
- `item_recall`   — probabilidad de recuerdo actual (curva de olvido) anclada a la
  actividad más reciente, producción o exposición (V3.23, P1-01).
- `item_status`   — `mastered`/`known`/`learning`/`weak` (determinista).
- `item_competence_matrix` — matriz Recognition/Production/Transfer/Retention
  con gaps independientes por ítem (V3.21, V20-16/V20-17; V3.22 separa
  Retention de Transfer con `exposure_days`; V3.23 exige recuperación DEMORADA
  para Retention y mide Transfer por contexto de actividad `channel:activity`,
  con `spaced_exposure`/`spaced_production` como señales independientes).
- `production_contexts` — contextos reales de producción `channel:activity`
  (V3.23, P1-04), base de la transferencia por contexto y no solo por canal.
- `next_review_days` — siguiente repaso (mismo scheduler que las destrezas).

P1 (§3.2 de la Constitución): el ítem pasa de `word`/`structure` a **Lexical
Unit** con taxonomía ampliada (`LEXICAL_KINDS`). El kind se infiere en el
sembrado (`classify_kind`) con patrones inequívocos; lo ambiguo queda como
`structure` (genérico, retrocompatible) en lugar de inventar un tipo. Además
expone el **Vocabulary Coverage Indicator** receptivo/productivo por nivel
(`coverage_indicator`, §3.1): informa, no certifica.

Puro y determinista: recibe filas ya agregadas (sin I/O ni base de datos).
Reutiliza `services.forgetting` (curva de olvido) y `services.mastery`
(scheduler de repaso a nivel de destreza). El scheduler FSRS-lite de V2.11
(`services.fsrs`) opera en paralelo sobre cartas skill/lexicon; este módulo
sigue exponiendo `next_review_days` como estimación ligera del léxico.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

from services import forgetting, fsrs, mastery, planner, semantics
from services.curriculum import CEFR_ORDER
from services.evidence import (
    CONTEXT_TRANSFER_MIN,
    LEXICAL_SKILLS,
    SEMANTIC_DOUBT_ERROR,
    SEMANTIC_MISMATCH_ERROR,
    WRITE_ERROR_TYPES,
    automatic_skills,
    is_automatic,
    transfer_confidence,
    transfer_state,
)
from services.phonetics import unit_produced
from services.recall import RECALL_CUES, next_recall_rung, resolve_recall_cue

# Mínimos de producción espaciada para considerar una palabra dominada
# (coinciden con `services.vocabulary`).
MASTERY_MIN_PRODUCTIONS = 3
MASTERY_MIN_DAYS = 2

# V3.23 (P1-03): pesos de la señal RECEPTIVA en `item_mastery`. El volumen
# (`exposures`) aporta 0.4 y los días distintos (`exposure_days`) 0.6: cien
# exposiciones en un solo día ya no saturan el reconocimiento, mientras que
# exposiciones repartidas en días distintos sí acumulan evidencia de
# exposición espaciada. Pesos heurísticos a calibrar empíricamente.
RECOGNITION_VOLUME_WEIGHT = 0.4
RECOGNITION_DAYS_WEIGHT = 0.6

# V3.23 (P1-02): evidencia de RETENCIÓN por recuperación DEMORADA. Una
# recuperación correcta (éxito de micro-drill) solo acredita retención si
# ocurre `RETENTION_MIN_INTERVAL_DAYS` o más días naturales después del ancla
# (la primera exposición/producción): ver de nuevo una palabra al día siguiente
# no demuestra que se recuerda tras un intervalo. `RETENTION_MIN_RETRIEVAL_DAYS`
# es el nº mínimo de días distintos con recuperación demorada para declarar
# `retention` en la matriz de competencia. Umbrales heurísticos a calibrar.
#
# V3.35 (P1-1, Longitudinal Learning Evidence): el ANCLA deja de ser la primera
# exposición/producción para toda la vida del ítem. Ahora se encadena:
#
#     evento_1 → intervalo_1 → evento_2 → intervalo_2 → evento_3 → ...
#
# El ancla es la ÚLTIMA recuperación válida (`last_retrieval_at`) y solo la
# primera recuperación se mide desde la primera señal. El intervalo exigido lo
# calcula el scheduler (FSRS `lexicon` `due_at`) cuando existe carta; sin carta
# se conserva el suelo determinista de V3.23.
RETENTION_MIN_INTERVAL_DAYS = 1
RETENTION_MIN_RETRIEVAL_DAYS = 1

# Umbral de recuerdo bajo el cual un ítem producido se considera "weak".
RECALL_WEAK_THRESHOLD = 0.7

# Taxonomía de Lexical Unit (Constitución §3.2). `structure` se conserva como
# tipo genérico retrocompatible para las semillas que no admiten un tipo
# inequívoco (etiquetas gramaticales/temáticas del currículo).
LEXICAL_KINDS: tuple[str, ...] = (
    "word",
    "collocation",
    "phrasal_verb",
    "expression",
    "sentence_frame",
    "functional_chunk",
    "structure",
)

# Objetivos de cobertura léxica por nivel (Constitución §3.1, tabla de rangos).
# Solo es un **indicador** interno (no una puerta); los rangos se calibrarán con
# corpus/wordlists (p. ej. English Vocabulary Profile) antes de usarlos en
# cualquier umbral. C2 no declara banda numérica (None).
LEXICAL_COVERAGE_TARGETS: dict[str, dict[str, tuple[int, int] | None]] = {
    "Pre-A1": {"receptive": (150, 300), "productive": (50, 100)},
    "A1": {"receptive": (700, 1000), "productive": (400, 600)},
    "A2": {"receptive": (1200, 1800), "productive": (800, 1200)},
    "B1": {"receptive": (2000, 3000), "productive": (1500, 2000)},
    "B2": {"receptive": (3500, 5000), "productive": (2500, 3500)},
    "C1": {"receptive": (5000, 7000), "productive": (4000, 5000)},
    "C2": {"receptive": None, "productive": None},
}

# Heurísticas de `classify_kind`: el contenido del currículo no declara el tipo
# de sus `concepts`/`vocabulary`, así que solo los patrones inequívocos mueven
# la semilla a la taxonomía ampliada. El resto permanece `structure`.
_SLOT_MARKERS = ("…", "___", "...")
_PHRASAL_PARTICLES = frozenset(
    {
        "up", "down", "on", "off", "in", "out", "over", "away", "back",
        "through", "together", "around", "along", "forward",
    }
)
_SUBJECT_STARTERS = frozenset(
    {"i", "you", "he", "she", "it", "we", "they", "my", "this", "that", "there"}
)
_REQUEST_STARTERS = frozenset(
    {"can", "could", "would", "shall", "should", "will", "may", "might"}
)
_NON_VERB_FIRST = frozenset(
    {
        "i", "you", "he", "she", "it", "we", "they", "my", "this", "that",
        "there", "the", "a", "an", "to", "be", "and", "or", "of", "with",
        "from", "in", "on", "at", "for",
    }
)


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# V3.25 (F-K7/P2-01, fase 6): nombres canónicos de los contadores léxicos. Las
# filas de `vocabulary` llegan del repositorio ya renombradas
# (`production_count`/`exposure_count`); los accesores aceptan también las
# claves históricas (`appearances`/`exposures`) para seguir leyendo dicts
# legacy (tests, datos en memoria) sin romper la retrocompatibilidad.
def production_count(row: dict) -> int:
    """Producción del alumno del ítem (nº de mensajes en los que lo dijo)."""
    return _int(row.get("production_count", row.get("appearances")))


def exposure_count(row: dict) -> int:
    """Exposición del ítem (nº de mensajes del tutor en los que apareció)."""
    return _int(row.get("exposure_count", row.get("exposures")))


def lexical_unit(row: dict) -> str:
    """Unidad léxica canónica de la fila (V3.25/P2-02): la columna
    `lexical_unit`, o la superficie normalizada si la fila legacy no la tiene."""
    unit = (row.get("lexical_unit") or "").strip()
    if unit:
        return unit.lower()
    word = (row.get("word") or "").strip()
    lemma = (row.get("lemma") or "").strip()
    return (lemma or word).lower()


def cefr_difficulty(row: dict) -> float:
    """Dificultad declarada del ÍTEM léxico (V3.36): posición CEFR en 1..6.

    Reutiliza la escala 1..6 de `difficulty_from_vector` (listening) para que
    todas las evidencias del proyecto hablen la misma escala. `0.0` = no
    declarada (fila sin CEFR o con un valor fuera de la escalera). Es la
    dificultad del ÍTEM, no del intento: no cambia con el resultado.
    """
    code = (row.get("cefr") or "").strip().upper()
    if code in CEFR_ORDER:
        return float(CEFR_ORDER.index(code) + 1)
    return 0.0


def classify_kind(text: str, source: str = "concepts") -> str:
    """Clasifica el kind de una semilla curricular (Constitución §3.2).

    Determinista y conservador: solo tipa como unidad funcional lo que admite
    un patrón inequívoco (hueco → `sentence_frame`; verbo + partícula →
    `phrasal_verb`; oración interrogativa o con sujeto/petición explícita →
    `functional_chunk`; frase fija declarada bajo `vocabulary` → `collocation`).
    Las etiquetas gramaticales/temáticas (" / ", " + ") y el resto de frases
    ambiguas quedan como `structure` (genérico) para no inventar un tipo que el
    contenido no declara.
    """
    raw = text.strip().lower()
    if not raw:
        return "structure"
    if any(marker in raw for marker in _SLOT_MARKERS):
        return "sentence_frame"
    if "/" in raw or " + " in raw:
        return "structure"
    tokens = raw.split()
    if len(tokens) == 1:
        return "word"
    if (
        len(tokens) == 2
        and tokens[1] in _PHRASAL_PARTICLES
        and tokens[0].isalpha()
        and tokens[0] not in _NON_VERB_FIRST
    ):
        return "phrasal_verb"
    if raw.endswith("?"):
        return "functional_chunk"
    if tokens[0] in _REQUEST_STARTERS and tokens[1] in {
        "i",
        "you",
        "we",
        "it",
        "there",
    }:
        return "functional_chunk"
    if tokens[0] in _SUBJECT_STARTERS:
        return "functional_chunk"
    # Frases fijas declaradas bajo `vocabulary` son unidades léxicas reales
    # (p. ej. "living room"); las frases sin señal bajo `concepts` suelen ser
    # etiquetas de tema/gramática, no unidades.
    return "collocation" if source == "vocabulary" else "structure"


def items_from_objective(level, objective) -> list[dict]:
    """Ítems léxicos declarados por un objetivo del currículo (P1, §3.2).

    Combina `objective.vocabulary` (palabras y frases fijas) y
    `objective.concepts` (estructuras: "I am", "My name is"...) en una lista de
    dicts `{word, lemma, cefr, level_id, objective_id, kind}` con `kind` de la
    taxonomía `LEXICAL_KINDS` (inferido con `classify_kind`). Normaliza a
    minúsculas y evita duplicados entre ambas fuentes (las frases se conservan
    como unidades, no se tokenizan).
    """
    items: list[dict] = []
    seen: set[str] = set()

    def add(text: str, kind: str) -> None:
        key = text.strip().lower()
        if not key or key in seen:
            return
        seen.add(key)
        items.append(
            {
                "word": key,
                "lemma": key,
                "cefr": level.level,
                "level_id": level.level_id,
                "objective_id": objective.id,
                "kind": kind,
            }
        )

    for word in objective.vocabulary:
        add(word, classify_kind(word, source="vocabulary"))
    for concept in objective.concepts:
        add(concept, classify_kind(concept, source="concepts"))
    return items



def _exposure_days(row: dict) -> int:
    """Días distintos de exposición del ítem (V3.23).

    Defiende el invariante de la migración V3.22 (backfill): toda fila con
    `exposures > 0` tuvo al menos un día de exposición. Las filas parciales
    (seeds, tests, datos previos al backfill) sin `exposure_days` se tratan con
    el mismo mínimo para no degradar la señal receptiva por un campo ausente.
    """
    days = _int(row.get("exposure_days"))
    return max(days, 1) if exposure_count(row) > 0 else days


def item_mastery(row: dict) -> float:
    """Dominio (0..1) de un ítem léxico combinando producción y reconocimiento.

    La producción espaciada domina (70%): se satura con `MASTERY_MIN_PRODUCTIONS`
    apariciones en `MASTERY_MIN_DAYS` días distintos. El reconocimiento (30%)
    aporta señal débil (haber leído/oído la palabra) sin llegar a dominio.

    V3.23 (P1-03): el reconocimiento ya NO se satura con volumen: separa
    `recognition_volume` (exposures) de `recognition_days` (exposure_days) con
    pesos 0.4/0.6, de modo que la evidencia espaciada en días distintos pesa
    más que acumular muchas exposiciones en un mismo día.
    """
    productions = production_count(row)
    production_days = _int(row.get("production_days"))
    exposures = exposure_count(row)
    exposure_days = _exposure_days(row)

    prod = (
        0.5 * min(productions, MASTERY_MIN_PRODUCTIONS) / MASTERY_MIN_PRODUCTIONS
        + 0.5 * min(production_days, MASTERY_MIN_DAYS) / MASTERY_MIN_DAYS
    )
    recognition = (
        RECOGNITION_VOLUME_WEIGHT
        * min(exposures, MASTERY_MIN_PRODUCTIONS)
        / MASTERY_MIN_PRODUCTIONS
        + RECOGNITION_DAYS_WEIGHT
        * min(exposure_days, MASTERY_MIN_DAYS)
        / MASTERY_MIN_DAYS
    )
    return round(min(1.0, 0.7 * prod + 0.3 * recognition), 3)


def item_confidence(row: dict) -> float:
    """Consistencia (0..1) de un ítem: volumen de evidencia producida + leída."""
    evidence = production_count(row) + exposure_count(row)
    return round(min(1.0, evidence / 3.0), 3)


def _last_activity_at(row: dict) -> str:
    """Marca temporal ISO de la actividad léxica más reciente (V3.23, P1-01).

    Compara timestamps reales de producción (`last_seen`) y de exposición
    (`last_exposed_at`) y devuelve el ORIGINAL del más reciente. Antes se usaba
    `last_seen or last_exposed_at`, que elegía el primero que existiera y, en
    cuanto el ítem se había producido alguna vez, ignoraba por completo las
    exposiciones posteriores: un recuerdo podía parecer en degradación pese a
    una exposición reciente. Normaliza naive/aware a UTC solo para comparar.
    """
    best = ""
    best_dt: datetime | None = None
    for candidate in (row.get("last_seen"), row.get("last_exposed_at")):
        text = (candidate or "").strip()
        if not text:
            continue
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if best_dt is None or dt > best_dt:
            best, best_dt = text, dt
    return best


def item_recall(row: dict, now: str = "") -> float:
    """Probabilidad de recuerdo actual del ítem (curva de olvido existente).

    V3.23 (P1-01): usa la actividad más RECIENTE (producción o exposición,
    `_last_activity_at`) como referencia temporal de la curva de olvido.
    """
    score = item_mastery(row)
    last = _last_activity_at(row)
    return round(forgetting.retrieval_probability(score, last, now), 3)


def item_status(row: dict, now: str = "") -> str:
    """Estado determinista de un ítem: `mastered`/`known`/`learning`/`weak`.

    - `mastered`: producción espaciada y repetida (consolidado).
    - `known`: solo reconocimiento (leído/oído, nunca producido).
    - `weak`: producido pero con recuerdo por debajo del umbral (a repasar).
    - `learning`: el resto (descubierto en el currículo sin tocar, o producido
      aún en consolidación con recuerdo aceptable).
    """
    productions = production_count(row)
    production_days = _int(row.get("production_days"))
    exposures = exposure_count(row)

    if productions >= MASTERY_MIN_PRODUCTIONS and production_days >= MASTERY_MIN_DAYS:
        return "mastered"
    if productions == 0:
        return "known" if exposures > 0 else "learning"
    return "weak" if item_recall(row, now) < RECALL_WEAK_THRESHOLD else "learning"


def next_review_days(row: dict) -> int:
    """Días hasta el próximo repaso del ítem (mismo scheduler que las destrezas)."""
    return mastery.review_interval_days(item_mastery(row), item_confidence(row))


# V3.35 (Longitudinal Learning Evidence): actividades de repaso del léxico. La
# cola de repaso (`GET /api/learning/review`) propone QUÉ hacer con una palabra
# vencida, en la escalera del drill: reconocer → recuperar → producir.
# V3.39 (Fase 3): se añade `write`, la actividad que cierra la modalidad
# `written_production` (producción escrita propia, sin modelo que repetir).
# V3.40 (Fase 4): se añade `transfer`, la actividad que cierra `spontaneous_use`
# (usar la unidad en un contexto NUEVO, no solo repetirla con un modelo).
REVIEW_ACTIVITIES: tuple[str, ...] = (
    "recognition",
    "recall",
    "sentence",
    "write",
    "transfer",
)

# Longitud mínima (en palabras) de una producción PROPIA (escritura o
# transferencia). Declarado y calibrable: por debajo, el intento es la palabra
# suelta con relleno y no una producción.
WRITE_MIN_WORDS = 4

# V3.43 (Transfer 2.0, P1-02) → V3.44 (P1-01/P1-02): la adecuación semántica del
# intento de transferencia se decide en el módulo PURO `services.semantics`
# (sin LLM, premisa 21): compara la función de la ocurrencia con las FAMILIAS
# POS declaradas por los SENTIDOS de la unidad (con fallback a la `pos` global)
# y devuelve `fit`/`suspect`/`incorrect`/`unknown`. Conservador a propósito: el
# proxy INFORMA y separa la señal léxica de la semántica; solo `incorrect`
# bloquea el clean success y nunca declara dominio.
def _semantic_fit(pos: str, word: str, text: str, senses: object = ()) -> str:
    """Adecuación semántica determinista del uso de la unidad (delegada, pura)."""
    return semantics.semantic_adequacy(word, text, senses=senses, pos=pos)


def _score_production_text(word: str, text: str, min_words: int) -> dict:
    """Puntúa una producción textual PROPIA con la unidad objetivo (V3.40, pura).

    Criterio determinista y sin LLM (premisa 21), compartido por la escritura
    (`write`) y la transferencia (`transfer`) para que la acreditación sea la
    MISMA en ambas:

    - `used_word` — la unidad objetivo quedó alineada en el texto (mismo
      `unit_produced` que acredita la producción oral: un tokenizador
      normalizado único para todas las modalidades);
    - `word_count` — palabras del texto (tokens alfabéticos);
    - `passed` — `used_word` AND `word_count >= min_words`;
    - `error_type` — taxonomía observacional `WRITE_ERROR_TYPES`.

    NO juzga corrección gramatical: no hay modelo de lengua local fiable y un
    falso negativo contaminaría el modelo de alumno. Acredita PRODUCCIÓN con la
    palabra, que es lo que cierran ambas modalidades.
    """
    written = (text or "").strip()
    count = len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", written))
    used = bool(written) and unit_produced(word, written)
    passed = bool(used and count >= min_words)
    if passed:
        error_type = "correct"
    elif not written:
        error_type = "empty"
    elif not used:
        error_type = "missing_target"
    else:
        error_type = "too_short"
    if error_type not in WRITE_ERROR_TYPES:  # paridad defensiva con la taxonomía
        error_type = ""
    return {
        "used_word": used,
        "word_count": count,
        "passed": passed,
        "error_type": error_type,
    }


def score_write_attempt(word: str, text: str) -> dict:
    """Puntúa la actividad de ESCRITURA propia del drill (V3.39, pura).

    El alumno escribe una frase SUYA que use la palabra objetivo: es la
    producción con menos andamiaje de la escalera de escritura (la palabra se
    muestra, la frase no). Acredita la modalidad `written_production`. Delegación
    en `_score_production_text` con `WRITE_MIN_WORDS`. Nunca lanza.

    V3.43 (P2-04 de la auditoría de V3.42.0): `passed` acredita PRODUCCIÓN
    LÉXICA (la unidad quedó alineada en una frase con longitud mínima), NUNCA
    corrección gramatical ni ortográfica. `I goed to work yesterday.` pasa si
    usa la unidad objetivo: no hay modelo de lengua local fiable y un falso
    negativo contaminaría el modelo de alumno. No interpretar
    `written_production = success` como calidad de la lengua escrita.
    """
    return _score_production_text(word, text, WRITE_MIN_WORDS)


def score_transfer_attempt(
    word: str,
    text: str,
    *,
    pos: str = "",
    senses: object = (),
) -> dict:
    """Puntúa la actividad de TRANSFERENCIA a un contexto nuevo (V3.40 → V3.44).

    La consigna da un ESCENARIO, nunca la unidad objetivo (V3.43, P1-01): el
    alumno decide si la usa. El TRANSFER LÉXICO es determinista y sin LLM
    (`_score_production_text`): unidad alineada + longitud mínima, la MISMA
    acreditación que la escritura.

    V3.44 (P1-01/P1-02 de la auditoría de V3.43.0): la adecuación semántica se
    decide contra los SENTIDOS de la unidad (`senses`, `[{pos, gloss}]` de la
    caché) y no contra la `pos` global; así `I plan my trip` deja de ser falso
    positivo cuando `plan` declara también sentido verbal. Taxonomía:

    - `fit` — la ocurrencia encaja con algún sentido declarado;
    - `incorrect` — contradice TODOS con pista fuerte → `semantic_mismatch`,
      el ÚNICO valor que bloquea el clean success (no destruye la evidencia
      léxica: `passed` sigue siendo verdadero);
    - `suspect` — contradice con pista débil → `semantic_doubt` (advisory);
    - `unknown` — sin datos suficientes (nunca bloquea).

    `pos` es la categoría declarada del ítem y actúa de FALLBACK cuando no hay
    sentidos (retrocompatible con el contrato de V3.43). Nunca lanza.
    """
    scored = _score_production_text(word, text, WRITE_MIN_WORDS)
    adequacy = _semantic_fit(pos, word, text, senses)
    if scored["passed"]:
        if adequacy == semantics.SENSE_INCORRECT:
            scored["error_type"] = SEMANTIC_MISMATCH_ERROR
        elif adequacy == semantics.SENSE_SUSPECT:
            scored["error_type"] = SEMANTIC_DOUBT_ERROR
    scored["lexical_transfer"] = bool(scored["passed"])
    scored["semantic_fit"] = (
        None
        if adequacy == semantics.SENSE_UNKNOWN
        else adequacy == semantics.SENSE_FIT
    )
    scored["adequacy"] = adequacy
    return scored


def recommend_review_activity(
    row: dict,
    competence: dict | None = None,
    now: str = "",
    evidence: dict | None = None,
) -> dict:
    """Actividad de repaso recomendada para un ítem léxico vencido (V3.35).

    Proyección DETERMINISTA del hueco de competencia del ítem sobre la escalera
    del drill (no un modelo predictivo). Prioriza el peldaño más temprano que
    falta:

    - sin base receptiva (nunca expuesta: `exposure_count == 0`) →
      `recognition`: el repaso vuelve al primer peldaño;
    - reconocida pero sin recuperación por texto (`cued_recall == False`) →
      `recall`: es lo que el repaso espaciado debe comprobar;
    - recuperada pero nunca producida (`production_gap`) → `sentence`: el hueco
      real es la producción;
    - V3.37: si el ítem es `automatic` (éxito independiente y ESPACIADO,
      `services.evidence.is_automatic`) y no hay hueco de producción → `recall`
      de MANTENIMIENTO (razón `automatic_maintenance`), que la cola sirve en el
      peldaño más exigente disponible;
    - el resto (producida y transferida) → `recall` de mantenimiento.

    V3.38 (planner / Optimal Next Task): añade razones ADITIVAS dirigidas por la
    evidencia fina de V3.36, que solo entran cuando el ledger las justifica
    (`services.planner.evidence_reason`):

    - `error_prone` — fallos `wrong_word` repetidos (confusión real, no errata)
      → volver a practicar el ítem (`recall`);
    - `skill_gap` — el ítem logra algo pero NO tiene ningún éxito en una
      modalidad de producción (segmentación de V3.38) → `sentence`;
    - `slow_recall` — aciertos medidos pero aún lentos → `recall`.

    V3.39 (Fase 3, motor de tarea óptima): la decisión dirigida por evidencia se
    delega en `services.planner.select_task`, la ÚNICA fuente de verdad, que
    separa "¿qué skill limita?" de "¿qué ítem primero?" (prioridad, que se
    calcula en `review_queue_item`). La novedad funcional es que el hueco de
    escritura (`spoken ✓ / written ✗`) pasa a ser accionable: la modalidad
    `written_production` se cierra con la actividad `write`.

    Nota de diseño: NO se usa `item_recall` para decidir "reconocimiento débil"
    porque esa probabilidad es función de la PRODUCCIÓN (curva de olvido sobre
    `production_count`), no del reconocimiento: un ítem solo leído/oído tendría
    siempre recuerdo bajo y jamás llegaría a los peldaños de recall/producción.
    El reconocimiento débil se detecta por su señal propia (falta de exposición).

    Devuelve `{activity, reason}` con `activity` en `REVIEW_ACTIVITIES`.
    """
    matrix = competence if competence is not None else item_competence_matrix(row)
    if exposure_count(row) <= 0:
        return {"activity": "recognition", "reason": "weak_recognition"}
    if not matrix.get("cued_recall"):
        return {"activity": "recall", "reason": "no_recall_evidence"}
    if matrix.get("production_gap"):
        return {"activity": "sentence", "reason": "production_gap"}
    planned = planner.select_task(
        matrix, evidence, planner.planned_signals(evidence, matrix)
    )
    if planned["activity"]:
        return {"activity": planned["activity"], "reason": planned["reason"]}
    if evidence is not None and is_automatic(evidence):
        return {"activity": "recall", "reason": "automatic_maintenance"}
    return {"activity": "recall", "reason": "maintenance"}


def review_queue_item(
    row: dict,
    card: dict,
    *,
    now: str = "",
    evidence: dict | None = None,
    available_cues: object | None = None,
    unit_surfaces: list[str] | None = None,
) -> dict:
    """Ítem de la cola de repaso lexica (V3.35), pura y determinista.

    Combina la carta FSRS vencida (`card`) con la fila léxica (`row`): la
    actividad recomendada por hueco de competencia, la urgencia del scheduler
    (`retrievability`/`stability`) y un snapshot de la matriz de competencia.
    Nunca incluye el cue ni la forma esperada (eso lo sirve el GET del peldaño).

    V3.37 (cues graduados) añade dos campos ADITIVOS:

    - `recommended_cue` — peldaño recomendado para la actividad `recall`. Es el
      ideal pedagógico (`next_recall_rung`) resuelto contra la disponibilidad
      real de contenido (`resolve_recall_cue`) cuando el llamador la aporta
      (`available_cues`), de modo que la cola nunca recomiende un peldaño sin
      contenido. Sigue SIN incluir el cue: solo su nombre.
    - `automatic` — el ítem acumula éxito independiente y espaciado
      (`services.evidence.is_automatic`).

    V3.38 (planner / Optimal Next Task) añade, también aditivos:

    - `priority` — prioridad 0..1 de la siguiente tarea (`services.planner`):
      combina olvido, hueco, debilidad, dependencia de apoyo y latencia. Es lo
      que permite ordenar la cola por "tarea óptima" y no solo por urgencia;
    - `signals` — las señales que producen esa prioridad (explicables);
    - `why` — explicación legible (inglés) de la recomendación;
    - `automatic_skills` — modalidades en las que el ítem es automático
      (P1-03: la automaticidad deja de ser un booleano global).

    V3.39 (Fase 3) añade, aditivos:

    - `limiting_skill` — modalidad con mayor prioridad (`planner.limiting_skill`),
      el "qué limita" de la tarea óptima;
    - `task` — la DECISIÓN de tarea (`planner.select_task`): `{skill, activity,
      reason, support_level}`. Cuando la evidencia no dirige nada, `skill` es la
      modalidad limitante y `activity`/`reason` son los de la escalera, de modo
      que la cola siempre expone la tarea con su apoyo declarado.

    V3.40 (Fase 4) añade, aditivos:

    - `unit_surfaces` — formas superficiales de la misma `lexical_unit` (el
      llamador las aporta; el gobierno del estado es de la unidad);
    - `transfer` / `success_contexts` — transferencia contextual demostrada
      (éxito en >= 2 contextos distintos) y los contextos con éxito.

    V3.43 (P1-03/P1-04) añade, aditivos:

    - `transfer_state` — estado formalizado del eje de transferencia
      (`services.evidence.transfer_state`), sustituto gradual de `transfer`;
    - `context_diversity` — diversidad contextual REAL de los contextos con
      éxito limpio (dimensiones que cambian de verdad).

    V3.49 (Transfer Evidence 3.0) añade, aditivo:

    - `transfer_confidence` — confianza explicable del eje de transferencia
      (`score`/`level`/`drivers`), derivada de la misma evidencia fina.
    """
    matrix = item_competence_matrix(row)
    summary = evidence if evidence is not None else {}
    recommendation = recommend_review_activity(
        row, matrix, now=now, evidence=summary
    )
    last = card.get("last_review_at") or card.get("last_evidence_at") or ""
    elapsed = _days_between(last, now) if last else 0.0
    stability = float(card.get("stability") or 0.0)
    retrievability = (
        fsrs.retrievability(stability, elapsed)
        if stability > 0 and last
        else None
    )
    signals = planner.planned_signals(
        summary, matrix, retrievability=retrievability
    )
    recommended_cue = ""
    if recommendation["activity"] == "recall":
        ideal = (
            RECALL_CUES[-1]
            if recommendation["reason"] == "automatic_maintenance"
            else next_recall_rung(row, summary)
        )
        if available_cues is None:
            recommended_cue = ideal
        else:
            recommended_cue = resolve_recall_cue(ideal, available_cues) or ""
    return {
        "word": row.get("word") or card.get("target_id") or "",
        "lexical_unit": lexical_unit(row),
        "cefr": row.get("cefr") or "",
        "kind": row.get("kind") or "word",
        "due_at": card.get("due_at") or "",
        "state": card.get("state") or "new",
        "stability": round(stability, 3),
        "retrievability": retrievability,
        "elapsed_days": round(elapsed, 3) if elapsed is not None else None,
        "activity": recommendation["activity"],
        "reason": recommendation["reason"],
        "recommended_cue": recommended_cue,
        "automatic": is_automatic(summary),
        "automatic_skills": automatic_skills(summary),
        "priority": planner.priority_score(signals),
        "signals": signals,
        "why": planner.explain_priority(signals, recommendation["reason"]),
        # V3.39 (Fase 3): decisión de tarea óptima (skill limitante + actividad
        # + apoyo declarado). Aditivo: `activity`/`reason` conservan su
        # semántica y `task` la explica.
        "limiting_skill": planner.limiting_skill(signals),
        # V3.51: vector completo de prioridad por modalidad (aditivo).
        "skill_priorities": planner.skill_priorities(signals),
        "task": _task_decision(matrix, summary, signals, recommendation),
        "competence": matrix,
        # V3.40 (Fase 4): estado a nivel de UNIDAD (formas hermanas) y
        # transferencia contextual. Aditivos: el drill sigue practicando `word`.
        "unit_surfaces": list(unit_surfaces or [row.get("word") or ""]),
        "transfer": planner.has_contextual_transfer(summary),
        "transfer_state": transfer_state(summary),
        # V3.49 (Transfer Evidence 3.0): confianza explicable del eje (aditiva).
        "transfer_confidence": transfer_confidence(summary),
        "success_contexts": list(summary.get("success_contexts") or []),
        "context_diversity": (
            dict(summary["context_diversity"])
            if isinstance(summary.get("context_diversity"), dict)
            else {}
        ),
        "evidence": evidence if evidence is not None else {},
    }


def _task_decision(
    matrix: dict,
    evidence: dict,
    signals: dict,
    recommendation: dict,
) -> dict:
    """Decisión de tarea expuesta en la cola (V3.39, puro).

    Si la evidencia dirige la tarea (`planner.select_task`), esa es la decisión;
    si no, la modalidad limitante con la actividad y la razón de la escalera. El
    `support_level` se declara siempre a partir de la actividad
    (`planner.ACTIVITY_SUPPORT_LEVEL`), para que el cliente sepa con cuánto
    andamiaje se espera el intento.
    """
    planned = planner.select_task(matrix, evidence, signals)
    if planned["activity"]:
        return planned
    activity = recommendation.get("activity") or ""
    return {
        "skill": planner.limiting_skill(signals),
        "activity": activity,
        "reason": recommendation.get("reason") or "",
        "support_level": planner.ACTIVITY_SUPPORT_LEVEL.get(activity, ""),
    }


# Canales de producción registrados en columnas `<channel>_prod` de la tabla
# `vocabulary` (V3.19). El orden importa para el desglose de `competence`.
PRODUCTION_CHANNELS: tuple[str, ...] = (
    "speaking_prod",
    "writing_prod",
    "conversation_prod",
    "chat_prod",
)

# Orden canónico de los CANALES (nombre plano, sin sufijo `_prod`) para la
# derivación de contextos de producción (V3.23). Coincide con el orden de
# `PRODUCTION_CHANNELS` del repositorio (`chat` → `conversation`) para que el
# `context_tags` persistido y la derivación pura ordenen igual.
ACTIVITY_CHANNEL_ORDER: tuple[str, ...] = (
    "chat",
    "speaking",
    "writing",
    "conversation",
)


def production_channels(row: dict) -> list[str]:
    """Canales con producción > 0 (p. ej. ["speaking", "writing"]). V3.21."""
    channels: list[str] = []
    for column in PRODUCTION_CHANNELS:
        if _int(row.get(column)) > 0:
            channels.append(column.removesuffix("_prod"))
    return channels


def _day_or_none(value: object) -> date | None:
    """Extrae la fecha 'YYYY-MM-DD' de un valor ISO (datetime o date). V3.21."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _dt_or_none(value: object) -> datetime | None:
    """`datetime` UTC de un valor ISO (None si vacío o inválido). V3.35."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _days_between(start: object, end: object) -> float | None:
    """Días (fraccionarios) entre dos marcas ISO (None si falta alguna). V3.35."""
    start_dt = _dt_or_none(start)
    end_dt = _dt_or_none(end)
    if start_dt is None or end_dt is None:
        return None
    return max(0.0, (end_dt - start_dt).total_seconds() / 86400.0)


def retrieval_anchor_at(row: dict) -> str:
    """Marca ISO del ancla actual de la cadena de recuperación (V3.35, P1-1).

    Es la ÚLTIMA recuperación válida del ítem: el más reciente entre la última
    recuperación del micro-drill (`last_retrieval_at`) y la última recuperación
    por texto (`last_recall_at`), porque ambas son recuperaciones del mismo
    ítem y comparten la cadena longitudinal. Solo para la PRIMERA recuperación
    se retrocede a la primera señal (`min(first_seen, first_exposed_at)`).
    Devuelve "" si no hay ancla medible (fila sin recuperaciones ni
    exposición/producción).
    """
    recents = [
        dt
        for dt in (
            _dt_or_none(row.get("last_retrieval_at")),
            _dt_or_none(row.get("last_recall_at")),
        )
        if dt is not None
    ]
    if recents:
        return max(recents).isoformat()
    candidates = [
        dt
        for dt in (
            _dt_or_none(row.get("first_seen")),
            _dt_or_none(row.get("first_exposed_at")),
        )
        if dt is not None
    ]
    return min(candidates).isoformat() if candidates else ""


def delayed_retrieval_decision(
    row: dict, *, now: str, due_at: str = ""
) -> dict:
    """Decisión determinista de si un intento acredita recuperación DEMORADA.

    V3.35 (P1-1): la retención se mide como una CADENA
    `evento_n → intervalo → evento_{n+1}`, no como repeticiones ancladas a la
    primera exposición:

    - `anchor_at` — la última recuperación válida o, si es la primera, la
      primera señal del ítem (`retrieval_anchor_at`).
    - `required_days` — el intervalo exigido. Si el ítem tiene carta FSRS
      `lexicon` con `due_at`, es el hueco hasta su vencimiento (FSRS calcula el
      intervalo, que crece con cada éxito); sin carta, el suelo
      `RETENTION_MIN_INTERVAL_DAYS`. Nunca por debajo del suelo: un intervalo
      diminuto (lapse) no es una recuperación demorada.
    - `interval_days` — días reales desde el ancla hasta `now`.
    - `credited` — `interval_days >= required_days` (False sin ancla).

    Pura: no toca BD; el repositorio solo persiste el resultado.
    """
    anchor = retrieval_anchor_at(row)
    interval = _days_between(anchor, now) if anchor else None
    from_fsrs = _days_between(anchor, due_at) if (anchor and due_at) else None
    required = (
        max(float(RETENTION_MIN_INTERVAL_DAYS), from_fsrs)
        if from_fsrs is not None
        else float(RETENTION_MIN_INTERVAL_DAYS)
    )
    credited = interval is not None and interval >= required
    return {
        "anchor_at": anchor,
        "interval_days": round(interval, 4) if interval is not None else None,
        "required_days": round(required, 4),
        "credited": credited,
    }


def _spaced_production(row: dict) -> bool:
    """Producción espaciada: ocurrió en >= 2 días distintos y con un hueco de
    >= 1 día natural entre la primera y la última señal. V3.21 (V20-17)."""
    if _int(row.get("production_days")) < 2:
        return False
    first = _day_or_none(row.get("first_seen"))
    last = _day_or_none(row.get("last_seen"))
    if first is None or last is None:
        return False
    return (last - first).days >= 1


def _spaced_exposure(row: dict) -> bool:
    """Exposición espaciada: el ítem se expuso en >= 2 días distintos y con un
    hueco de >= 1 día natural entre la primera y la última exposición.
    V3.22/V3.23: señal RECEPTIVA independiente (leído/oído en días distintos).
    Ya NO acredita `retention` (V3.23): exposición repetida no demuestra que se
    recuerda el ítem; la retención exige recuperación demorada (retrieval)."""
    if _int(row.get("exposure_days")) < 2:
        return False
    first = _day_or_none(row.get("first_exposed_at"))
    last = _day_or_none(row.get("last_exposed_at"))
    if first is None or last is None:
        return False
    return (last - first).days >= 1


def _retrieval_days(row: dict) -> int:
    """Días distintos con recuperación correcta demorada (V3.23, P1-02).

    Columna `retrieval_days` (repositorio): default 0 para filas sin columna
    (tests, filas previas a la migración)."""
    return _int(row.get("retrieval_days"))


def _retrieval_successes(row: dict) -> int:
    """Nº de recuperaciones correctas demoradas (V3.23, P1-02)."""
    return _int(row.get("retrieval_successes"))


def _recall_successes(row: dict) -> int:
    """Nº de recuperaciones correctas de RECALL por texto (V3.34).

    Señal propia del paso Recall del drill (teclear la palabra desde su
    significado). Distinta de la producción (`<channel>_prod`) y de la
    recuperación demorada (`retrieval_successes`): no acredita ni una ni otra,
    solo constata que el alumno recuperó la palabra."""
    return _int(row.get("recall_successes"))


def _recall_days(row: dict) -> int:
    """Días distintos con recuperación correcta de recall (V3.34)."""
    return _int(row.get("recall_days"))


def _recall_attempts(row: dict) -> int:
    """Nº de INTENTOS de recall (acierto o fallo) del paso Recall (V3.35).

    Separa el intento del éxito: `recall_successes` solo cuenta aciertos, así
    que sin este contador no se puede distinguir "no lo intentó" de "falló"."""
    return _int(row.get("recall_attempts"))


def production_contexts(row: dict) -> list[str]:
    """Contextos de producción `channel:activity` del ítem (V3.23, P1-04).

    Contexto REAL de actividad: etiquetas explícitas de `context_tags` más un
    fallback `channel:other` por cada canal con producción que aún no tenga
    etiqueta explícita (histórico previo a V3.23). Dos actividades distintas del
    mismo canal (p. ej. `speaking:drill` y `speaking:speaking_route`) cuentan
    como contextos distintos, mientras que `chat` y `conversation` guiada dejan
    de colapsar en un mismo contexto genérico. Orden canónico: canales según
    `ACTIVITY_CHANNEL_ORDER`, luego actividad alfabética (determinista)."""
    channel_index = {ch: i for i, ch in enumerate(ACTIVITY_CHANNEL_ORDER)}
    by_channel: dict[str, set[str]] = {}
    for tag in (row.get("context_tags") or "").split(","):
        tag = tag.strip()
        if not tag:
            continue
        channel, _, activity = tag.partition(":")
        if activity:
            by_channel.setdefault(channel, set()).add(activity)
    # Fallback para filas legacy (sin `context_tags` explícito): cada canal con
    # producción sin etiqueta explícita se cubre con `channel:other`. Un canal
    # que ya tiene tag explícito NO recibe `other`.
    for channel in ACTIVITY_CHANNEL_ORDER:
        if channel in by_channel:
            continue
        if _int(row.get(f"{channel}_prod")) > 0:
            by_channel[channel] = {"other"}
    contexts: list[str] = []
    for channel in sorted(by_channel, key=lambda ch: channel_index.get(ch, 99)):
        for activity in sorted(by_channel[channel]):
            contexts.append(f"{channel}:{activity}")
    return contexts


def item_competence_matrix(row: dict) -> dict:
    """Matriz de competencia por ítem léxico (V3.21/V3.22/V3.23).

    Derivada SIN migrar columnas de producción (se mantiene el invariante por
    fila `sum(channel_prod) == appearances`). Pura y determinista:

    - `recognition`       — el ítem se ha expuesto (leído/oído): `exposures > 0`.
    - `production`        — se ha producido en algún canal (`sum(channel_prod) > 0`),
      con desglose `production_channels`.
    - `transfer_contexts` — nº de CONTEXTOS de producción distintos
      (`production_contexts`: `channel:activity`), no de canales (V3.23).
    - `transfer`          — producción en >= 2 contextos de actividad distintos:
      evidencia de uso fuera del contexto original de aprendizaje.
    - `retention`         — V3.23 (P1-02): recuperación correcta DEMORADA. Se
      acredita solo con `retrieval_days >= RETENTION_MIN_RETRIEVAL_DAYS` días
      distintos en los que el alumno recuperó el ítem (éxito de micro-drill)
      fuera del intervalo respecto a la primera señal. La exposición o
      producción espaciada ya NO bastan.
    - `spaced_exposure` / `spaced_production` — señales espaciadas
      independientes (exposición receptiva en días distintos / producción en
      días distintos): informan, no certifican retención (V3.23).
    - `cued_recall` — V3.34: el alumno ha RECUPERADO la palabra desde su
      significado en el paso Recall del drill (`recall_successes > 0`), por
      texto y sin micrófono. Señal propia: no acredita producción ni sustituye
      la recuperación demorada (`retention`), pero es más fuerte que reconocer
      el significado.
    - `production_gap`    — reconocida pero NUNCA producida (`recognition &&
      !production`): el gap que cierra el speaking micro-drill (antes `gap`).
    - `transfer_gap`      — producida en ejercicios pero nunca usada en otro
      contexto (`production && !transfer`): señal de falta de transferencia
      real.

    Deuda de modelo (sin migración destructiva): renombrar conceptualmente
    `appearances` -> `production_count` y `exposures` -> `exposure_count`.

    F-K5 (V3.25, fase 3): desambiguación por dominio. Esta matriz es la capa
    LÉXICA por ítem (señal informativa, D5/E3) y NO comparte semántica con la
    capa ACADÉMICA:
      - `transfer` léxico  = producción en ≥2 contextos `channel:activity` por
        ÍTEM.   No es el `evidence_kind="transfer"` académico (superar un
        peldaño unit/progress/level de la escalera Assessment 2.0).
      - `retention` léxico = `retrieval_days >= RETENTION_MIN_RETRIEVAL_DAYS`
        (≥1 día) de micro-drill por ítem. No es la retención certificable
        §6.3 (≥7 días, ratio ≥0.9, `evidence_kind="delayed"`).
    En un futuro schema de dominio, estos campos pasarían a llamarse
    `contextual_transfer` y `delayed_recall` para eliminar la homonimia.
    """
    exposure_total = exposure_count(row)
    recognition = exposure_total > 0
    channels = production_channels(row)
    production = len(channels) > 0
    contexts = production_contexts(row)
    transfer_contexts = len(contexts)
    transfer = transfer_contexts >= 2
    spaced_exposure = _spaced_exposure(row)
    spaced_production = _spaced_production(row)
    retention = _retrieval_days(row) >= RETENTION_MIN_RETRIEVAL_DAYS
    return {
        "recognition": recognition,
        "production": production,
        "production_channels": channels,
        "transfer_contexts": transfer_contexts,
        "transfer": transfer,
        "retention": retention,
        "spaced_exposure": spaced_exposure,
        "spaced_production": spaced_production,
        "retrieval_successes": _retrieval_successes(row),
        "retrieval_days": _retrieval_days(row),
        "cued_recall": _recall_successes(row) > 0,
        "recall_successes": _recall_successes(row),
        "recall_attempts": _recall_attempts(row),
        "recall_days": _recall_days(row),
        "production_gap": recognition and not production,
        "transfer_gap": recognition and production and not transfer,
    }


def cefr_distribution(rows: list[dict]) -> list[dict]:
    """Distribución de ítems por nivel CEFR, ordenada por la escalera canónica.

    Devuelve `[{"cefr": "A1", "count": n}, ...]`; los niveles fuera de la
    escalera (si los hubiera) van al final, ordenados alfabéticamente.
    """
    counts: dict[str, int] = {}
    for row in rows:
        cefr = (row.get("cefr") or "").strip()
        if cefr:
            counts[cefr] = counts.get(cefr, 0) + 1
    ordered = [(c, counts[c]) for c in CEFR_ORDER if c in counts]
    extra = sorted(c for c in counts if c not in CEFR_ORDER)
    ordered.extend((c, counts[c]) for c in extra)
    return [{"cefr": cefr, "count": count} for cefr, count in ordered]


def summary(rows: list[dict], now: str = "") -> dict:
    """Resumen del léxico: totales por estado, distribución CEFR y contadores de
    la matriz de competencia (V3.21/V3.22/V3.23): `recognized`, `produced`,
    `transfer`, `retention` (V3.23: recuperación demorada), `production_gap`
    (reconocidas-nunca-producidas), `transfer_gap` (producidas en ejercicios
    sin transferencia a otro contexto), `spaced_exposure` (informativo:
    expuestas en días distintos, señal receptiva independiente de la retención)
    y `recalled` (V3.34: recuperadas desde el significado en el paso Recall)."""
    statuses = {"mastered": 0, "learning": 0, "known": 0, "weak": 0}
    competence = {
        "recognized": 0,
        "produced": 0,
        "transfer": 0,
        "retention": 0,
        "production_gap": 0,
        "transfer_gap": 0,
        "spaced_exposure": 0,
        "recalled": 0,
    }
    for row in rows:
        statuses[item_status(row, now)] += 1
        matrix = item_competence_matrix(row)
        if matrix["recognition"]:
            competence["recognized"] += 1
        if matrix["production"]:
            competence["produced"] += 1
        if matrix["transfer"]:
            competence["transfer"] += 1
        if matrix["retention"]:
            competence["retention"] += 1
        if matrix["spaced_exposure"]:
            competence["spaced_exposure"] += 1
        if matrix["cued_recall"]:
            competence["recalled"] += 1
        if matrix["production_gap"]:
            competence["production_gap"] += 1
        if matrix["transfer_gap"]:
            competence["transfer_gap"] += 1
    return {
        "total": len(rows),
        "known": statuses["known"],
        "learning": statuses["learning"],
        "weak": statuses["weak"],
        "mastered": statuses["mastered"],
        "by_cefr": cefr_distribution(rows),
        **competence,
    }


def _speaking_prod(row: dict) -> int:
    """Producción de la palabra en práctica de speaking (V3.19).

    Columna `speaking_prod` de `vocabulary`: el alumno pronunció/leyó en voz
    alta la palabra en alguna superficie oral (assessment/misión/routes/
    pronunciación) o en el micro-drill. Es la señal real de "la he dicho", que
    la producción *tecleada* en el chat libre (`chat_prod`) no aporta."""
    return _int(row.get("speaking_prod"))


# V3.21 (V20-06): nº de días distintos con éxito de drill (`drill:<word>:ok` o
# `drill:<word>:sentence:ok`) exigidos para considerar "consolidada" la palabra
# en el micro-drill y sacarla de la lista de candidatas. No declara dominio
# (D5/E3): es solo el criterio de salida de la lista "pendiente".
DRILL_SPACED_OK_DAYS = 2


def drill_ok_days(events: list[dict]) -> dict[str, set[str]]:
    """Días (YYYY-MM-DD) con éxito de speaking micro-drill por palabra.

    V3.21 (V20-06): el micro-drill registra eventos `learning_events` del tipo
    `drill:<word>:ok` (paso palabra) y `drill:<word>:sentence:ok` (paso frase).
    Devuelve `{word: {día, ...}}` para exigir éxito ESPACIADO (>= 2 días) antes
    de dejar de ofrecer la palabra en la lista de candidatas. Ignora el resto de
    eventos. Pura y determinista.
    """
    days_by_word: dict[str, set[str]] = {}
    for event in events:
        detail = (event.get("detail") or "").strip()
        if not detail.startswith("drill:"):
            continue
        created = event.get("created_at") or ""
        day = created[:10] if created else ""
        word, outcome = _drill_event_word_outcome(detail)
        if word and outcome == "ok" and day:
            days_by_word.setdefault(word, set()).add(day)
    return days_by_word


def _drill_event_word_outcome(detail: str) -> tuple[str, str]:
    """Extrae `(word, outcome)` de un detalle `drill:<word>[:sentence]:<outcome>`.

    El propio `word` puede contener espacios o dos puntos, por eso se descompone
    desde el final: el último segmento es el outcome y el penúltimo, si existe,
    es la marca `sentence` del paso frase (V3.21, F6.1).
    """
    body = detail[len("drill:") :]
    parts = body.split(":")
    if not parts or parts[-1] not in {"ok", "ko", "unclear"}:
        return "", ""
    outcome = parts[-1]
    if len(parts) >= 2 and parts[-2] == "sentence":
        return ":".join(parts[:-2]), outcome
    return ":".join(parts[:-1]), outcome


def drill_candidates(
    rows: list[dict],
    limit: int = 8,
    now: str = "",
    *,
    ok_days: dict[str, set[str]] | None = None,
    today: str = "",
) -> list[str]:
    """Candidatos a speaking micro-drill escalera (V3.21, F6/V20-06).

    Filtra ítems con `exposures > 0` (leídos/oídos del tutor) que aún no han
    consolidado la producción oral espaciada, ordenados por recuerdo actual
    ascendente (primero los más olvidados) y acotados a `limit`.

    Criterio de salida de la lista "pendiente" (no declara dominio, D5/E3):
    - nunca dichas (`speaking_prod == 0`) → siempre candidatas;
    - ya dichas pero sin éxito espaciado → siguen pendientes:
      - salen con 2 días de éxito de drill (`ok_days`, V3.21/F6.2); o
      - salen si hay señal de speaking espaciada sin eventos de drill
        (`speaking_prod >= 2` y `production_days >= 2`, aproximación);
    - `today` (YYYY-MM-DD): si la palabra ya se superó HOY en el drill y aún no
      está consolidada, se oculta hasta mañana (una producción del día no la
      elimina, pero tampoco se repite el mismo día).

    V3.35 (P1-2): esta cola es SOLO de producción oral pendiente. El repaso
    espaciado del léxico (cartas FSRS `lexicon` vencidas) vive en la cola propia
    `GET /api/learning/review` (actividad recomendada por hueco de competencia);
    ya NO se inyecta aquí como prioridad. Mezclar la programación espaciada con
    el micro-drill de speaking confundía dos conceptos distintos."""
    pending = (
        row
        for row in rows
        if _is_pending_drill_candidate(row, ok_days=ok_days, today=today)
    )
    candidates = sorted(pending, key=lambda row: item_recall(row, now))
    return [row["word"] for row in candidates[: max(0, limit)]]


def _is_pending_drill_candidate(
    row: dict,
    *,
    ok_days: dict[str, set[str]] | None = None,
    today: str = "",
) -> bool:
    if exposure_count(row) <= 0:
        return False
    word = row.get("word", "")
    days = (ok_days or {}).get(word, set()) if ok_days else set()
    if not _speaking_prod(row) > 0:
        return True
    # Producida oralmente alguna vez: pendiente hasta éxito espaciado.
    if len(days) >= DRILL_SPACED_OK_DAYS:
        return False
    if (
        _int(row.get("speaking_prod")) >= DRILL_SPACED_OK_DAYS
        and _int(row.get("production_days")) >= DRILL_SPACED_OK_DAYS
    ):
        return False
    if today and today in days:
        return False
    return True


def recognized_not_produced(rows: list[dict]) -> list[str]:
    """Palabras reconocidas (leídas/oídas) pero nunca producidas *hablando*.

    V3.19: la señal pasa de "nunca tecleada" (semántica de teclado, era
    calculable con `appearances == 0`) a "expuestas y nunca dichas en una
    superficie oral" (`speaking_prod == 0`), que es lo que un speaking
    micro-drill puede cerrar. Sin límite (respaldo de la lista completa).

    Nota V3.21 (V20-06): esta función conserva la semántica histórica "nunca
    dichas"; la lista "pendiente" del drill (que reutiliza las ya dichas con
    éxito no espaciado) vive en `drill_candidates`."""
    return [
        row["word"]
        for row in rows
        if exposure_count(row) > 0 and _speaking_prod(row) == 0
    ]


_COVERAGE_ORDER = ["Pre-A1", *CEFR_ORDER]


def _band_ratio(count: int, band: tuple[int, int] | None) -> float | None:
    """Ratio 0..1 frente al extremo superior de la banda objetivo (None sin banda)."""
    if band is None:
        return None
    return round(min(1.0, count / band[1]), 3)


def coverage_indicator(rows: list[dict], now: str = "") -> dict:
    """Vocabulary Coverage Indicator receptivo/productivo (Constitución §3.1).

    **Indicador interno, no una puerta**: informa del volumen de unidades
    léxicas encontradas/producidas, comparado con las bandas objetivo
    (`LEXICAL_COVERAGE_TARGETS`) que se calibrarán con corpus antes de usarse en
    cualquier umbral.

    - `receptive`  — unidades con evidencia de input o producción (leídas/oídas
      o producidas al menos una vez).
    - `productive` — unidades producidas al menos una vez (señal de producción,
      no dominio).
    - `mastered`   — unidades consolidadas (producción espaciada ≥3 en ≥2 días).
    - `by_level`   — desglose por nivel CEFR (Pre-A1..C2) con ratio frente a la
      banda objetivo (`receptive_pct`/`productive_pct`, None cuando la banda no
      es numérica, p. ej. C2).
    """
    buckets: dict[str, dict[str, int]] = {}

    def bucket(cefr: str) -> dict[str, int]:
        return buckets.setdefault(
            cefr,
            {
                "total": 0,
                "receptive": 0,
                "productive": 0,
                "mastered": 0,
                "known": 0,
                "learning": 0,
                "weak": 0,
            },
        )

    for row in rows:
        cefr = (row.get("cefr") or "").strip()
        if cefr not in LEXICAL_COVERAGE_TARGETS:
            continue
        b = bucket(cefr)
        b["total"] += 1
        status = item_status(row, now)
        b[status] += 1  # mastered/known/learning/weak ya existen en el bucket
        if exposure_count(row) > 0 or production_count(row) > 0:
            b["receptive"] += 1
        if production_count(row) > 0:
            b["productive"] += 1

    by_level: list[dict] = []
    for cefr in _COVERAGE_ORDER:
        if cefr not in buckets:
            continue
        b = buckets[cefr]
        targets = LEXICAL_COVERAGE_TARGETS[cefr]
        by_level.append(
            {
                "cefr": cefr,
                **b,
                "receptive_pct": _band_ratio(
                    b["receptive"], targets["receptive"]
                ),
                "productive_pct": _band_ratio(
                    b["productive"], targets["productive"]
                ),
            }
        )
    totals = {key: 0 for key in ("receptive", "productive", "mastered")}
    for b in buckets.values():
        for key in totals:
            totals[key] += b[key]
    return {
        "receptive": totals["receptive"],
        "productive": totals["productive"],
        "mastered": totals["mastered"],
        "by_level": by_level,
    }


# V3.25.1 (P1-02, auditoría externa V3.25): agregado REAL por unidad léxica.
# `lexical_unit` ya existía como columna, pero el cálculo de dominio seguía
# siendo por fila (una entrada por `word`/surface form). Estas funciones
# agrupan las filas por `lexical_unit` para exponer el conocimiento a nivel de
# UNIDAD sin fundir las superficies: `go/going/went/gone` comparten la unidad
# `go`, pero cada forma conserva su PROPIO estado (dominar `go` no implica
# dominar `going`). El estado de unidad es un derivado informativo (máximo
# entre superficies), nunca un sustituto de la competencia por forma.


def _unit_status(statuses: list[str]) -> str:
    """Estado agregado de una unidad desde los estados de sus superficies.

    Indicador informativo (no sustituye a la competencia por forma):
    `mastered` si alguna superficie está dominada; si no, `weak` si alguna lo
    está; `known` si solo hay reconocimiento; `learning` en el resto."""
    if "mastered" in statuses:
        return "mastered"
    if "weak" in statuses:
        return "weak"
    if "known" in statuses:
        return "known"
    return "learning"


def _unit_representative(group: list[dict], unit: str) -> dict:
    """Fila representativa de una unidad para su metadata (kind/cefr/lemma).

    Prefiere la fila de currículo, luego la superficie que coincide con la
    unidad canónica (p. ej. `go` para la unidad `go`), luego el CEFR menor y
    finalmente la superficie alfabéticamente menor. Determinista."""
    return min(
        group,
        key=lambda r: (
            r.get("source") != "curriculum",
            (r.get("word") or "").lower() != unit,
            (r.get("cefr") or ""),
            (r.get("word") or "").lower(),
        ),
    )


def units_from_rows(rows: list[dict], now: str = "") -> list[dict]:
    """Unidades léxicas agregadas (V3.25.1/P1-02).

    Agrupa las filas por `lexical_unit` y devuelve una entrada por UNIDAD con:

    - `surfaces`: cada forma superficial con su estado/mastery/recall propio
      (independientes entre sí) más contadores y matriz de competencia;
    - conocimiento derivado de unidad: `recognized`/`produced`/`transfer`,
      `mastery`/`recall` (máximo entre superficies, informativo), `status`
      agregado (`_unit_status`), `mastered_surfaces`;
    - gaps a nivel de unidad: `production_gap` (reconocida y ninguna forma
      producida) y `transfer_gap` (producida y ninguna forma transferida).

    Orden determinista: unidades por `lexical_unit`, superficies por `word`.
    """
    by_unit: dict[str, list[dict]] = {}
    for row in rows:
        unit = lexical_unit(row)
        if not unit:
            continue
        by_unit.setdefault(unit, []).append(row)

    units: list[dict] = []
    for unit in sorted(by_unit):
        group = by_unit[unit]
        surfaces = [
            {
                "word": row["word"],
                "lemma": row.get("lemma") or "",
                "cefr": row.get("cefr") or "",
                "kind": row.get("kind") or "word",
                "source": row.get("source") or "user",
                "status": item_status(row, now),
                "mastery": item_mastery(row),
                "recall": item_recall(row, now),
                "production_count": production_count(row),
                "exposure_count": exposure_count(row),
                "speaking_prod": _speaking_prod(row),
                "competence": item_competence_matrix(row),
            }
            for row in sorted(group, key=lambda r: (r.get("word") or "").lower())
        ]
        rep = _unit_representative(group, unit)
        produced = any(s["production_count"] > 0 for s in surfaces)
        recognized = any(
            s["exposure_count"] > 0 or s["production_count"] > 0
            for s in surfaces
        )
        transfer = any(s["competence"]["transfer"] for s in surfaces)
        statuses = [s["status"] for s in surfaces]
        units.append(
            {
                "lexical_unit": unit,
                "kind": rep.get("kind") or "word",
                "cefr": rep.get("cefr") or "",
                "lemma": rep.get("lemma") or "",
                "source": (
                    "curriculum"
                    if any(s["source"] == "curriculum" for s in surfaces)
                    else "user"
                ),
                "status": _unit_status(statuses),
                "mastery": round(max(s["mastery"] for s in surfaces), 3),
                "recall": round(max(s["recall"] for s in surfaces), 3),
                "surface_count": len(surfaces),
                "mastered_surfaces": sum(
                    1 for s in surfaces if s["status"] == "mastered"
                ),
                "recognized": recognized,
                "produced": produced,
                "transfer": transfer,
                "production_count": sum(s["production_count"] for s in surfaces),
                "exposure_count": sum(s["exposure_count"] for s in surfaces),
                "production_gap": recognized and not produced,
                "transfer_gap": produced and not transfer,
                "surfaces": surfaces,
            }
        )
    return units


def summary_units(rows: list[dict], now: str = "") -> dict:
    """Resumen por UNIDAD léxica (V3.25.1/P1-02): cada `lexical_unit` cuenta
    una sola vez (`go/going/went/gone` ya no son 4 conocimientos
    independientes).

    Equivalente de `summary` (por superficie) a nivel de unidad: totales por
    estado derivado, competencia de unidad (reconocida/producida/transferida,
    gaps) y distribución CEFR de las unidades. Contadores de superficie
    (`surface_total`, `mastered_surfaces`) acompañan como contexto del agregado.
    """
    units = units_from_rows(rows, now)
    statuses = {"mastered": 0, "learning": 0, "known": 0, "weak": 0}
    competence = {
        "recognized": 0,
        "produced": 0,
        "transfer": 0,
        "production_gap": 0,
        "transfer_gap": 0,
        "surface_total": 0,
        "mastered_surfaces": 0,
    }
    cefr_buckets: dict[str, int] = {}
    for u in units:
        statuses[u["status"]] += 1
        for key in ("recognized", "produced", "transfer"):
            if u[key]:
                competence[key] += 1
        if u["production_gap"]:
            competence["production_gap"] += 1
        if u["transfer_gap"]:
            competence["transfer_gap"] += 1
        competence["surface_total"] += u["surface_count"]
        competence["mastered_surfaces"] += u["mastered_surfaces"]
        if u["cefr"]:
            cefr_buckets[u["cefr"]] = cefr_buckets.get(u["cefr"], 0) + 1
    ordered = [(c, cefr_buckets[c]) for c in CEFR_ORDER if c in cefr_buckets]
    ordered.extend(
        (c, cefr_buckets[c])
        for c in sorted(cefr_buckets)
        if c not in CEFR_ORDER
    )
    return {
        "total": len(units),
        "mastered": statuses["mastered"],
        "learning": statuses["learning"],
        "known": statuses["known"],
        "weak": statuses["weak"],
        "by_cefr": [{"cefr": c, "count": n} for c, n in ordered],
        **competence,
    }


# V3.40 (Fase 4, P1-04 de la auditoría de V3.38.1): agrega el estado PEDAGÓGICO
# (la evidencia) por `lexical_unit`, no solo por forma superficial. `go/went/
# gone/going` dejan de ser cuatro estados independientes cuando el planner
# decide: la unidad es la que sabe o no sabe, y sus formas son sus pruebas.
#
# Solo se SUMAN los contadores (volumen, días, modalidades, errores) y se
# recalculan las ratios: es un roll-up informativo y determinista, no una
# segunda definición de automaticidad (`automatic`/`automatic_skills` se OR-ean
# de las formas, que es lo que ya exponía `automatic_skills` por forma).
_UNIT_EVIDENCE_SUM_KEYS: tuple[str, ...] = (
    "attempts",
    "successes",
    "distinct_success_days",
    "independent_successes",
    "independent_success_days",
)
_UNIT_EVIDENCE_SUM_MAPS: tuple[str, ...] = (
    "error_types",
    "skill_successes",
    "skill_success_days",
    "skill_independent_successes",
    "skill_independent_days",
    "skill_attempts",
)


def unit_evidence(
    rows: list[dict],
    evidence_by_word: dict | None = None,
) -> list[dict]:
    """Evidencia agregada por `lexical_unit` (V3.40, pura y determinista).

    Devuelve una entrada por unidad con las formas superficiales que la componen
    y el roll-up de su evidencia:

    - contadores sumados (`attempts`, `successes`, `independent_successes`, …);
    - mapas sumados por modalidad y tipo de error;
    - `success_rate` RECALCULADA del total (nunca media de medias);
    - `automatic` / `automatic_skills` unidos de las formas (si cualquier forma
      lo es, la unidad da esa modalidad por consolidada);
    - `success_contexts` unidos y `transfer` (éxito en >= 2 contextos, contando
      los contextos de todas las formas).

    Es la pieza que permite que el estado pedagógico esté gobernado por la
    UNIDAD (irregulares, phrasal verbs, collocations, chunks) sin cambiar la
    evidencia por forma: cada intento sigue registrando su `surface_form`.
    Orden determinista por unidad. `evidence_by_word` acepta el mapa
    `{word: resumen}` del repositorio; sin él solo se exponen las formas.
    """
    evidence_map = evidence_by_word if isinstance(evidence_by_word, dict) else {}
    by_unit: dict[str, list[str]] = {}
    for row in rows:
        unit = lexical_unit(row)
        word = (row.get("word") or "").strip()
        if not unit or not word:
            continue
        forms = by_unit.setdefault(unit, [])
        if word not in forms:
            forms.append(word)
    result: list[dict] = []
    for unit in sorted(by_unit):
        forms = sorted(by_unit[unit])
        totals: dict[str, int] = dict.fromkeys(_UNIT_EVIDENCE_SUM_KEYS, 0)
        maps: dict[str, dict[str, int]] = {
            key: {} for key in _UNIT_EVIDENCE_SUM_MAPS
        }
        automatic = False
        automatic_skills: list[str] = []
        success_contexts: set[str] = set()
        for word in forms:
            summary = evidence_map.get(word)
            if not isinstance(summary, dict):
                continue
            for key in _UNIT_EVIDENCE_SUM_KEYS:
                totals[key] += _int(summary.get(key))
            for key in _UNIT_EVIDENCE_SUM_MAPS:
                bucket = summary.get(key)
                if not isinstance(bucket, dict):
                    continue
                for name, value in bucket.items():
                    maps[key][str(name)] = maps[key].get(str(name), 0) + _int(value)
            if summary.get("automatic") or summary.get("automatic_skills"):
                automatic = True
            for skill in summary.get("automatic_skills") or ():
                if skill not in automatic_skills:
                    automatic_skills.append(str(skill))
            for context in summary.get("success_contexts") or ():
                text = str(context or "").strip()
                if text:
                    success_contexts.add(text)
        attempts = totals["attempts"]
        successes = totals["successes"]
        result.append(
            {
                "lexical_unit": unit,
                "surfaces": forms,
                "surface_count": len(forms),
                **totals,
                "success_rate": (
                    round(successes / attempts, 4) if attempts else 0.0
                ),
                **maps,
                "automatic": automatic,
                "automatic_skills": [
                    skill for skill in LEXICAL_SKILLS if skill in automatic_skills
                ],
                "success_contexts": sorted(success_contexts),
                # V3.43: el roll-up por unidad conserva el booleano histórico
                # (unión de contextos con éxito de todas las formas). El estado
                # AUTORITATIVO del eje de transferencia es `transfer_state`
                # (con diversidad real y éxitos limpios) a nivel de resumen.
                "transfer": len(success_contexts) >= CONTEXT_TRANSFER_MIN,
            }
        )
    return result
