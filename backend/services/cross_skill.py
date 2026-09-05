"""Registro cross-skill por estructura (V3.13 P1.2 → v3.14: escalado A1–C2).

Para cada estructura gramatical del nivel (un `Objective` del currículo con
checks MC de grammar) cruza las EVIDENCIAS del mismo usuario a través de las
destrezas que el currículo ofrece para esa estructura:

    recognition  → checks MC de grammar del objetivo (academy_evidence)
    production   → ítems `controlled_production` del nivel enlazados al objetivo
                   (grammar_route_attempts aprobados, corrección determinista)
    listening    → ítems/checks de listening del objetivo (academy_evidence)
    speaking     → evidencia de speaking del objetivo (academy_evidence)
    transfer     → evidencia con kinds transfer/novel/delayed del objetivo

El registro distingue el INSTRUMENTO que el currículo ofrece (`offered`) de la
EVIDENCIA real del usuario (`evidence`, muestras correctas). Un ✗ con
instrumento no es fracaso: significa "instrumento disponible, aún sin evidencia
en esta destreza" (p. ej. se reconoce la estructura en MC pero no se ha
evidenciado al hablar). Un "–" (ofrecido = False) significa que el currículo no
expone esa estructura a esa destreza.

El registro es SOLO LECTURA y cubre los seis niveles A1–C2. El binding de los
ítems `controlled_production` a su estructura gramatical es normativo (los
tests verifican que cada id existe en el currículo y que su objetivo tiene
checks MC de grammar). Este módulo es puro y determinista.
"""
from __future__ import annotations

from collections import defaultdict

from services.curriculum import load_level

# Destrezas (canales) de la matriz, en orden de lectura.
CHANNELS: tuple[str, ...] = (
    "recognition",
    "production",
    "listening",
    "speaking",
    "transfer",
)

# Niveles con registro cross-skill (A1–C2).
CROSS_SKILL_LEVELS: tuple[str, ...] = ("a1", "a2", "b1", "b2", "c1", "c2")

# Enlace producción controlada → estructura por nivel. Un ítem CP del nivel se
# atribuye al objetivo gramatical que ejercita. Es normativo: los tests
# verifican que cada id existe en el currículo, que su objetivo tiene checks MC
# de grammar y que no quedan CP huérfanos.
A1_PRODUCTION_BINDINGS: dict[str, str] = {
    "a1-cp-01": "a1-m01-u01-l01-o01",  # verb to be
    "a1-cp-02": "a1-m02-u01-l01-o01",  # present simple (3rd person)
    "a1-cp-03": "a1-m02-u01-l01-o03",  # adverbs of frequency
    "a1-cp-04": "a1-m03-u01-l01-o01",  # have got / has got
    "a1-cp-05": "a1-m04-u01-l01-o02",  # prepositions of place
    "a1-cp-06": "a1-m08-u01-l01-o02",  # past simple
}

A2_PRODUCTION_BINDINGS: dict[str, str] = {
    "a2-cp-01": "a2-m01-u01-l01-o01",  # past simple
    "a2-cp-02": "a2-m01-u01-l01-o02",  # present perfect
    "a2-cp-03": "a2-m02-u01-l01-o01",  # comparatives
    "a2-cp-04": "a2-m02-u01-l01-o02",  # superlatives
    "a2-cp-05": "a2-m03-u01-l01-o01",  # be going to
    "a2-cp-06": "a2-m04-u01-l01-o02",  # have to / must
}

B1_PRODUCTION_BINDINGS: dict[str, str] = {
    "b1-cp-01": "b1-m01-u01-l01-o01",  # present perfect for experience
    "b1-cp-02": "b1-m01-u01-l01-o02",  # yet / already
    "b1-cp-03": "b1-m02-u01-l01-o05",  # will / going to
    "b1-cp-04": "b1-m02-u01-l01-o06",  # first conditional
    "b1-cp-05": "b1-m02-u01-l02-o07",  # have to / must
    "b1-cp-06": "b1-m03-u01-l01-o15",  # reported speech
}

B2_PRODUCTION_BINDINGS: dict[str, str] = {
    "b2-cp-01": "b2-m01-u01-l01-o01",  # discourse markers
    "b2-cp-02": "b2-m01-u01-l01-o02",  # linkers of consequence
    "b2-cp-03": "b2-m01-u01-l02-o03",  # second conditional
    "b2-cp-04": "b2-m01-u01-l02-o03",  # third conditional
    "b2-cp-05": "b2-m01-u01-l02-o04",  # reported speech
    "b2-cp-06": "b2-m02-u01-l02-o11",  # modals of deduction
}

C1_PRODUCTION_BINDINGS: dict[str, str] = {
    "c1-cp-01": "c1-m01-u01-l01-o01",  # inversion for emphasis
    "c1-cp-02": "c1-m01-u01-l01-o02",  # cleft sentences
    "c1-cp-03": "c1-m01-u01-l01-o04",  # inversion in discussion
    "c1-cp-04": "c1-m02-u01-l02-o01",  # collocations
    "c1-cp-05": "c1-m03-u01-l01-o04",  # passive (formal writing)
    "c1-cp-06": "c1-m03-u01-l01-o04",  # passive (formal writing)
}

