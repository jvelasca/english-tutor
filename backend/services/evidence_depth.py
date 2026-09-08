"""Profundidad de la evidencia de una destreza en un nivel (V3.13, §6.4).

Clasifica la evidencia formal acumulada de una destreza en un nivel CEFR en
bandas de profundidad (low / medium / high), comparando las muestras reales
(`academy_evidence`, kinds familiar/transfer/novel/delayed) con los mínimos de
`curriculum/cefr_matrix.json`:

    LOW    → muestras < `minimum_evidence` del nivel (o ninguna)
    MEDIUM → muestras ≥ `minimum_evidence`, sin retención retardada
    HIGH   → muestras ≥ `minimum_evidence` con retención retardada (≥ 1 `delayed`)

`meets_matrix` indica además si la muestra satisface los requisitos de
transferencia que la matriz exige desde B1 (los mismos que aplica
`services.adaptive.readiness`); el kind `novel` quedó reservado sin emisor y la
matriz exige `novel_required = 0` desde V3.24 (F-K1, dossier K).

Regla R7 (Constitución §6.4): la profundidad describe la evidencia FORMAL de la
destreza, nunca la práctica de una ruta; una ruta con banco corto solo puede
leerse como "practice coverage · evidence depth LOW". Este módulo es puro y
determinista; no toca la base de datos.
"""
from __future__ import annotations

from services.cefr_matrix import requirements_for

# Orden creciente de las bandas de profundidad.
DEPTH_ORDER: tuple[str, ...] = ("low", "medium", "high")

# Tipos de ítem que exigen PRODUCCIÓN (no solo reconocimiento). Se usa para
# distinguir la evidencia de reconocimiento (mcq) de la de producción en el
# Student Model (R5: Recognition ≠ Production). `controlled_production` lo
# emiten los ítems de producción controlada de Grammar (V3.13).
PRODUCTION_ITEM_TYPES: tuple[str, ...] = (
    "speaking",
    "writing",
    "pronunciation",
    "controlled_production",
)

# Fallback plano si la destreza no tiene fila en la matriz (p. ej. pronunciation
# es componente de Speaking y conserva su mínimo histórico de readiness).
FALLBACK_MINIMUM_EVIDENCE = 3

_KINDS: tuple[str, ...] = ("familiar", "transfer", "novel", "delayed")


def minimum_evidence_for(skill: str, level: str) -> int:
    """Muestras mínimas que la matriz CEFR exige a una destreza en un nivel.

    Las destrezas sin fila en la matriz (p. ej. `pronunciation`) usan el
    fallback plano histórico (`READINESS_MIN_EVIDENCE`).
    """
    req = requirements_for(level, skill)
    return req.minimum_evidence if req is not None else FALLBACK_MINIMUM_EVIDENCE


def _by_kind_counts(evidence_by_kind: dict | None) -> dict[str, int]:
    counts = {kind: 0 for kind in _KINDS}
    for kind, n in (evidence_by_kind or {}).items():
        if kind in counts:
            counts[kind] = int(n or 0)
    return counts


def evidence_depth_report(
    skill: str,
    level: str,
    samples: int,
    evidence_by_kind: dict | None = None,
    *,
    production_count: int = 0,
) -> dict:
    """Reporte de profundidad de la evidencia de una destreza en un nivel.

    Devuelve `{skill, level, samples, minimum_evidence, delayed,
    production_count, depth, meets_matrix}`:

    - `samples` son las muestras de `academy_evidence` de la destreza en el
      nivel; `delayed` las de kind `delayed` (retención retardada estable ≥ 7
      días, que solo se escriben tras el retention reassessment).
    - `depth` ∈ {low, medium, high} según la tabla de la Constitución §6.4.
    - `meets_matrix` es cierto cuando la muestra satisface la cantidad mínima Y
      los requisitos de transferencia de la matriz (a partir de B1).
    """
    samples = int(samples or 0)
    counts = _by_kind_counts(evidence_by_kind)
    min_evidence = minimum_evidence_for(skill, level)
    req = requirements_for(level, skill)
    transfer_required = req.transfer_required if req is not None else 0
    novel_required = req.novel_required if req is not None else 0
    delayed = counts["delayed"]

    if samples < min_evidence:
        depth = "low"
    elif delayed >= 1:
        depth = "high"
    else:
        depth = "medium"

    meets_matrix = bool(
        samples >= min_evidence
        and counts["transfer"] >= transfer_required
        and counts["novel"] >= novel_required
    )

    return {
        "skill": skill,
        "level": level,
        "samples": samples,
        "minimum_evidence": min_evidence,
        "delayed": delayed,
        "production_count": int(production_count or 0),
        "depth": depth,
        "meets_matrix": meets_matrix,
    }


def evidence_depth(
    skill: str,
    level: str,
    samples: int,
    evidence_by_kind: dict | None = None,
) -> str:
    """Banda de profundidad de la evidencia de una destreza en un nivel."""
    return evidence_depth_report(skill, level, samples, evidence_by_kind)["depth"]
