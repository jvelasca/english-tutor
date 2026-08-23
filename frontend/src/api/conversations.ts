import { deleteJson, getJson, postJson, putJson } from "./client";
import type { Conversation, ConversationMeta, Message } from "../types/api";

export function createConversation(): Promise<ConversationMeta> {
  return postJson<ConversationMeta>("/api/conversations", {});
}

export function listConversations(): Promise<ConversationMeta[]> {
  return getJson<ConversationMeta[]>("/api/conversations");
}

export function getConversation(id: string): Promise<Conversation> {
  return getJson<Conversation>(`/api/conversations/${id}`);
}

export function saveConversation(
  id: string,
  title: string,
  messages: Message[],
): Promise<ConversationMeta> {
  return putJson<ConversationMeta>(`/api/conversations/${id}`, {
    title,
    messages,
  });
}

export function deleteConversation(id: string): Promise<{ ok: boolean }> {
  return deleteJson<{ ok: boolean }>(`/api/conversations/${id}`);
}
