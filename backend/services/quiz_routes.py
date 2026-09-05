"""Motor compartido de rutas quiz MC sobre los checks del currículo (V3.11+).

Vocabulary (v3.11) y Grammar (v3.12) comparten el mismo diseño de ruta: el banco
de un nivel son los `checks` de opción múltiple del currículo oficial
(`curriculum/<level>.json` → `objectives[].checks`) con la skill pedida. Cada
"ítem" de una ruta es un check `{check_id, level, topic, prompt, options,
correct_index}` y la evaluación es determinista (acierto = superado), sin LLM y
sin corpus propio: el pool se lee del currículo en caliente.

Este módulo es el motor puro común, parametrizado por `skill`. Vocabulary y
Grammar montan sobre él sus repositorios/dominios/routers particulares (tabla de
intentos y URL propia).

Honestidad pedagógica (igual que speaking/listening/pronunciation/conversation):
la ruta mide *práctica* (checks dominados sobre el banco oficial del currículo) y
su puerta marca como mucho `functional`; el nivel "demostrado" solo puede venir
de evidencia formal (exámenes/escalera del curso para la banda), nunca de
superar la ruta.
"""
from __future__ import annotations

import json
from functools import lru_cache

from services.curriculum import CURRICULUM_DIR, CEFR_ORDER

# Orden CEFR de las rutas quiz (mismo orden que el currículum).
LEVEL_ORDER: list[str] = list(CEFR_ORDER)

# --- Puerta de ruta ----------------------------------------------------------
# Mismos criterios calibrados que el resto de rutas: dominar todos los checks una
# vez no basta; la ruta exige cobertura del banco oficial, precisión global y un
# checkpoint de primeros checks superados.
ROUTE_MIN_COVERAGE = 0.8
ROUTE_MIN_ACCURACY = 70.0
ROUTE_MIN_TOPICS = 3

# Checkpoint: checks del banco oficial superados a la PRIMERA exposición.
ROUTE_CHECKPOINT_FRACTION = 0.1
ROUTE_CHECKPOINT_MIN = 3
ROUTE_CHECKPOINT_MAX = 25

# Banco corto: por debajo de este número de ítems la puerta adapta su checkpoint
# (los bancos de niveles altos de grammar son muy pequeños, p. ej. C2 = 4 ítems)
# para que superar la ruta no exija "dominar 3 a la primera" un banco entero.
QUIZ_SHORT_BANK = 12
_QUIZ_SHORT_CHECKPOINT_FRACTION = 0.25

# Archivos de currículo por nivel (misma convención que `services.curriculum`).
def _level_files() -> dict[str, dict]:
    """Carga en caliente el JSON de cada nivel CEFR (una vez por proceso)."""
    files: dict[str, dict] = {}
    for level_id in ("a1", "a2", "b1", "b2", "c1", "c2"):
        path = CURRICULUM_DIR / f"{level_id}.json"
        with path.open(encoding="utf-8") as f:
            files[level_id] = json.load(f)
    return files


_LEVEL_CACHE: dict[str, dict] = {}


def _level_data(level: str) -> dict:
    """Datos crudos de un nivel CEFR (mayúscula) con caché por proceso."""
    key = level.lower()
    if key not in _LEVEL_CACHE:
        _LEVEL_CACHE.update(_level_files())
    return _LEVEL_CACHE.get(key, {})


@lru_cache(maxsize=4)
def quiz_checks(skill: str) -> tuple[dict, ...]:
    """Pool oficial de checks MC con `skill` de todo el currículo (A1-C2).

    Cada ítem es `{check_id, level, topic, prompt, options, correct_index}` donde
    `check_id` es el id del check (único en el currículo) y `topic` es el módulo
    del currículo que lo contiene (agrupación temática para la puerta y la UI).
    """
    checks: list[dict] = []
    for level in LEVEL_ORDER:
        data = _level_data(level)
        for module in data.get("modules", []):
            module_title = module.get("title", "")
            for unit in module.get("units", []):
                for lesson in unit.get("lessons", []):
                    for objective in lesson.get("objectives", []):
                        for check in objective.get("checks", []):
                            if check.get("skill") != skill:
                                continue
                            checks.append(
                                {
                                    "check_id": check.get("id", ""),
                                    "level": level,
                                    "topic": module_title,
                                    "prompt": check.get("prompt", ""),
                                    "options": list(check.get("options", [])),
                                    "correct_index": int(check.get("correct_index", -1)),
                                }
                            )
    return tuple(checks)


