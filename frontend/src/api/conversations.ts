import { deleteJson, getJson, postJson, putJson } from "./client";
import type { Conversation, ConversationMeta, Message } from "../types/api";

export function createConversation(_userId: string): Promise<ConversationMeta> {
  return postJson<ConversationMeta>("/api/conversations", {});
}

export function listConversations(_userId: string): Promise<ConversationMeta[]> {
  return getJson<ConversationMeta[]>("/api/conversations");
}

export function getConversation(id: string, _userId: string): Promise<Conversation> {
  return getJson<Conversation>(`/api/conversations/${id}`);
}

export function saveConversation(
  id: string,
  _userId: string,
  title: string,
  messages: Message[],
): Promise<ConversationMeta> {
  return putJson<ConversationMeta>(`/api/conversations/${id}`, {
    title,
    messages,
  });
}

export function deleteConversation(id: string, _userId: string): Promise<{ ok: boolean }> {
  return deleteJson<{ ok: boolean }>(`/api/conversations/${id}`);
}
