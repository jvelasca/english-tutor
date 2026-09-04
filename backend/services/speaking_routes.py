"""Rutas de speaking por nivel CEFR (V3.8).

Replica para speaking el patrón de las rutas de listening pero con tarjetas de
micro-conversación guiada (`curriculum/speaking_corpus.json`): cada "ítem" de una
ruta es una tarjeta `{setup, you, app_line, model_response}` que plantea un
intercambio breve. El alumno lee/oye la situación y la línea del interlocutor
(`app_line`), responde HABLANDO con sus palabras y, tras la evaluación, se
revela una respuesta modelo (`model_response`). La evaluación del intento es de
respuesta abierta (LLM local extrae evidencia + scorer determinista), no una
lectura en voz alta contra una frase fija.

Honestidad pedagógica (igual que listening): la ruta mide *práctica* (tarjetas
dominadas sobre el banco oficial) y su puerta marca como mucho `functional`;
el nivel "demostrado" solo puede venir de evidencia formal (Speaking Assessment,
escenarios/misiones y retención), nunca de superar la ruta.
"""
from __future__ import annotations

import json

from services.curriculum import CURRICULUM_DIR
from services.listening import difficulty_from_vector  # reutiliza el mismo criterio

# Banco curado de tarjetas: contenido versionado fuera del código (espejo de
# la convención de `services.curriculum`). `load_speaking_corpus()` lo carga al
# importar; un nivel con 0 tarjetas se degrada en el gate (nunca certifica).
_SPEAKING_CORPUS_PATH = CURRICULUM_DIR / "speaking_corpus.json"