def checks_for_level(skill: str, level: str) -> list[dict]:
    """Checks del banco oficial de un nivel CEFR (solo skill pedida)."""
    return [c for c in quiz_checks(skill) if c.get("level") == level]


def topics_for_level(skill: str, level: str) -> tuple[str, ...]:
    """Temas presentes en el banco oficial de un nivel."""
    return tuple(
        sorted(
            {c.get("topic") for c in checks_for_level(skill, level) if c.get("topic")}
        )
    )


def get_check(skill: str, check_id: str) -> dict | None:
    """Devuelve un check del banco oficial por id (None si no existe)."""
    for c in quiz_checks(skill):
        if c.get("check_id") == check_id:
            return c
    return None


def route_items(skill: str, level: str) -> list[dict]:
    """Pool de checks de una ruta (el banco oficial de ese nivel)."""
    return checks_for_level(skill, level)


def is_short_bank(total: int) -> bool:
    """True si un banco de `total` ítems se considera corto (puerta adaptada)."""
    return 0 < total < QUIZ_SHORT_BANK


def _accuracy(rows: list[dict]) -> float | None:
    """Precisión (0..100) como % de intentos superados sobre los del nivel."""
    if not rows:
        return None
    passed = sum(1 for r in rows if r.get("passed"))
    return round(passed / len(rows) * 100, 1)


def level_items(skill: str, level: str, attempts_rows: list[dict]) -> list[dict]:
    """Estado por check del banco de un nivel CEFR (puro).

    Para cada check de la ruta devuelve `{check_id, level, topic, prompt,
    attempts, state}` donde `state` es:
    - "unseen": nunca respondido;
    - "failed": respondido alguna vez pero nunca acertado;
    - "mastered": acertado al menos una vez.

    El estado se deriva en vivo de la tabla de intentos (sin migración).
    """
    pool = route_items(skill, level)
    seen: set[str] = set()
    passed: set[str] = set()
    counts: dict[str, int] = {}
    for row in attempts_rows:
        qid = row.get("check_id")
        if not qid:
            continue
        seen.add(qid)
        counts[qid] = counts.get(qid, 0) + 1
        if row.get("passed"):
            passed.add(qid)
    items = []
    for c in pool:
        qid = c["check_id"]
        if qid in passed:
            state = "mastered"
        elif qid in seen:
            state = "failed"
        else:
            state = "unseen"
        items.append(
            {
                "check_id": qid,
                "level": level,
                "topic": c.get("topic", ""),
                "prompt": c.get("prompt", ""),
                "attempts": counts.get(qid, 0),
                "state": state,
            }
        )
    return items


def _checkpoint_pass_ids(attempts_rows: list[dict]) -> set[str]:
    """Checks cuyo checkpoint está superado (primera exposición acertada).

    La primera fila registrada de cada `check_id` es su primera vez: si esa fila
    tiene `passed`, el check cuenta para el checkpoint de la ruta.
    """
    passed: set[str] = set()
    seen: set[str] = set()
    for row in attempts_rows:
        qid = row.get("check_id")
        if not qid or qid in seen:
            continue
        seen.add(qid)
        if row.get("passed"):
            passed.add(qid)
    return passed


def _checkpoint_required(total: int) -> int:
    """Checks del banco oficial exigidos en el checkpoint (adaptado a bancos cortos).

    En bancos normales exige el mínimo calibrado (3) o la fracción del banco, la
    que sea mayor, acotado al total. En bancos cortos (< QUIZ_SHORT_BANK) exige
    una cuarta parte redondeada (mínimo 1), para no pedir a un banco de 4 ítems
    "3 superados a la primera" como si fuera un banco de 20.
    """
    if total <= 0:
        return 0
    if is_short_bank(total):
        return min(total, max(1, round(total * _QUIZ_SHORT_CHECKPOINT_FRACTION)))
    target = round(total * ROUTE_CHECKPOINT_FRACTION)
    return min(total, max(ROUTE_CHECKPOINT_MIN, min(ROUTE_CHECKPOINT_MAX, target)))


