"""Endpoints CRUD de conversaciones."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from dependencies import current_user
from schemas.conversations import Conversation, ConversationMeta, ConversationUpsert
from services import store_async

router = APIRouter()


@router.post("/api/conversations", response_model=ConversationMeta)
async def create(user_id: str) -> dict:
    conv = await store_async.create_conversation(user_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return conv


@router.get("/api/conversations", response_model=list[ConversationMeta])
async def list_all(user_id: str) -> list[dict]:
    return await store_async.list_conversations(user_id)


@router.get("/api/conversations/{cid}", response_model=Conversation)
async def get_one(cid: str, user: dict = Depends(current_user)) -> dict:
    conv = await store_async.get_conversation(cid, user["id"])
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return conv


@router.put("/api/conversations/{cid}", response_model=ConversationMeta)
async def save(
    cid: str, body: ConversationUpsert, user: dict = Depends(current_user)
) -> dict:
    conv = await store_async.save_conversation(
        cid, user["id"], body.title, [m.model_dump() for m in body.messages]
    )
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return conv


@router.delete("/api/conversations/{cid}")
async def delete(cid: str, user: dict = Depends(current_user)) -> dict:
    if not await store_async.delete_conversation(cid, user["id"]):
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return {"ok": True}