# Orden CEFR de las rutas de speaking (mismo orden que listening/currículum).
LEVEL_ORDER: list[str] = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Prefijo de id de las tarjetas extra generadas por IA (diferencian del banco
# curado "mc-*" en las tablas y al resolver el origen de una tarjeta).
GENERATED_ID_PREFIX = "sp-"

# Umbral de overall (0..1) para dar una tarjeta por superada en un intento.
# El overall de la respuesta abierta sale del scorer de criterios (0.6 equivale
# a ~60/100 medio entre cumplimiento de la tarea, gramática, léxico, fluidez,
# coherencia e interacción).
SPEAKING_PASS_THRESHOLD = 0.6

# --- Puerta de ruta (V3.7/V3.8) ---------------------------------------------
# Mismos criterios calibrados que listening: dominar todas las tarjetas una vez
# no basta; la ruta exige cobertura del banco oficial, precisión global y un
# checkpoint de primeras respuestas superadas.

# Fracción mínima del banco oficial dominada para declarar la ruta superada.
ROUTE_MIN_COVERAGE = 0.8
# Porcentaje mínimo de intentos superados (passed) sobre los del banco oficial.
ROUTE_MIN_ACCURACY = 70.0
# Variedad mínima de temas entre las tarjetas dominadas (degradada al banco real).
ROUTE_MIN_TOPICS = 3
# Checkpoint: tarjetas del banco oficial superadas a la PRIMERA exposición.
ROUTE_CHECKPOINT_FRACTION = 0.1
ROUTE_CHECKPOINT_MIN = 5
ROUTE_CHECKPOINT_MAX = 25


def _load_corpus() -> list[dict]:
    """Carga el corpus curado desde `curriculum/speaking_corpus.json`."""
    with _SPEAKING_CORPUS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["items"]


# Banco oficial: items {id, level, topic, setup, you, app_line, model_response,
# difficulty_vector}.
SPEAKING_CORPUS: list[dict] = _load_corpus()

# Topics reales presentes en el corpus (para el generador de práctica extra).
SPEAKING_TOPICS: tuple[str, ...] = tuple(
    sorted({item.get("topic", "") for item in SPEAKING_CORPUS if item.get("topic")})
)


def phrases_for_level(level: str) -> list[dict]:
    """Tarjetas del banco oficial de un nivel CEFR (solo banco curado)."""
    return [q for q in SPEAKING_CORPUS if q.get("level") == level]


def topics_for_level(level: str) -> tuple[str, ...]:
    """Temas presentes en el banco oficial de un nivel (para generación extra)."""
    return tuple(
        sorted(
            {q.get("topic") for q in phrases_for_level(level) if q.get("topic")}
        )
    )


def get_phrase(phrase_id: str) -> dict | None:
    """Devuelve una tarjeta del banco oficial por id (None si no existe)."""
    for q in SPEAKING_CORPUS:
        if q.get("id") == phrase_id:
            return q
    return None


def route_questions(
    level: str, extra_phrases: list[dict] | None = None
) -> list[dict]:
    """Pool de tarjetas de una ruta: banco oficial + tarjetas extra activadas.

    `extra_phrases` son dicts de tarjetas generadas (payload ya con `id`). El
    resultado mantiene el orden del banco oficial primero y los extras después.
    """
    pool = list(phrases_for_level(level))
    if extra_phrases:
        # Solo las que corresponden a este nivel (defensa ante ids cruzados).
        pool.extend(q for q in extra_phrases if q.get("level") == level)
    return pool


def _accuracy(rows: list[dict]) -> float | None:
    """Precisión (0..100) como % de intentos superados sobre los del nivel."""
    if not rows:
        return None
    passed = sum(1 for r in rows if r.get("passed"))
    return round(passed / len(rows) * 100, 1)


def level_items(
    level: str,
    attempts_rows: list[dict],
    *,
    extra_phrases: list[dict] | None = None,
) -> list[dict]:
    """Estado por tarjeta del pool de un nivel CEFR (puro).

    Para cada tarjeta de la ruta (banco curado + `extra_phrases` activados)
    devuelve `{phrase_id, level, app_line, topic, difficulty, attempts, state,
    source}` donde `state` es:
    - "unseen": nunca intentada;
    - "failed": vista alguna vez pero nunca superada;
    - "mastered": superada al menos una vez.

    `source` es "base" (banco curado) o "generated" (práctica extra generada).
    El estado se deriva en vivo de `speaking_attempts` (sin migración).
    """
    pool = route_questions(level, extra_phrases)
    base_ids = {q["id"] for q in phrases_for_level(level)}
    seen: set[str] = set()
    passed: set[str] = set()
    counts: dict[str, int] = {}
    for row in attempts_rows:
        qid = row.get("phrase_id")
        if not qid:
            continue
        seen.add(qid)
        counts[qid] = counts.get(qid, 0) + 1
        if row.get("passed"):
            passed.add(qid)
    items = []
    for q in pool:
        qid = q["id"]
        if qid in passed:
            state = "mastered"
        elif qid in seen:
            state = "failed"
        else:
            state = "unseen"
        items.append(
            {
                "phrase_id": qid,
                "level": level,
                "app_line": q.get("app_line", ""),
                "topic": q.get("topic", ""),
                "difficulty": difficulty_from_vector(
                    q.get("difficulty_vector", {})
                ),
                "attempts": counts.get(qid, 0),
                "state": state,
                "source": "base" if qid in base_ids else "generated",
            }
        )
    return items


def _checkpoint_pass_ids(attempts_rows: list[dict]) -> set[str]:
    """Tarjetas cuyo checkpoint está superado (primera exposición superada).

    La primera fila registrada de cada `phrase_id` es su primera vez: si esa
    fila tiene `passed`, la tarjeta cuenta para el checkpoint de la ruta.
    """
    passed: set[str] = set()
    seen: set[str] = set()
    for row in attempts_rows:
        qid = row.get("phrase_id")
        if not qid or qid in seen:
            continue
        seen.add(qid)
        if row.get("passed"):
            passed.add(qid)
    return passed


def _effective_checkpoint_required(total: int) -> int:
    """Tarjetas del banco oficial exigidas en el checkpoint (acotado)."""
    if total <= 0:
        return 0
    target = round(total * ROUTE_CHECKPOINT_FRACTION)
    return max(ROUTE_CHECKPOINT_MIN, min(ROUTE_CHECKPOINT_MAX, target, total))


def route_gate(level: str, attempts_rows: list[dict]) -> dict:
    """Estado de la puerta de ruta de speaking de un nivel (puro).

    Igual semántica que `route_gate` de listening: cobertura del banco oficial
    dominada, precisión global de los intentos del banco oficial y un checkpoint
    de primeras respuestas superadas. `blockers` vacío ⇒ `passed`. Las tarjetas
    extra generadas NO participan en la puerta.
    """
    official = phrases_for_level(level)
    total = len(official)
    if total == 0:
        return {
            "passed": False,
            "total": 0,
            "mastered": 0,
            "coverage_pct": 0.0,
            "coverage_required_pct": round(ROUTE_MIN_COVERAGE * 100),
            "accuracy": None,
            "accuracy_required": ROUTE_MIN_ACCURACY,
            "topics": 0,
            "topics_required": 0,
            "checkpoint": 0,
            "checkpoint_required": 0,
            "blockers": ["coverage", "accuracy", "topics", "checkpoint"],
        }
    official_ids = {q["id"] for q in official}
    # La puerta se calcula solo sobre los intentos de tarjetas del banco oficial:
    # la práctica extra generada amplía el anillo pero no certifica la ruta.
    level_rows = [
        row for row in attempts_rows if row.get("phrase_id") in official_ids
    ]
    passed_ids = {row["phrase_id"] for row in level_rows if row.get("passed")}
    mastered = len(passed_ids)
    coverage_pct = round(mastered / total * 100, 1)
    coverage_required_pct = round(ROUTE_MIN_COVERAGE * 100)

    accuracy = _accuracy(level_rows)
    mastered_phrases = [q for q in official if q["id"] in passed_ids]
    bank_topics = {q.get("topic") for q in official if q.get("topic")}
    topics = len({q.get("topic") for q in mastered_phrases if q.get("topic")})
    topics_required = min(ROUTE_MIN_TOPICS, len(bank_topics))

    checkpoint = len(_checkpoint_pass_ids(level_rows))
    checkpoint_required = _effective_checkpoint_required(total)

    blockers: list[str] = []
    if coverage_pct < coverage_required_pct:
        blockers.append("coverage")
    if accuracy is None or accuracy < ROUTE_MIN_ACCURACY:
        blockers.append("accuracy")
    if topics < topics_required:
        blockers.append("topics")
    if checkpoint < checkpoint_required:
        blockers.append("checkpoint")

    return {
        "passed": not blockers,
        "total": total,
        "mastered": mastered,
        "coverage_pct": coverage_pct,
        "coverage_required_pct": coverage_required_pct,
        "accuracy": accuracy,
        "accuracy_required": ROUTE_MIN_ACCURACY,
        "topics": topics,
        "topics_required": topics_required,
        "checkpoint": checkpoint,
        "checkpoint_required": checkpoint_required,
        "blockers": blockers,
    }


def level_status(attempts_rows: list[dict]) -> list[dict]:
    """Progreso por ruta de nivel CEFR con puerta de ruta.

    Cada entrada es `{level, total, mastered, coverage_pct, accuracy, completed,
    gate}` (listado en orden CEFR). `mastered`/`coverage_pct` miden práctica
    sobre el banco oficial; `completed` refleja la puerta (`gate["passed"]`).
    """
    return [
        {
            "level": level,
            "total": gate["total"],
            "mastered": gate["mastered"],
            "coverage_pct": gate["coverage_pct"],
            "accuracy": gate["accuracy"],
            "completed": gate["passed"],
            "gate": gate,
        }
        for level in LEVEL_ORDER
        for gate in [route_gate(level, attempts_rows)]
    ]


def current_level(passed_phrase_ids: set[str]) -> str:
    """Nivel CEFR cuyo contenido se está practicando (routing por cobertura).

    Primer nivel cuyo banco oficial aún no está dominado por completo; si todos
    lo están, devuelve el último para poder seguir añadiendo práctica extra.
    """
    for level in LEVEL_ORDER:
        official = phrases_for_level(level)
        if not official:
            continue
        mastered = sum(1 for q in official if q["id"] in passed_phrase_ids)
        if mastered < len(official):
            return level
    return LEVEL_ORDER[-1]


def review_next_phrase(
    level: str,
    attempts_rows: list[dict],
    *,
    only_failed: bool = False,
    only_mastered: bool = False,
    extra_phrases: list[dict] | None = None,
) -> dict:
    """Siguiente tarjeta del pool de una ruta para practicar (rotación LRU).

    Devuelve la tarjeta del pool (banco curado + extras activados) cuyo último
    intento registrado es más antiguo (o cualquier tarjeta aún no intentada).
    Con `only_failed=True` restringe a las tarjetas intentadas pero nunca
    superadas (estado "failed"); con `only_mastered=True`, a las superadas alguna
    vez (repasar lo aprendido). Si no queda ninguna del grupo, `ValueError`
    ("speaking.no_failed").
    """
    pool = route_questions(level, extra_phrases)
    if not pool:
        raise ValueError(f"nivel sin tarjetas en el banco: {level}")
    candidates: list[dict]
    if only_failed or only_mastered:
        wanted = "failed" if only_failed else "mastered"
        keep = {
            item["phrase_id"]
            for item in level_items(
                level, attempts_rows, extra_phrases=extra_phrases
            )
            if item["state"] == wanted
        }
        candidates = [q for q in pool if q["id"] in keep]
        if not candidates:
            raise ValueError("speaking.no_failed")
    else:
        candidates = pool
    candidate_ids = {q["id"] for q in candidates}
    last_index: dict[str, int] = {}
    for i, row in enumerate(attempts_rows):
        qid = row.get("phrase_id")
        if qid in candidate_ids:
            last_index[qid] = i
    # Nunca intentadas primero; entre las demás, la de intento más antiguo (LRU).
    ordered = sorted(
        candidates,
        key=lambda q: (q["id"] in last_index, last_index.get(q["id"], -1)),
    )
    return ordered[0]


def route_competence(attempt_rows: list[dict]) -> list[dict]:
    """Competencia de speaking por ruta de nivel CEFR (honesta).

    Para cada ruta devuelve `{level, state, gate}` con `state`:
    - `not_started` → sin intentos en la ruta.
    - `developing` → hay práctica pero la puerta de ruta aún no se supera.
    - `functional` → ruta superada (`route_gate` pasa).

    La ruta NUNCA devuelve `demonstrated`: demostrar el nivel exige evidencia
    formal (Speaking Assessment + escenarios/misiones + retención), no práctica.
    """
    result: list[dict] = []
    for level in LEVEL_ORDER:
        official_ids = {q["id"] for q in phrases_for_level(level)}
        level_rows = [r for r in attempt_rows if r.get("phrase_id") in official_ids]
        gate = route_gate(level, attempt_rows)
        if not level_rows:
            state = "not_started"
        elif gate["passed"]:
            state = "functional"
        else:
            state = "developing"
        result.append({"level": level, "state": state, "gate": gate})
    return result
