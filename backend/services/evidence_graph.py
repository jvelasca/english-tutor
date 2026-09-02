"""Evidence Graph (V2.12) — can-do → dimensiones → limiting factor → mastery.

Conecta el currículo (objetivos can-do) con la evidencia del alumno para
exponer, por competencia:

    CAN-DO
      ├── vocabulary / grammar / discourse / listening / speaking / interaction
      └── transfer (y novel/delayed como cobertura de evidencia)
             ↓
          limiting factor → recomendación

Y alimenta el Adaptive Engine con un "Why this activity?" estructurado:

    Because:
    1. Your B1 interaction mastery is 61%.
    2. Your vocabulary is already 88%.
    3. Transfer evidence is missing.
    4. This activity directly targets transfer.

Puro y determinista: sin FastAPI ni BD.
"""

from __future__ import annotations

from services.curriculum import Level, Objective

GRAPH_VERSION = "2.12.0"

# Dimensiones canónicas del grafo (auditoría V2.12).
GRAPH_DIMENSIONS: tuple[str, ...] = (
    "vocabulary",
    "grammar",
    "discourse",
    "listening",
    "speaking",
    "interaction",
    "transfer",
)

DISCOURSE_SUBSKILLS: frozenset[str] = frozenset(
    {"coherence", "discourse_markers", "collocations", "fluency"}
)
INTERACTION_SUBSKILLS: frozenset[str] = frozenset(
    {"interaction", "turn_taking", "repair"}
)

# Fase de actividad preferida cuando el limiting factor es X.
FOCUS_PHASE: dict[str, str] = {
    "vocabulary": "practice",
    "grammar": "practice",
    "discourse": "speak",
    "listening": "listen",
    "speaking": "speak",
    "interaction": "interact",
    "transfer": "transfer",
}


def _pct(score: float) -> int:
    return int(round(max(0.0, min(1.0, score)) * 100))


def _human(label: str) -> str:
    return label.replace("_", " ")


def _skill_score(
    objective_id: str,
    skill: str,
    objective_scores: dict[str, dict[str, float]],
    profile_by_skill: dict[str, dict],
) -> float:
    """Score de una destreza para el objetivo (mastery local o perfil)."""
    local = objective_scores.get(objective_id, {}).get(skill)
    if local is not None:
        return round(float(local), 3)
    entry = profile_by_skill.get(skill)
    if entry is not None:
        return round(float(entry.get("score") or 0.0), 3)
    return 0.0


def _evidence_kind_score(
    objective_id: str,
    kind: str,
    evidence_rows: list[dict],
) -> tuple[float, int]:
    """Media de `result` para un evidence_kind del objetivo (0 si no hay)."""
    rows = [
        r
        for r in evidence_rows
        if r.get("objective_id") == objective_id
        and (r.get("evidence_kind") or "familiar") == kind
        and isinstance(r.get("result"), (int, float))
    ]
    if not rows:
        # Fallback: evidencia de nivel (sin objective_id) del mismo kind.
        rows = [
            r
            for r in evidence_rows
            if not r.get("objective_id")
            and (r.get("evidence_kind") or "familiar") == kind
            and isinstance(r.get("result"), (int, float))
        ]
    if not rows:
        return 0.0, 0
    mean = sum(float(r["result"]) for r in rows) / len(rows)
    return round(mean, 3), len(rows)


def _declared_dimensions(objective: Objective) -> list[str]:
    """Dimensiones relevantes para este can-do (orden canónico)."""
    skills = set(objective.skills)
    sub = set(objective.subskills or [])
    declared: list[str] = []
    for dim in GRAPH_DIMENSIONS:
        if dim == "discourse":
            if sub & DISCOURSE_SUBSKILLS or "speaking" in skills:
                # Discourse solo si hay subskills de discurso o speaking declarado.
                if sub & DISCOURSE_SUBSKILLS:
                    declared.append(dim)
            continue
        if dim == "interaction":
            if sub & INTERACTION_SUBSKILLS or "interaction" in skills:
                declared.append(dim)
            continue
        if dim == "transfer":
            declared.append(dim)
            continue
        if dim in skills:
            declared.append(dim)
    # Siempre incluir transfer al final si aún no (ya está en el loop).
    if "transfer" not in declared:
        declared.append("transfer")
    return declared


