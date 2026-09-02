"""Speaking Mission Performance (V2.9).

Loop: Mission → Attempt → Evaluation → Drill → Retry → Improvement.

Motor puro y determinista. Recibe puntuaciones por criterio (ya calculadas por el
scorer de speaking) y produce evaluación, drills dirigidos y la mejora visible
entre el primer intento y el retry. El LLM no puntúa: solo (si acaso) extrae
evidencia antes de llegar aquí.
"""
from __future__ import annotations

from services.speaking import SPEAKING_CRITERIA

# Umbral bajo el cual un criterio entra en el drill dirigido (alineado con
# SPEAKING_WEAK_THRESHOLD del diagnóstico longitudinal).
MISSION_WEAK_THRESHOLD = 0.6

# Nº máximo de drills sugeridos tras un intento (sesión corta y accionable).
MISSION_DRILL_CAP = 2

# Fases canónicas del loop de rendimiento (auditoría V2.9).
MISSION_PHASES: tuple[str, ...] = (
    "mission",
    "attempt",
    "evaluation",
    "drill",
    "retry",
    "improvement",
)

# Instrucciones de micro-práctica por criterio débil. Contenido estático: el
# frontend las muestra tal cual; no hay generación LLM.
CRITERION_DRILLS: dict[str, dict[str, str]] = {
    "task_achievement": {
        "title": "Hit the communicative goal",
        "instruction": (
            "Say the goal in one clear sentence, then add one supporting detail."
        ),
        "prompt": "State what you want to achieve, then give one reason.",
    },
    "grammatical_control": {
        "title": "Clean grammar under pressure",
        "instruction": (
            "Repeat the same idea twice: first carefully, then at natural speed."
        ),
        "prompt": "Describe your plan for tomorrow in two correct sentences.",
    },
    "lexical_resource": {
        "title": "Upgrade your wording",
        "instruction": "Replace three basic words with more precise alternatives.",
        "prompt": "Retell the same message using more precise vocabulary.",
    },
    "fluency": {
        "title": "Keep the flow",
        "instruction": (
            "Speak for 20 seconds without stopping; use fillers if you need time."
        ),
        "prompt": "Talk continuously about your day for about 20 seconds.",
    },
    "pronunciation": {
        "title": "Clear key words",
        "instruction": (
            "Slow down and stress the content words; then speak at normal speed."
        ),
        "prompt": "Say three key words carefully, then put them in one sentence.",
    },
    "coherence": {
        "title": "Link your ideas",
        "instruction": "Use first / then / finally to organise a short answer.",
        "prompt": "Explain a small sequence using first, then and finally.",
    },
    "interaction": {
        "title": "Respond and take turns",
        "instruction": "Answer a question, then ask one back to keep the turn going.",
        "prompt": "Answer briefly, then ask a follow-up question.",
    },
}


def mission_from_scenario(scenario: dict) -> dict:
    """Construye la carga útil de una misión a partir de un escenario del catálogo."""
    return {
        "scenario_id": scenario["id"],
        "title": scenario.get("title") or scenario["id"],
        "prompt": scenario.get("prompt") or "",
        "communicative_objective": scenario.get("communicative_objective") or "",
        "cefr_target": scenario.get("cefr_target") or "B1",
        "task_type": scenario.get("task_type") or "role_play",
        "metrics": list(scenario.get("metrics") or []),
        "difficulty": scenario.get("difficulty"),
        "difficulty_vector": dict(scenario.get("difficulty_vector") or {}),
    }


def _criterion_scores(criteria: dict) -> dict[str, float | None]:
    """Normaliza a los 7 criterios canónicos (faltantes → None)."""
    return {c: criteria.get(c) for c in SPEAKING_CRITERIA}


def weak_criteria(
    criteria: dict,
    *,
    threshold: float = MISSION_WEAK_THRESHOLD,
) -> list[str]:
    """Criterios observados por debajo del umbral, en orden de la rúbrica."""
    scores = _criterion_scores(criteria)
    return [
        name
        for name in SPEAKING_CRITERIA
        if scores[name] is not None and scores[name] < threshold
    ]


def evaluate_attempt(
    *,
    overall: float | None,
    criteria: dict,
    observed: dict | None = None,
) -> dict:
    """Evalúa un intento: overall, criterios, lista débil y recomendación.

    Determinista. `observed` es opcional; si falta, se infiere de scores no-None.
    """
    scores = _criterion_scores(criteria)
    if observed is None:
        observed_map = {c: scores[c] is not None for c in SPEAKING_CRITERIA}
    else:
        observed_map = {c: bool(observed.get(c, False)) for c in SPEAKING_CRITERIA}
    weak = weak_criteria(scores)
    if weak:
        recommendation = f"Practice {weak[0].replace('_', ' ')} before retrying."
    elif overall is not None and overall >= MISSION_WEAK_THRESHOLD:
        recommendation = "Solid attempt. Retry to lock in the improvement."
    else:
        recommendation = "Retry the mission focusing on the communicative goal."
    return {
        "overall": overall,
        "criteria": scores,
        "observed": observed_map,
        "weak": weak,
        "recommendation": recommendation,
        "phase": "evaluation",
    }


def targeted_drills(
    weak: list[str],
    *,
    cap: int = MISSION_DRILL_CAP,
) -> list[dict]:
    """Micro-prácticas dirigidas a los criterios débiles (máx. `cap`)."""
    drills: list[dict] = []
    for name in weak:
        if len(drills) >= cap:
            break
        template = CRITERION_DRILLS.get(name)
        if template is None:
            continue
        drills.append(
            {
                "criterion": name,
                "title": template["title"],
                "instruction": template["instruction"],
                "prompt": template["prompt"],
            }
        )
    return drills


def improvement(first: dict, retry: dict) -> dict:
    """Delta visible entre el primer intento y el retry (overall + por criterio).

    `first`/`retry` son evaluaciones (`evaluate_attempt`) o dicts con
    `overall` + `criteria`. Criterios no observados en cualquiera de los dos
    quedan fuera del desglose. `improved` es True si el overall sube.
    """
    first_overall = first.get("overall")
    retry_overall = retry.get("overall")
    delta = None
    if first_overall is not None and retry_overall is not None:
        delta = round(retry_overall - first_overall, 3)

    by_criterion: list[dict] = []
    first_scores = _criterion_scores(first.get("criteria") or {})
    retry_scores = _criterion_scores(retry.get("criteria") or {})
    for name in SPEAKING_CRITERIA:
        a = first_scores[name]
        b = retry_scores[name]
        if a is None or b is None:
            continue
        by_criterion.append(
            {
                "criterion": name,
                "before": a,
                "after": b,
                "delta": round(b - a, 3),
            }
        )

    improved = bool(delta is not None and delta > 0)
    return {
        "before_overall": first_overall,
        "after_overall": retry_overall,
        "delta": delta,
        "improved": improved,
        "by_criterion": by_criterion,
        "phase": "improvement",
    }


def next_phase(status: str) -> str | None:
    """Siguiente fase del loop, o None si ya terminó."""
    try:
        idx = MISSION_PHASES.index(status)
    except ValueError:
        return None
    if idx + 1 >= len(MISSION_PHASES):
        return None
    return MISSION_PHASES[idx + 1]
