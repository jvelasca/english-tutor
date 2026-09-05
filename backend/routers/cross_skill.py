"""Endpoint de solo lectura del registro cross-skill (V3.13 P1.2 → v3.14 A1–C2).

Devuelve la matriz por estructura gramatical del nivel solicitado (qué
instrumentos ofrece el currículo por destreza y qué evidencia real tiene el
usuario en cada canal). No escribe nada: leer evidencia no cambia el Student
Model.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from dependencies import current_user
from repositories import academy as academy_repo
from repositories import grammar_routes as grammar_repo
from schemas.cross_skill import CrossSkillMatrixOut
from services.cross_skill import CROSS_SKILL_LEVELS, cross_skill_matrix

router = APIRouter()


@router.get("/api/cross-skill", response_model=CrossSkillMatrixOut)
async def get_cross_skill_matrix(
    level: str = "b1",
    user: dict = Depends(current_user),
) -> dict:
    level = (level or "").strip().lower()
    if level not in CROSS_SKILL_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"cross_skill.level_unknown ({', '.join(CROSS_SKILL_LEVELS)})",
        )
    evidence = academy_repo.list_evidence(user["id"], level_id=level)
    attempts = grammar_repo.list_attempts(user["id"])
    passed = {
        a["check_id"]
        for a in attempts
        if bool(a.get("passed")) and a.get("level") == level
    }
    return cross_skill_matrix(
        level,
        evidence_rows=evidence,
        production_passed_ids=passed,
    )
