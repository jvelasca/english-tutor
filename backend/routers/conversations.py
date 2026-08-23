"""Endpoints CRUD de conversaciones."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from schemas.conversations import Conversation, ConversationMeta, ConversationUpsert
from services import store

router = APIRouter()


@router.post("/api/conversations", response_model=ConversationMeta)
async def create(user_id: str) -> dict:
    conv = store.create_conversation(user_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return conv


@router.get("/api/conversations", response_model=list[ConversationMeta])
async def list_all(user_id: str) -> list[dict]:
    return store.list_conversations(user_id)


@router.get("/api/conversations/{cid}", response_model=Conversation)
async def get_one(cid: str) -> dict:
    conv = store.get_conversation(cid)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return conv


@router.put("/api/conversations/{cid}", response_model=ConversationMeta)
async def save(cid: str, body: ConversationUpsert) -> dict:
    conv = store.save_conversation(
        cid, body.title, [m.model_dump() for m in body.messages]
    )
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return conv


@router.delete("/api/conversations/{cid}")
async def delete(cid: str) -> dict:
    if not store.delete_conversation(cid):
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return {"ok": True}
