"""Validador de contenido del ESPACIO de instancias del banco de transferencia.

V3.61 — parte determinista del P1-02 de la auditoría `S` de V3.60: el motor sabía
**representar** la dificultad de una superficie (`difficulty_delta`) pero no
**validar** que la representación fuera coherente con el contenido declarado. Este
módulo recorre el banco y comprueba, de forma pura y determinista (sin LLM:
premisa 21), los invariantes que hasta ahora solo se sostenían «por suerte del
banco»:

- el espacio está ENTRE el mínimo anti-memorización y el techo por familia;
- ninguna consigna deja llaves sin resolver y los slugs de una familia son únicos;
- todo `difficulty_delta` usa dimensiones canónicas, es entero, cabe en ±2 y
  **justifica** su carga (`scenario`/`goal`) — declarar carga sin explicarla era
  el hueco de V3.60;
- `register` de instancia o BIEN no se declara o BIEN coincide con el de la
  familia (formaliza la tensión P3-01: la familia es la identidad);
- `skill_delta` solo añade competencias del vocabulario `CONTEXT_SKILLS`;
- con una unidad objetivo declarada, la familia conserva **alguna** superficie
  servible (si no, el guard anti-spoiler la dejaría sin tarea: callejón sin
  salida).

Además emite AVISOS **heurísticos** (nunca gate) de perfil de demanda: dos
superficies con la misma carga efectiva que piden competencias muy distintas son
una señal de equivalencia pedagógica dudosa. El aviso se declara como heurístico
porque **sin WSD real** (P2-05) el sistema no puede demostrar equivalencia
semántica: este validador cierra el P1-02 SOLO en su parte determinista.
"""

from __future__ import annotations

import re
from typing import Mapping

from services import difficulty, transfer

# ---------------------------------------------------------------------------
# Perfil de demanda (ADVISORY, heurístico): marcadores léxicos de la competencia
# que la consigna parece exigir. No entra en ninguna decisión ni en el ledger.
# ---------------------------------------------------------------------------
_ARGUMENT_MARKERS = (
    "because",
    "although",
    "however",
    "therefore",
    "whereas",
    "despite",
    "unless",
    "furthermore",
    "moreover",
    "contrast",
    "compare",
)
_OPINION_MARKERS = (
    "think",
    "believe",
    "opinion",
    "agree",
    "disagree",
    "prefer",
    "argue",
    "defend",
    "justify",
    "recommend",
)
_NARRATIVE_MARKERS = (
    "yesterday",
    "last",
    "ago",
    "then",
    "after",
    "before",
    "happened",
    "remember",
    "story",
    "describe",
)
_IMPERATIVE_MARKERS = (
    "ask",
    "explain",
    "describe",
    "tell",
    "give",
    "write",
    "prepare",
    "make",
    "negotiate",
    "present",
    "answer",
)

_WORD = re.compile(r"[a-z']+")


