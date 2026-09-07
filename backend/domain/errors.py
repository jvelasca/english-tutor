"""Excepciones del dominio de la Academy (frontera de integridad de evidencia)."""

from __future__ import annotations


class EvidenceInvariantError(Exception):
    """Una o varias evidencias violan invariantes y no se persisten.

    Se lanza desde `domain.academy._record_evidence_validated` antes de escribir
    en la base de datos. Lleva las violaciones para que el handler las exponga de
    forma estructurada y queden visibles en logs.
    """

    def __init__(
        self, user_id: str, level_id: str, violations: list[str]
    ) -> None:
        self.user_id = user_id
        self.level_id = level_id
        self.violations = violations
        super().__init__(
            f"Evidencia inválida para user={user_id!r} level={level_id!r}: "
            + "; ".join(violations)
        )


class RetentionNotDueError(Exception):
    """La retención (R6) no es debida: no ha pasado la ventana mínima ni se
    cumple el ratio de estabilidad. Se mapea a HTTP 409 (conflicto de estado).
    """

    def __init__(self, user_id: str, level_id: str, reason: str) -> None:
        self.user_id = user_id
        self.level_id = level_id
        self.reason = reason
        super().__init__(
            f"Retención no debida user={user_id!r} level={level_id!r}: {reason}"
        )


class ObjectiveLockedError(Exception):
    """El objetivo evaluado está locked (GATE-01): no puede evaluarse ni
    completarse. Se mapea a HTTP 409 (conflicto de estado).
    """

    def __init__(self, user_id: str, objective_id: str) -> None:
        self.user_id = user_id
        self.objective_id = objective_id
        super().__init__(
            f"Objetivo locked user={user_id!r} objective={objective_id!r}"
        )