def dimension_scores(
    objective: Objective,
    *,
    objective_scores: dict[str, dict[str, float]],
    profile: list[dict],
    evidence_rows: list[dict],
) -> list[dict]:
    """Lista de dimensiones `{id, kind, score, evidence_count, missing}`."""
    by_skill = {e.get("skill"): e for e in profile}
    dims: list[dict] = []
    for dim in _declared_dimensions(objective):
        if dim == "transfer":
            score, count = _evidence_kind_score(
                objective.id, "transfer", evidence_rows
            )
            # Si no hay transfer, mirar novel como cobertura parcial (0.5 peso).
            if count == 0:
                novel_score, novel_n = _evidence_kind_score(
                    objective.id, "novel", evidence_rows
                )
                if novel_n > 0:
                    score, count = round(0.5 * novel_score, 3), novel_n
            dims.append(
                {
                    "id": dim,
                    "kind": "evidence",
                    "score": score,
                    "evidence_count": count,
                    "missing": count == 0,
                }
            )
            continue

        if dim == "discourse":
            # Proxy: speaking mastery del objetivo (o perfil).
            score = _skill_score(
                objective.id, "speaking", objective_scores, by_skill
            )
            entry = by_skill.get("speaking") or {}
            dims.append(
                {
                    "id": dim,
                    "kind": "subskill",
                    "score": score,
                    "evidence_count": int(entry.get("evidence_count") or 0),
                    "missing": False,
                }
            )
            continue

        if dim == "interaction":
            score = _skill_score(
                objective.id, "speaking", objective_scores, by_skill
            )
            # Preferir skill interaction del perfil si existe.
            if "interaction" in by_skill:
                score = round(float(by_skill["interaction"].get("score") or 0.0), 3)
            inter_entry = by_skill.get("interaction") or by_skill.get("speaking") or {}
            dims.append(
                {
                    "id": dim,
                    "kind": "subskill",
                    "score": score,
                    "evidence_count": int(inter_entry.get("evidence_count") or 0),
                    "missing": False,
                }
            )
            continue

        score = _skill_score(objective.id, dim, objective_scores, by_skill)
        entry = by_skill.get(dim) or {}
        dims.append(
            {
                "id": dim,
                "kind": "skill",
                "score": score,
                "evidence_count": int(entry.get("evidence_count") or 0),
                "missing": False,
            }
        )
    return dims


def limiting_factor(dimensions: list[dict]) -> dict | None:
    """Dimensión más débil (score ascendente; missing primero)."""
    if not dimensions:
        return None
    ordered = sorted(
        dimensions,
        key=lambda d: (0 if d.get("missing") else 1, float(d.get("score") or 0.0)),
    )
    weak = ordered[0]
    return {
        "id": weak["id"],
        "score": float(weak.get("score") or 0.0),
        "missing": bool(weak.get("missing")),
        "kind": weak.get("kind") or "skill",
    }


def mastery_from_dimensions(dimensions: list[dict]) -> float:
    if not dimensions:
        return 0.0
    return round(
        sum(float(d.get("score") or 0.0) for d in dimensions) / len(dimensions), 3
    )


def recommended_focus(limit: dict | None) -> dict:
    if limit is None:
        return {"dimension": None, "phase": "practice", "reason": "no-dimensions"}
    dim = limit["id"]
    return {
        "dimension": dim,
        "phase": FOCUS_PHASE.get(dim, "practice"),
        "reason": "missing-evidence" if limit.get("missing") else "weak-dimension",
    }


def objective_node(
    objective: Objective,
    *,
    level_id: str,
    level_label: str,
    objective_scores: dict[str, dict[str, float]],
    profile: list[dict],
    evidence_rows: list[dict],
) -> dict:
    """Nodo del grafo para un can-do."""
    dimensions = dimension_scores(
        objective,
        objective_scores=objective_scores,
        profile=profile,
        evidence_rows=evidence_rows,
    )
    limit = limiting_factor(dimensions)
    focus = recommended_focus(limit)
    return {
        "objective_id": objective.id,
        "can_do": objective.can_do,
        "title": objective.title,
        "level_id": level_id,
        "level": level_label,
        "dimensions": dimensions,
        "limiting_factor": limit,
        "mastery": mastery_from_dimensions(dimensions),
        "recommended_focus": focus,
        "graph_version": GRAPH_VERSION,
    }


