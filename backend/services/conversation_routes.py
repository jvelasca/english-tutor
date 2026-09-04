"""Rutas de conversation por nivel CEFR (V3.10).

Replica para conversación el patrón de las rutas de speaking/listening pero con
mini-diálogos guiados multi-turno (`curriculum/conversation_corpus.json`): cada
"ítem" de una ruta es un diálogo `{context, student_role, tutor_role,
opening_line, communicative_goals}` que el alumno conversa con el tutor (varios
turnos, guiado por la situación) y que se puntúa al terminar sobre el transcripto
completo (pipeline LLM de evidencia + señal objetiva de interacción), no turno a
turno.

Honestidad pedagógica (igual que speaking/listening/pronunciation): la ruta mide
*práctica* (diálogos dominados sobre el banco oficial) y su puerta marca como
mucho `functional`; el nivel "demostrado" solo puede venir de evidencia formal
(Speaking Assessment para la banda oral), nunca de superar la ruta.
"""
from __future__ import annotations

import json

from services.curriculum import CURRICULUM_DIR

# Banco curado de diálogos: contenido versionado fuera del código (espejo de la
# convención de `services.curriculum`). `_load_corpus()` lo carga al importar; un
# nivel con 0 diálogos se degrada en el gate (nunca certifica).
_CONVERSATION_CORPUS_PATH = CURRICULUM_DIR / "conversation_corpus.json"

# Orden CEFR de las rutas de conversación (mismo orden que currículum).
LEVEL_ORDER: list[str] = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Umbral de overall (0..1) para dar un diálogo por dominado en un intento. El
# overall sale del scorer de criterios sobre el transcripto completo de la
# conversación (0.6 equivale a ~60/100 medio entre cumplimiento de las metas,
# control gramatical, léxico, fluidez, coherencia e interacción).
CONVERSATION_PASS_THRESHOLD = 0.6

# --- Puerta de ruta ----------------------------------------------------------
# Mismos criterios calibrados que speaking: dominar todos los diálogos una vez no
# basta; la ruta exige cobertura del banco oficial, precisión global y un
# checkpoint de primeros diálogos superados.

# Fracción mínima del banco oficial dominada para declarar la ruta superada.
ROUTE_MIN_COVERAGE = 0.8
# Porcentaje mínimo de intentos superados (passed) sobre los del banco oficial.
ROUTE_MIN_ACCURACY = 70.0
# Variedad mínima de temas entre los diálogos dominados (degradada al banco real).
ROUTE_MIN_TOPICS = 3
# Checkpoint: diálogos del banco oficial superados a la PRIMERA exposición.
ROUTE_CHECKPOINT_FRACTION = 0.1
ROUTE_CHECKPOINT_MIN = 3
ROUTE_CHECKPOINT_MAX = 25

# Nº mínimo de turnos del alumno en una conversación guiada para poder evaluarla
# (la conversación no puede cerrarse con un único monosílabo: se exige un mínimo
# de intercambio real antes de puntuar el transcripto).
CONV_MIN_STUDENT_TURNS = 2
# Palabras mínimas totales del alumno para considerar evaluable el transcripto.
CONV_MIN_STUDENT_WORDS = 12


def _load_corpus() -> list[dict]:
    """Carga el corpus curado desde `curriculum/conversation_corpus.json`."""
    with _CONVERSATION_CORPUS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["items"]


# Banco oficial: items {id, level, topic, context, student_role, tutor_role,
# opening_line, communicative_goals[]}.
CONVERSATION_CORPUS: list[dict] = _load_corpus()


def dialogues_for_level(level: str) -> list[dict]:
    """Diálogos del banco oficial de un nivel CEFR (solo banco curado)."""
    return [d for d in CONVERSATION_CORPUS if d.get("level") == level]


def topics_for_level(level: str) -> tuple[str, ...]:
    """Temas presentes en el banco oficial de un nivel."""
    return tuple(
        sorted(
            {d.get("topic") for d in dialogues_for_level(level) if d.get("topic")}
        )
    )


def get_dialogue(dialogue_id: str) -> dict | None:
    """Devuelve un diálogo del banco oficial por id (None si no existe)."""
    for d in CONVERSATION_CORPUS:
        if d.get("id") == dialogue_id:
            return d
    return None


def route_items(level: str) -> list[dict]:
    """Pool de diálogos de una ruta (el banco oficial de ese nivel)."""
    return dialogues_for_level(level)


def _accuracy(rows: list[dict]) -> float | None:
    """Precisión (0..100) como % de intentos superados sobre los del nivel."""
    if not rows:
        return None
    passed = sum(1 for r in rows if r.get("passed"))
    return round(passed / len(rows) * 100, 1)


def level_items(level: str, attempts_rows: list[dict]) -> list[dict]:
    """Estado por diálogo del banco de un nivel CEFR (puro).

    Para cada diálogo de la ruta devuelve `{dialogue_id, level, opening_line,
    topic, attempts, state}` donde `state` es:
    - "unseen": nunca conversado;
    - "failed": conversado alguna vez pero nunca dominado;
    - "mastered": dominado al menos una vez.

    El estado se deriva en vivo de `conversation_route_attempts` (sin migración).
    """
    pool = route_items(level)
    seen: set[str] = set()
    passed: set[str] = set()
    counts: dict[str, int] = {}
    for row in attempts_rows:
        qid = row.get("dialogue_id")
        if not qid:
            continue
        seen.add(qid)
        counts[qid] = counts.get(qid, 0) + 1
        if row.get("passed"):
            passed.add(qid)
    items = []
    for d in pool:
        qid = d["id"]
        if qid in passed:
            state = "mastered"
        elif qid in seen:
            state = "failed"
        else:
            state = "unseen"
        items.append(
            {
                "dialogue_id": qid,
                "level": level,
                "opening_line": d.get("opening_line", ""),
                "topic": d.get("topic", ""),
                "attempts": counts.get(qid, 0),
                "state": state,
            }
        )
    return items