C2_PRODUCTION_BINDINGS: dict[str, str] = {
    "c2-cp-01": "c2-m01-u01-l01-o04",  # inversion for rhetorical effect
    "c2-cp-02": "c2-m01-u01-l01-o04",  # cleft sentences
    "c2-cp-03": "c2-m03-u01-l01-o01",  # mixed conditional (precision)
    "c2-cp-04": "c2-m02-u01-l01-o01",  # passive (formal register)
}

# Binding por nivel.
PRODUCTION_BINDINGS_BY_LEVEL: dict[str, dict[str, str]] = {
    "a1": A1_PRODUCTION_BINDINGS,
    "a2": A2_PRODUCTION_BINDINGS,
    "b1": B1_PRODUCTION_BINDINGS,
    "b2": B2_PRODUCTION_BINDINGS,
    "c1": C1_PRODUCTION_BINDINGS,
    "c2": C2_PRODUCTION_BINDINGS,
}

# Kinds de evidencia que cuentan como TRANSFERENCIA en la matriz (superan la
# práctica familiar: uso en contexto nuevo/retardado).
_TRANSFER_KINDS: tuple[str, ...] = ("transfer", "novel", "delayed")


def _production_bindings_for(level_id: str) -> dict[str, str]:
    """Binding CP → estructura del nivel (vacío si el nivel no está cableado)."""
    return dict(PRODUCTION_BINDINGS_BY_LEVEL.get(level_id, {}))


def structure_registry(level_id: str) -> list[dict]:
    """Estructuras del nivel con su oferta de instrumentos por canal.

    Cada estructura es un objetivo con checks MC de grammar: es el ancla del
    currículo que ya agrupa can-dos, concepts, `scenario_ids` (speaking) y
    `listening_items` (V2.5-C4).
    """
    if level_id not in CROSS_SKILL_LEVELS:
        return []
    level = load_level(level_id)
    bindings = _production_bindings_for(level_id)
    cp_ids = {c.id for c in level.production_checks}
    cp_by_objective: dict[str, list[str]] = defaultdict(list)
    for cp_id, obj_id in bindings.items():
        if cp_id in cp_ids:
            cp_by_objective[obj_id].append(cp_id)

    rows: list[dict] = []
    for obj in level.objectives():
        if not any(c.skill == "grammar" for c in obj.checks):
            continue
        channels = {
            "recognition": {"offered": True, "evidence": 0},
            "production": {
                "offered": bool(cp_by_objective.get(obj.id)),
                "evidence": 0,
            },
            "listening": {
                "offered": bool(obj.listening_items),
                "evidence": 0,
            },
            "speaking": {
                "offered": bool(obj.scenario_ids),
                "evidence": 0,
            },
            "transfer": {"offered": True, "evidence": 0},
        }
        rows.append(
            {
                "structure_id": obj.id,
                "name": " · ".join(obj.concepts) if obj.concepts else obj.title,
                "can_do": obj.can_do,
                "channels": channels,
            }
        )
    rows.sort(key=lambda r: r["structure_id"])
    return rows


def _correct(evidence_rows: list[dict]) -> int:
    """Muestras correctas (result > 0). Un intento fallido (0.0) no es evidencia."""
    return sum(1 for r in evidence_rows if float(r.get("result") or 0.0) > 0.0)


def cross_skill_matrix(
    level_id: str,
    evidence_rows: list[dict] | None = None,
    production_passed_ids: set[str] | None = None,
) -> dict:
    """Matriz cross-skill del usuario en `level_id`.

    `evidence_rows` son las filas de `academy_evidence` del nivel (keys:
    `objective_id`, `skill`, `item_type`, `evidence_kind`, `result`).
    `production_passed_ids` son los ids de `production_checks` superados en las
    rutas de grammar (check_id de `grammar_route_attempts` con passed = 1).
    """
    rows = structure_registry(level_id)
    if not rows:
        return {"level_id": level_id, "level": level_id.upper(), "structures": []}

    evidence_by_objective: dict[str, list[dict]] = defaultdict(list)
    for row in evidence_rows or []:
        if row.get("objective_id"):
            evidence_by_objective[row["objective_id"]].append(row)
    passed = set(production_passed_ids or ())
    bindings = _production_bindings_for(level_id)
    cp_by_objective: dict[str, list[str]] = defaultdict(list)
    for cp_id, obj_id in bindings.items():
        cp_by_objective[obj_id].append(cp_id)

    for structure in rows:
        obj_id = structure["structure_id"]
        items = evidence_by_objective.get(obj_id, [])
        channels = structure["channels"]
        for skill, ch_name in (
            ("grammar", "recognition"),
            ("listening", "listening"),
            ("speaking", "speaking"),
        ):
            ch = channels[ch_name]
            if ch["offered"]:
                ch["evidence"] = _correct(
                    [r for r in items if r.get("skill") == skill]
                )
        prod_ids = [cid for cid in cp_by_objective.get(obj_id, []) if cid in passed]
        channels["production"]["evidence"] = len(prod_ids)
        transfer = [r for r in items if r.get("evidence_kind") in _TRANSFER_KINDS]
        channels["transfer"]["evidence"] = _correct(transfer)

    return {
        "level_id": level_id,
        "level": level_id.upper(),
        "structures": rows,
    }