def route_gate(skill: str, level: str, attempts_rows: list[dict]) -> dict:
    """Estado de la puerta de ruta quiz de un nivel (puro).

    Igual semántica que el resto de rutas: cobertura del banco oficial dominada,
    precisión global de los intentos del banco oficial y un checkpoint de primeros
    checks acertados. `blockers` vacío ⇒ `passed`. En bancos cortos la puerta se
    adapta (checkpoint menor) y se expone `short_bank` para la nota honesta.
    """
    official = route_items(skill, level)
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
            "short_bank": False,
        }
    official_ids = {c["check_id"] for c in official}
    level_rows = [row for row in attempts_rows if row.get("check_id") in official_ids]
    passed_ids = {row["check_id"] for row in level_rows if row.get("passed")}
    mastered = len(passed_ids)
    coverage_pct = round(mastered / total * 100, 1)
    coverage_required_pct = round(ROUTE_MIN_COVERAGE * 100)

    accuracy = _accuracy(level_rows)
    mastered_checks = [c for c in official if c["check_id"] in passed_ids]
    bank_topics = {c.get("topic") for c in official if c.get("topic")}
    topics = len({c.get("topic") for c in mastered_checks if c.get("topic")})
    topics_required = min(ROUTE_MIN_TOPICS, len(bank_topics))

    checkpoint = len(_checkpoint_pass_ids(level_rows))
    checkpoint_required = _checkpoint_required(total)

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
        "short_bank": is_short_bank(total),
    }


def level_status(skill: str, attempts_rows: list[dict]) -> list[dict]:
    """Progreso por ruta de nivel CEFR con puerta de ruta.

    Cada entrada es `{level, total, mastered, coverage_pct, accuracy, completed,
    gate}` (listado en orden CEFR). `mastered`/`coverage_pct` miden práctica sobre
    el banco oficial; `completed` refleja la puerta (`gate["passed"]`).
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
        for gate in [route_gate(skill, level, attempts_rows)]
    ]


def current_level(skill: str, passed_check_ids: set[str]) -> str:
    """Nivel CEFR cuyo contenido se está practicando (routing por cobertura).

    Primer nivel cuyo banco oficial aún no está dominado por completo; si todos
    lo están, devuelve el último para poder seguir practicando.
    """
    for level in LEVEL_ORDER:
        official = checks_for_level(skill, level)
        if not official:
            continue
        mastered = sum(1 for c in official if c["check_id"] in passed_check_ids)
        if mastered < len(official):
            return level
    return LEVEL_ORDER[-1]


def review_next_question(
    skill: str,
    level: str,
    attempts_rows: list[dict],
    *,
    only_failed: bool = False,
    only_mastered: bool = False,
) -> dict:
    """Siguiente check del banco de una ruta para practicar (rotación LRU).

    Devuelve el check del banco cuyo último intento registrado es más antiguo (o
    cualquier check aún no respondido). Con `only_failed=True` restringe a los
    respondidos pero nunca acertados (estado "failed"); con `only_mastered=True`,
    a los acertados alguna vez (repasar lo aprendido). Si no queda ninguno del
    grupo, `ValueError` ("vocabulary.no_failed").
    """
    pool = route_items(skill, level)
    if not pool:
        raise ValueError(f"nivel sin checks en el banco: {level}")
    candidates: list[dict]
    if only_failed or only_mastered:
        wanted = "failed" if only_failed else "mastered"
        keep = {
            item["check_id"]
            for item in level_items(skill, level, attempts_rows)
            if item["state"] == wanted
        }
        candidates = [c for c in pool if c["check_id"] in keep]
        if not candidates:
            raise ValueError("vocabulary.no_failed")
    else:
        candidates = pool
    candidate_ids = {c["check_id"] for c in candidates}
    last_index: dict[str, int] = {}
    for i, row in enumerate(attempts_rows):
        qid = row.get("check_id")
        if qid in candidate_ids:
            last_index[qid] = i
    # Nunca intentados primero; entre los demás, el de intento más antiguo (LRU).
    ordered = sorted(
        candidates,
        key=lambda c: (c["check_id"] in last_index, last_index.get(c["check_id"], -1)),
    )
    return ordered[0]


def route_competence(skill: str, attempt_rows: list[dict]) -> list[dict]:
    """Competencia quiz por ruta de nivel CEFR (honesta).

    Para cada ruta devuelve `{level, state, gate}` con `state`:
    - `not_started` → sin intentos en la ruta.
    - `developing` → hay práctica pero la puerta de ruta aún no se supera.
    - `functional` → ruta superada (`route_gate` pasa).

    La ruta NUNCA devuelve `demonstrated`: demostrar el nivel exige evidencia
    formal (exámenes/escalera del curso), no práctica.
    """
    result: list[dict] = []
    for level in LEVEL_ORDER:
        official_ids = {c["check_id"] for c in checks_for_level(skill, level)}
        level_rows = [r for r in attempt_rows if r.get("check_id") in official_ids]
        gate = route_gate(skill, level, attempt_rows)
        if not level_rows:
            state = "not_started"
        elif gate["passed"]:
            state = "functional"
        else:
            state = "developing"
        result.append({"level": level, "state": state, "gate": gate})
    return result