def explain_because(
    node: dict,
    *,
    activity_focus: str | None = None,
    max_strong: int = 2,
) -> list[str]:
    """Viñetas 'Because:' del Adaptive Engine explicable."""
    level = node.get("level") or node.get("level_id") or ""
    dims = {d["id"]: d for d in node.get("dimensions") or []}
    limit = node.get("limiting_factor")
    bullets: list[str] = []

    if limit is not None:
        name = _human(limit["id"])
        if limit.get("missing"):
            bullets.append(
                f"{name.capitalize()} evidence is missing for this can-do."
            )
        else:
            bullets.append(
                f"Your {level} {name} mastery is {_pct(limit['score'])}%."
            )

    # Destrezas ya sólidas (contraste).
    strong = sorted(
        (
            d
            for d in (node.get("dimensions") or [])
            if d["id"] != (limit or {}).get("id")
            and not d.get("missing")
            and float(d.get("score") or 0.0) >= 0.8
        ),
        key=lambda d: float(d.get("score") or 0.0),
        reverse=True,
    )
    for d in strong[:max_strong]:
        bullets.append(
            f"Your {_human(d['id'])} is already {_pct(float(d['score']))}%."
        )

    # Cobertura transfer explícita si no es el limiting.
    transfer = dims.get("transfer")
    if (
        transfer
        and transfer.get("missing")
        and (limit or {}).get("id") != "transfer"
    ):
        bullets.append("Transfer evidence is missing.")

    focus = activity_focus or (node.get("recommended_focus") or {}).get("dimension")
    if focus:
        bullets.append(
            f"This activity directly targets {_human(focus)}."
        )
    elif limit is not None:
        bullets.append(
            f"This activity directly targets {_human(limit['id'])}."
        )

    return bullets


def build_level_graph(
    level: Level,
    *,
    objective_scores: dict[str, dict[str, float]],
    profile: list[dict],
    evidence_rows: list[dict],
    mastered_ids: set[str] | None = None,
) -> dict:
    """Grafo completo del nivel: un nodo por objetivo + agregados."""
    mastered_ids = mastered_ids or set()
    nodes = [
        objective_node(
            obj,
            level_id=level.level_id,
            level_label=level.level,
            objective_scores=objective_scores,
            profile=profile,
            evidence_rows=evidence_rows,
        )
        for obj in level.objectives()
    ]
    # Limiting factors más frecuentes entre objetivos no dominados.
    tallies: dict[str, int] = {}
    for node in nodes:
        if node["objective_id"] in mastered_ids:
            continue
        limit = node.get("limiting_factor")
        if limit:
            tallies[limit["id"]] = tallies.get(limit["id"], 0) + 1
    top_limiting = None
    if tallies:

        def _tally_key(k: str) -> tuple[int, int]:
            order = (
                GRAPH_DIMENSIONS.index(k) if k in GRAPH_DIMENSIONS else 99
            )
            return (tallies[k], -order)

        top_id = max(tallies, key=_tally_key)
        top_limiting = {"id": top_id, "count": tallies[top_id]}

    open_nodes = [n for n in nodes if n["objective_id"] not in mastered_ids]
    avg_mastery = (
        round(sum(n["mastery"] for n in open_nodes) / len(open_nodes), 3)
        if open_nodes
        else 1.0
    )
    return {
        "level_id": level.level_id,
        "level": level.level,
        "nodes": nodes,
        "open_count": len(open_nodes),
        "mastered_count": len(nodes) - len(open_nodes),
        "average_mastery": avg_mastery,
        "top_limiting_factor": top_limiting,
        "graph_version": GRAPH_VERSION,
    }


def enrich_next_best(
    activity: dict,
    node: dict | None,
) -> dict:
    """Añade because[] + limiting_factor al payload de next-best."""
    out = dict(activity)
    if node is None:
        out.setdefault("because", [])
        out.setdefault("limiting_factor", None)
        out.setdefault("graph_mastery", None)
        return out
    focus = activity.get("skill") or (node.get("recommended_focus") or {}).get(
        "dimension"
    )
    # Si el paso apunta a transfer phase vía kind, priorizar transfer.
    if activity.get("kind") in ("new", "weakness") and (
        node.get("limiting_factor") or {}
    ).get("id") == "transfer":
        focus = "transfer"
    out["because"] = explain_because(node, activity_focus=focus)
    out["limiting_factor"] = node.get("limiting_factor")
    out["graph_mastery"] = node.get("mastery")
    out["can_do"] = node.get("can_do")
    return out
