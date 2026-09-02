"""Léxico personal (V2.3): estado y recuerdo por ítem léxico.

Baja el modelo de evidencia de "destreza" a "palabra/estructura". Convierte cada
entrada de la tabla `vocabulary` en un ítem léxico de primer nivel con:

- `item_mastery`  — dominio 0..1 combinando producción (espaciada) y reconocimiento.
- `item_recall`   — probabilidad de recuerdo actual (curva de olvido existente).
- `item_status`   — `mastered`/`known`/`learning`/`weak` (determinista).
- `next_review_days` — siguiente repaso (mismo scheduler que las destrezas).

Puro y determinista: recibe filas ya agregadas (sin I/O ni base de datos).
Reutiliza `services.forgetting` (curva de olvido) y `services.mastery`
(scheduler de repaso a nivel de destreza). El scheduler FSRS-lite de V2.11
(`services.fsrs`) opera en paralelo sobre cartas skill/lexicon; este módulo
sigue exponiendo `next_review_days` como estimación ligera del léxico.
"""

from __future__ import annotations

from services import forgetting, mastery
from services.curriculum import CEFR_ORDER

# Mínimos de producción espaciada para considerar una palabra dominada
# (coinciden con `services.vocabulary`).
MASTERY_MIN_PRODUCTIONS = 3
MASTERY_MIN_DAYS = 2

# Umbral de recuerdo bajo el cual un ítem producido se considera "weak".
RECALL_WEAK_THRESHOLD = 0.7


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def items_from_objective(level, objective) -> list[dict]:
    """Ítems léxicos declarados por un objetivo del currículo (V2.3).

    Combina `objective.vocabulary` (palabras) y `objective.concepts`
    (estructuras: "I am", "My name is"...) en una lista de dicts
    `{word, lemma, cefr, level_id, objective_id, kind}` con `kind` en
    `word`/`structure`. Normaliza a minúsculas y evita duplicados entre ambas
    fuentes (las estructuras se conservan como frases, no se tokenizan).
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
        add(word, "word")
    for concept in objective.concepts:
        add(concept, "structure")
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
    """Resumen del léxico: totales por estado y distribución CEFR."""
    statuses = {"mastered": 0, "learning": 0, "known": 0, "weak": 0}
    for row in rows:
        statuses[item_status(row, now)] += 1
    return {
        "total": len(rows),
        "known": statuses["known"],
        "learning": statuses["learning"],
        "weak": statuses["weak"],
        "mastered": statuses["mastered"],
        "by_cefr": cefr_distribution(rows),
    }


def recognized_not_produced(rows: list[dict]) -> list[str]:
    """Palabras reconocidas (leídas/oídas) pero nunca producidas.

    Son los candidatos a un *speaking micro-drill*: el alumno reconoce la palabra
    en input pero aún no la recupera al hablar (la señal; la generación del drill
    queda para V2.4).
    """
    return [
        row["word"]
        for row in rows
        if _int(row.get("exposures")) > 0 and _int(row.get("appearances")) == 0
    ]
