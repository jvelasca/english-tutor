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
