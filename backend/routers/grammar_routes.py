"""Endpoints de las rutas de grammar (V3.12).

Práctica MC determinista por nivel CEFR sobre los checks de grammar del
currículo: siguiente pregunta (nueva/failed/mastered), estado del nivel, intentos
(elegir opción ⇒ feedback inmediato) y progreso del mapa. La ruta es un hito de
práctica con techo `functional`; demostrar el nivel exige los exámenes/escalera
formales del curso, nunca esta ruta.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from dependencies import current_user
from domain import grammar_routes as grammar_routes_service
from domain import learning as learning_service
from domain.grammar_routes import is_valid_level
from schemas.grammar_routes import (
    GrammarAttemptRequest,
    GrammarAttemptResponse,
    GrammarLevelItemsOut,
    GrammarQuestion,
    GrammarStats,
)

router = APIRouter()

VALID_MODES = ("all", "failed", "mastered")


@router.get("/api/grammar/routes/question", response_model=GrammarQuestion)
async def question(
    level: str | None = None,
    mode: str = "all",
    user: dict = Depends(current_user),
) -> dict:
    if level is not None and not is_valid_level(level):
        raise HTTPException(status_code=400, detail=f"Nivel no válido: {level}")
    if mode not in VALID_MODES:
        raise HTTPException(status_code=400, detail=f"Modo no válido: {mode}")
    try:
        return await grammar_routes_service.next_question(
            user["id"], level=level, mode=mode
        )
    except ValueError as exc:
        if str(exc) == "grammar.no_failed":
            raise HTTPException(
                status_code=404, detail="grammar.no_failed"
            ) from None
        raise


@router.get("/api/grammar/routes/items", response_model=GrammarLevelItemsOut)
async def level_items(
    level: str,
    user: dict = Depends(current_user),
) -> dict:
    if not is_valid_level(level):
        raise HTTPException(status_code=400, detail=f"Nivel no válido: {level}")
    return await grammar_routes_service.items_for_level_out(user["id"], level)


@router.get("/api/grammar/routes/stats", response_model=GrammarStats)
async def stats(user: dict = Depends(current_user)) -> dict:
    return await grammar_routes_service.get_stats(user["id"])


@router.post(
    "/api/grammar/routes/attempt",
    response_model=GrammarAttemptResponse,
)
async def attempt(
    body: GrammarAttemptRequest,
    user: dict = Depends(current_user),
) -> dict:
    """Evalúa la opción elegida de un check (determinista) y persiste el intento.

    La evaluación es instantánea y sin LLM: acierto si `selected_index` coincide
    con la respuesta del currículo. Tras responder se revela la respuesta
    correcta para el feedback.
    """
    try:
        result = await grammar_routes_service.submit_attempt(
            user["id"], body.check_id, body.selected_index
        )
    except ValueError as exc:
        if str(exc) == "grammar.bad_option":
            raise HTTPException(
                status_code=400,
                detail="grammar.bad_option",
            ) from None
        raise
    if result is None:
        raise HTTPException(status_code=404, detail="Check no encontrado")
    await learning_service.record_event(
        user["id"],
        "exercise",
        f"grammar:{body.check_id}:{'ok' if result['passed'] else 'ko'}",
    )
    return result