def _checkpoint_pass_ids(attempts_rows: list[dict]) -> set[str]:
    """Diálogos cuyo checkpoint está superado (primera exposición superada).

    La primera fila registrada de cada `dialogue_id` es su primera vez: si esa
    fila tiene `passed`, el diálogo cuenta para el checkpoint de la ruta.
    """
    passed: set[str] = set()
    seen: set[str] = set()
    for row in attempts_rows:
        qid = row.get("dialogue_id")
        if not qid or qid in seen:
            continue
        seen.add(qid)
        if row.get("passed"):
            passed.add(qid)
    return passed


def _effective_checkpoint_required(total: int) -> int:
    """Diálogos del banco oficial exigidos en el checkpoint (acotado)."""
    if total <= 0:
        return 0
    target = round(total * ROUTE_CHECKPOINT_FRACTION)
    return max(ROUTE_CHECKPOINT_MIN, min(ROUTE_CHECKPOINT_MAX, target, total))


def route_gate(level: str, attempts_rows: list[dict]) -> dict:
    """Estado de la puerta de ruta de conversation de un nivel (puro).

    Igual semántica que `route_gate` de speaking/listening: cobertura del banco
    oficial dominada, precisión global de los intentos del banco oficial y un
    checkpoint de primeras conversaciones dominadas. `blockers` vacío ⇒ `passed`.
    """
    official = dialogues_for_level(level)
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
    official_ids = {d["id"] for d in official}
    level_rows = [
        row for row in attempts_rows if row.get("dialogue_id") in official_ids
    ]
    passed_ids = {row["dialogue_id"] for row in level_rows if row.get("passed")}
    mastered = len(passed_ids)
    coverage_pct = round(mastered / total * 100, 1)
    coverage_required_pct = round(ROUTE_MIN_COVERAGE * 100)

    accuracy = _accuracy(level_rows)
    mastered_dialogues = [d for d in official if d["id"] in passed_ids]
    bank_topics = {d.get("topic") for d in official if d.get("topic")}
    topics = len({d.get("topic") for d in mastered_dialogues if d.get("topic")})
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


def current_level(passed_dialogue_ids: set[str]) -> str:
    """Nivel CEFR cuyo contenido se está practicando (routing por cobertura).

    Primer nivel cuyo banco oficial aún no está dominado por completo; si todos
    lo están, devuelve el último para poder seguir practicando.
    """
    for level in LEVEL_ORDER:
        official = dialogues_for_level(level)
        if not official:
            continue
        mastered = sum(1 for d in official if d["id"] in passed_dialogue_ids)
        if mastered < len(official):
            return level
    return LEVEL_ORDER[-1]


def review_next_dialogue(
    level: str,
    attempts_rows: list[dict],
    *,
    only_failed: bool = False,
    only_mastered: bool = False,
) -> dict:
    """Siguiente diálogo del banco de una ruta para practicar (rotación LRU).

    Devuelve el diálogo del banco cuyo último intento registrado es más antiguo
    (o cualquier diálogo aún no intentado). Con `only_failed=True` restringe a
    los intentados pero nunca dominados (estado "failed"); con
    `only_mastered=True`, a los dominados alguna vez (repasar lo aprendido). Si
    no queda ninguno del grupo, `ValueError` ("conversation.no_failed").
    """
    pool = route_items(level)
    if not pool:
        raise ValueError(f"nivel sin diálogos en el banco: {level}")
    candidates: list[dict]
    if only_failed or only_mastered:
        wanted = "failed" if only_failed else "mastered"
        keep = {
            item["dialogue_id"]
            for item in level_items(level, attempts_rows)
            if item["state"] == wanted
        }
        candidates = [d for d in pool if d["id"] in keep]
        if not candidates:
            raise ValueError("conversation.no_failed")
    else:
        candidates = pool
    candidate_ids = {d["id"] for d in candidates}
    last_index: dict[str, int] = {}
    for i, row in enumerate(attempts_rows):
        qid = row.get("dialogue_id")
        if qid in candidate_ids:
            last_index[qid] = i
    # Nunca intentados primero; entre los demás, el de intento más antiguo (LRU).
    ordered = sorted(
        candidates,
        key=lambda d: (d["id"] in last_index, last_index.get(d["id"], -1)),
    )
    return ordered[0]


def route_competence(attempt_rows: list[dict]) -> list[dict]:
    """Competencia de conversation por ruta de nivel CEFR (honesta).

    Para cada ruta devuelve `{level, state, gate}` con `state`:
    - `not_started` → sin intentos en la ruta.
    - `developing` → hay práctica pero la puerta de ruta aún no se supera.
    - `functional` → ruta superada (`route_gate` pasa).

    La ruta NUNCA devuelve `demonstrated`: demostrar el nivel exige evidencia
    formal (Speaking Assessment para la banda oral), no práctica.
    """
    result: list[dict] = []
    for level in LEVEL_ORDER:
        official_ids = {d["id"] for d in dialogues_for_level(level)}
        level_rows = [r for r in attempt_rows if r.get("dialogue_id") in official_ids]
        gate = route_gate(level, attempt_rows)
        if not level_rows:
            state = "not_started"
        elif gate["passed"]:
            state = "functional"
        else:
            state = "developing"
        result.append({"level": level, "state": state, "gate": gate})
    return result