def _integer_load(value: object) -> int | None:
    """Delta ENTERO de una dimensión (None si no describe un paso de carga).

    Espejo del criterio de `services.difficulty` (rechaza `bool`, fracciones,
    NaN y texto) para poder auditar la declaración CRUDA, antes del recorte que
    `normalize_delta` aplica en silencio. Nunca lanza.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    return int(value)


def demand_profile(text: object) -> dict:
    """Perfil de DEMANDA heurístico de una consigna (V3.61, advisory, pura).

    Cuenta marcadores de argumentación, opinión, narración e instrucción, más la
    complejidad oracional aproximada (comas y conectores). Devuelve un `score`
    entero 1..5 que NO es una dificultad: es una señal de comparación para avisar
    cuando dos superficies de la misma carga efectiva piden cosas muy distintas.
    `heuristic=True` lo declara explícitamente. Nunca lanza.
    """
    normalized = " ".join(str(text or "").strip().lower().split())
    tokens = set(_WORD.findall(normalized))
    clauses = 1 + normalized.count(",") + normalized.count(" and ")
    signals = {
        "argumentation": len(tokens.intersection(_ARGUMENT_MARKERS)),
        "opinion": len(tokens.intersection(_OPINION_MARKERS)),
        "narrative": len(tokens.intersection(_NARRATIVE_MARKERS)),
        "imperative": len(tokens.intersection(_IMPERATIVE_MARKERS)),
    }
    total = sum(min(count, 2) for count in signals.values())
    if clauses >= 3:
        total += 1
    return {
        "score": int(max(1, min(5, 1 + total))),
        "signals": signals,
        "clauses": clauses,
        "heuristic": True,
    }


def _raw_surfaces(attributes: Mapping) -> list[tuple[str, Mapping]]:
    """Declaraciones CRUDAS de superficie de una familia (V3.61, pura).

    Devuelve `(etiqueta, declaración)` de las `instances` de V3.59 y de cada
    valor de slot declarado como dict. Se auditan CRUDAS (antes del recorte y del
    descarte silencioso de `normalize_delta`/`_skill_delta`) para que la
    violación se vea donde está declarada. Nunca lanza.
    """
    found: list[tuple[str, Mapping]] = []
    declared = attributes.get("instances")
    if isinstance(declared, (list, tuple)):
        for position, raw in enumerate(declared):
            if isinstance(raw, Mapping):
                found.append((f"instances[{position}]", raw))
    spec = attributes.get("instance_space")
    if isinstance(spec, Mapping):
        slots = spec.get("slots")
        if isinstance(slots, Mapping):
            for name, values in slots.items():
                if isinstance(values, str) or not isinstance(values, (list, tuple)):
                    continue
                for position, raw in enumerate(values):
                    if isinstance(raw, Mapping):
                        found.append((f"slots[{name}][{position}]", raw))
    return found


def _check_raw_metadata(
    raw: Mapping, attributes: Mapping, label: str, add
) -> None:
    """Invariantes de una declaración CRUDA de superficie (V3.61, pura)."""
    family_register = str(attributes.get("register") or "").strip().lower()
    declared_register = str(raw.get("register") or "").strip().lower()
    if declared_register and family_register and declared_register != family_register:
        add(
            "register_mismatch",
            "error",
            f"{label}: register {declared_register!r} != familia "
            f"{family_register!r}",
        )
    delta = raw.get("difficulty_delta")
    if isinstance(delta, Mapping):
        vector = transfer.context_difficulty(attributes)
        justified = bool(str(raw.get("scenario") or "").strip()) or bool(
            str(raw.get("goal") or "").strip()
        )
        for dimension, declared in delta.items():
            name = str(dimension or "").strip().lower()
            if name not in difficulty.DIFFICULTY_DIMENSIONS:
                add(
                    "delta_unknown_dimension",
                    "error",
                    f"{label}: dimensión {dimension!r} fuera del vocabulario",
                )
                continue
            load = _integer_load(declared)
            if load is None:
                add(
                    "delta_not_integer",
                    "error",
                    f"{label}: {name}={declared!r} no es un paso entero",
                )
                continue
            if abs(load) > 2:
                add(
                    "delta_out_of_range",
                    "error",
                    f"{label}: {name}={load} fuera del rango ±2",
                )
                continue
            if not load:
                continue
            if name not in vector:
                add(
                    "delta_unknown_dimension",
                    "error",
                    f"{label}: {name} no la declara la familia {sorted(vector)}",
                )
            elif not justified:
                add(
                    "delta_without_justification",
                    "error",
                    f"{label}: {name}={load} sin `scenario`/`goal` que lo "
                    "explique",
                )
    skills = raw.get("skill_delta")
    if skills is None:
        return
    if isinstance(skills, str) or not isinstance(
        skills, (list, tuple, set, frozenset)
    ):
        add(
            "skill_delta_invalid",
            "error",
            f"{label}: `skill_delta` no es una lista de competencias",
        )
        return
    unknown = sorted(
        {str(skill or "").strip().lower() for skill in skills}
        - set(transfer.CONTEXT_SKILLS)
    )
    if unknown:
        add(
            "skill_delta_unknown",
            "error",
            f"{label}: competencias fuera de CONTEXT_SKILLS {unknown}",
        )


def _report(
    family: str, surfaces: int, violations: list[dict], advisories: list[dict]
) -> dict:
    """Informe normalizado de una familia (V3.61, pura)."""
    return {
        "family": family,
        "surfaces": surfaces,
        "ok": not violations,
        "violations": violations,
        "advisories": advisories,
    }


def validate_instance_space(context: object, target: object = "") -> dict:
    """Informe determinista del espacio de una familia (V3.61, pura).

    Comprueba los invariantes de contenido y devuelve
    `{family, surfaces, ok, violations, advisories}`; `violations` es el gate
    (severidad `error`) y `advisories` son avisos heurísticos. Con `target`
    (unidad objetivo) añade la garantía de que la familia conserva alguna
    superficie servible tras el guard anti-spoiler. Nunca lanza.
    """
    attributes = transfer.context_attributes(context)
    family = transfer.context_id_for(attributes) if attributes else ""
    violations: list[dict] = []
    advisories: list[dict] = []

    def add(code: str, severity: str, detail: str, surface: str = "") -> None:
        entry = {
            "code": code,
            "severity": severity,
            "family": family,
            "surface": surface,
            "detail": detail,
        }
        (violations if severity == "error" else advisories).append(entry)

    if not attributes:
        add("unknown_family", "error", "familia no reconocible")
        return _report(family, 0, violations, advisories)

    details = transfer.context_instance_details(attributes)
    safe = transfer.available_instance_details(attributes, target)

    if len(details) < transfer.CONTEXT_INSTANCE_SPACE_MIN:
        add(
            "below_min",
            "error",
            f"{len(details)} superficies < CONTEXT_INSTANCE_SPACE_MIN "
            f"({transfer.CONTEXT_INSTANCE_SPACE_MIN})",
        )
    if len(details) > transfer.CONTEXT_INSTANCE_SPACE_MAX:
        add(
            "above_max",
            "error",
            f"{len(details)} superficies > CONTEXT_INSTANCE_SPACE_MAX "
            f"({transfer.CONTEXT_INSTANCE_SPACE_MAX})",
        )

    slugs: dict[str, list[str]] = {}
    for position, detail in enumerate(details):
        prompt = str(detail["prompt"] or "")
        if "{" in prompt or "}" in prompt:
            add(
                "unresolved_placeholder",
                "error",
                f"consigna con llaves sin resolver: {prompt!r}",
                str(detail["instance"]),
            )
        # La superficie 0 es la consigna HISTÓRICA (V3.58) y por diseño no tiene
        # slug: no es una superficie declarada, es la degradación exacta.
        if position == 0 and not str(detail["instance"] or ""):
            continue
        slugs.setdefault(str(detail["instance"]), []).append(prompt)
    for slug, prompts in slugs.items():
        if not slug:
            add("missing_instance_slug", "error", "superficie sin slug")
        elif len(prompts) > 1:
            add(
                "duplicate_instance_slug",
                "error",
                f"{len(prompts)} consignas distintas comparten el slug {slug!r}",
                slug,
            )

    for label, raw in _raw_surfaces(attributes):
        _check_raw_metadata(raw, attributes, label, add)

    spec = attributes.get("instance_space")
    if not isinstance(spec, Mapping):
        add("no_instance_space", "error", "la familia no declara `instance_space`")
    else:
        declared_slots = set(spec.get("slots") or {})
        normalized = transfer.context_instance_spec(attributes)
        if not normalized:
            add(
                "unusable_spec",
                "error",
                "el `instance_space` no es utilizable (plantilla, placeholders "
                "o slots inservibles): la familia no genera superficies",
            )
        else:
            unused = sorted(declared_slots - set(normalized["slots"]))
            if unused:
                add(
                    "unused_slots",
                    "warning",
                    f"slots declarados que la plantilla no interpola: {unused}",
                )
            if normalized["difficulty_delta"] and not any(
                isinstance(raw, Mapping)
                and (raw.get("scenario") or raw.get("goal"))
                for _label, raw in _raw_surfaces(attributes)
            ):
                add(
                    "base_delta_without_justification",
                    "warning",
                    "el delta base del espacio no se explica con ningún "
                    "`scenario`/`goal` de slot",
                )

    if target and not safe:
        add(
            "no_safe_surface",
            "error",
            f"ninguna superficie es servible para la unidad {target!r}: el guard "
            "anti-spoiler dejaría la familia sin tarea",
        )
    elif target and len(safe) < len(details):
        advisories.append(
            {
                "code": "guarded_surfaces",
                "severity": "warning",
                "family": family,
                "surface": "",
                "detail": f"{len(details) - len(safe)} superficies nombran la "
                f"unidad {target!r} y no se sirven",
            }
        )

    # Aviso HEURÍSTICO de equivalencia: misma carga efectiva, demanda dispar.
    by_effective: dict[tuple, list[tuple[str, int]]] = {}
    for index, detail in enumerate(details):
        vector = transfer.context_instance_difficulty(
            attributes, index, target=target
        )
        key = tuple(sorted(vector.items()))
        by_effective.setdefault(key, []).append(
            (str(detail["instance"]), demand_profile(detail["prompt"])["score"])
        )
    for key, entries in by_effective.items():
        if len(entries) < 2:
            continue
        scores = [score for _slug, score in entries]
        if max(scores) - min(scores) >= 2:
            advisories.append(
                {
                    "code": "demand_spread",
                    "severity": "warning",
                    "family": family,
                    "surface": entries[0][0],
                    "detail": "misma carga efectiva "
                    f"{dict(key)} con demanda heurística {min(scores)}.."
                    f"{max(scores)} (advisory, sin WSD)",
                }
            )
    return _report(family, len(details), violations, advisories)


def validate_bank(contexts: object = None, target: object = "") -> dict:
    """Informe determinista del banco COMPLETO de transferencia (V3.61, pura).

    Devuelve `{families, surfaces, ok, errors, warnings, reports}`. `ok` es
    `False` si CUALQUIER familia tiene una violación (el gate del CLI de CI).
    Nunca lanza.
    """
    families = (
        list(contexts)
        if contexts is not None
        else list(transfer.TRANSFER_CONTEXTS)
    )
    reports = [validate_instance_space(context, target) for context in families]
    errors = [entry for report in reports for entry in report["violations"]]
    warnings = [entry for report in reports for entry in report["advisories"]]
    return {
        "families": len(reports),
        "surfaces": sum(report["surfaces"] for report in reports),
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "reports": reports,
    }
