"""Léxico personal (V2.3 → P1): estado, recuerdo y cobertura por unidad léxica.

Baja el modelo de evidencia de "destreza" a "unidad léxica" (palabra o frase
funcional). Convierte cada entrada de la tabla `vocabulary` en un ítem léxico
de primer nivel con:

- `item_mastery`  — dominio 0..1 combinando producción (espaciada) y reconocimiento.
- `item_recall`   — probabilidad de recuerdo actual (curva de olvido existente).
- `item_status`   — `mastered`/`known`/`learning`/`weak` (determinista).
- `item_competence_matrix` — matriz Recognition/Production/Transfer/Retention
  con gaps independientes por ítem (V3.21, V20-16/V20-17; V3.22 separa
  Retention de Transfer con `exposure_days`).
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

from datetime import date, datetime

from services import forgetting, mastery
from services.curriculum import CEFR_ORDER

# Mínimos de producción espaciada para considerar una palabra dominada
# (coinciden con `services.vocabulary`).
MASTERY_MIN_PRODUCTIONS = 3
MASTERY_MIN_DAYS = 2

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



def item_mastery(row: dict) -> float:
    """Dominio (0..1) de un ítem léxico combinando producción y reconocimiento.

    La producción espaciada domina (70%): se satura con `MASTERY_MIN_PRODUCTIONS`
    apariciones en `MASTERY_MIN_DAYS` días distintos. El reconocimiento (30%)
    aporta señal débil (haber leído/oído la palabra) sin llegar a dominio.
    """
    appearances = _int(row.get("appearances"))
    production_days = _int(row.get("production_days"))
    exposures = _int(row.get("exposures"))

    prod = (
        0.5 * min(appearances, MASTERY_MIN_PRODUCTIONS) / MASTERY_MIN_PRODUCTIONS
        + 0.5 * min(production_days, MASTERY_MIN_DAYS) / MASTERY_MIN_DAYS
    )
    recognition = min(exposures, MASTERY_MIN_PRODUCTIONS) / MASTERY_MIN_PRODUCTIONS
    return round(min(1.0, 0.7 * prod + 0.3 * recognition), 3)


def item_confidence(row: dict) -> float:
    """Consistencia (0..1) de un ítem: volumen de evidencia producida + leída."""
    evidence = _int(row.get("appearances")) + _int(row.get("exposures"))
    return round(min(1.0, evidence / 3.0), 3)


def item_recall(row: dict, now: str = "") -> float:
    """Probabilidad de recuerdo actual del ítem (curva de olvido existente).

    Usa la última actividad (producción o exposición) como referencia temporal.
    """
    score = item_mastery(row)
    last = row.get("last_seen") or row.get("last_exposed_at") or ""
    return round(forgetting.retrieval_probability(score, last, now), 3)


def item_status(row: dict, now: str = "") -> str:
    """Estado determinista de un ítem: `mastered`/`known`/`learning`/`weak`.

    - `mastered`: producción espaciada y repetida (consolidado).
    - `known`: solo reconocimiento (leído/oído, nunca producido).
    - `weak`: producido pero con recuerdo por debajo del umbral (a repasar).
    - `learning`: el resto (descubierto en el currículo sin tocar, o producido
      aún en consolidación con recuerdo aceptable).
    """
    appearances = _int(row.get("appearances"))
    production_days = _int(row.get("production_days"))
    exposures = _int(row.get("exposures"))

    if appearances >= MASTERY_MIN_PRODUCTIONS and production_days >= MASTERY_MIN_DAYS:
        return "mastered"
    if appearances == 0:
        return "known" if exposures > 0 else "learning"
    return "weak" if item_recall(row, now) < RECALL_WEAK_THRESHOLD else "learning"


def next_review_days(row: dict) -> int:
    """Días hasta el próximo repaso del ítem (mismo scheduler que las destrezas)."""
    return mastery.review_interval_days(item_mastery(row), item_confidence(row))


# Canales de producción registrados en columnas `<channel>_prod` de la tabla
# `vocabulary` (V3.19). El orden importa para el desglose de `competence`.
PRODUCTION_CHANNELS: tuple[str, ...] = (
    "speaking_prod",
    "writing_prod",
    "conversation_prod",
    "chat_prod",
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
    V3.22: señal de retención RECEPTIVA (leído/oído en días distintos), que
    permite separar la dimensión Retention de Transfer sin tocar producción."""
    if _int(row.get("exposure_days")) < 2:
        return False
    first = _day_or_none(row.get("first_exposed_at"))
    last = _day_or_none(row.get("last_exposed_at"))
    if first is None or last is None:
        return False
    return (last - first).days >= 1


def item_competence_matrix(row: dict) -> dict:
    """Matriz de competencia por ítem léxico (V3.21, V20-16/V20-17; V3.22).

    Derivada SIN migrar columnas de producción (se mantiene el invariante por
    fila `sum(channel_prod) == appearances`). V3.22 separa Retention de
    Transfer usando `exposure_days`/`first_exposed_at`. Pura y determinista:

    - `recognition`       — el ítem se ha expuesto (leído/oído): `exposures > 0`.
    - `production`        — se ha producido en algún canal (`sum(channel_prod) > 0`),
      con desglose `production_channels`.
    - `transfer_contexts` — nº de canales de producción distintos.
    - `transfer`          — uso fuera del contexto original de aprendizaje:
      producción en >= 2 canales. Ya NO incluye el espaciado: ese es señal de
      retención (¿lo recuerda después de un intervalo?), no de transferencia
      (¿lo usa en otro contexto?).
    - `retention`         — recuerdo tras intervalo: producción espaciada
      (`_spaced_production`) O exposición espaciada receptiva (`_spaced_exposure`).
    - `production_gap`    — reconocida pero NUNCA producida (`recognition &&
      !production`): el gap que cierra el speaking micro-drill (antes `gap`).
    - `transfer_gap`      — producida en ejercicios pero nunca usada en otro
      contexto (`production && !transfer`): señal de falta de transferencia
      real (V3.22: antes `gap` era Recognition->Production, no un transfer gap).

    Deuda de modelo (sin migración destructiva): renombrar conceptualmente
    `appearances` -> `production_count` y `exposures` -> `exposure_count`.
    """
    exposure_total = _int(row.get("exposures"))
    recognition = exposure_total > 0
    channels = production_channels(row)
    production = len(channels) > 0
    transfer_contexts = len(channels)
    transfer = transfer_contexts >= 2
    retention = _spaced_exposure(row) or _spaced_production(row)
    return {
        "recognition": recognition,
        "production": production,
        "production_channels": channels,
        "transfer_contexts": transfer_contexts,
        "transfer": transfer,
        "retention": retention,
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
    la matriz de competencia (V3.21/V3.22): `recognized`, `produced`,
    `transfer`, `retention`, `production_gap` (reconocidas-nunca-producidas) y
    `transfer_gap` (producidas en ejercicios sin transferencia a otro contexto)."""
    statuses = {"mastered": 0, "learning": 0, "known": 0, "weak": 0}
    competence = {
        "recognized": 0,
        "produced": 0,
        "transfer": 0,
        "retention": 0,
        "production_gap": 0,
        "transfer_gap": 0,
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
      elimina, pero tampoco se repite el mismo día)."""
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
    if _int(row.get("exposures")) <= 0:
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
        if _int(row.get("exposures")) > 0 and _speaking_prod(row) == 0
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
        if _int(row.get("exposures")) > 0 or _int(row.get("appearances")) > 0:
            b["receptive"] += 1
        if _int(row.get("appearances")) > 0:
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
