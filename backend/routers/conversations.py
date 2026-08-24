"""Endpoints CRUD de conversaciones."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from dependencies import current_user
from domain import conversations as conversation_service
from domain import learning as learning_service
from schemas.conversations import Conversation, ConversationMeta, ConversationUpsert

router = APIRouter()


@router.post("/api/conversations", response_model=ConversationMeta)
async def create(user: dict = Depends(current_user)) -> dict:
    user_id = user["id"]
    conv = await conversation_service.create_conversation(user_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    await learning_service.record_event(user_id, "conversation", conv["id"])
    return conv


@router.get("/api/conversations", response_model=list[ConversationMeta])
async def list_all(user: dict = Depends(current_user)) -> list[dict]:
    return await conversation_service.list_conversations(user["id"])


@router.get("/api/conversations/{cid}", response_model=Conversation)
async def get_one(cid: str, user: dict = Depends(current_user)) -> dict:
    conv = await conversation_service.get_conversation(cid, user["id"])
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return conv


@router.put("/api/conversations/{cid}", response_model=ConversationMeta)
async def save(
    cid: str, body: ConversationUpsert, user: dict = Depends(current_user)
) -> dict:
    conv = await conversation_service.save_conversation(
        cid, user["id"], body.title, [m.model_dump() for m in body.messages]
    )
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return conv


@router.delete("/api/conversations/{cid}")
async def delete(cid: str, user: dict = Depends(current_user)) -> dict:
    if not await conversation_service.delete_conversation(cid, user["id"]):
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return {"ok": True}
