import { deleteJson, getJson, postJson, putJson } from "./client";
import type { Conversation, ConversationMeta, Message } from "../types/api";

export function createConversation(userId: string): Promise<ConversationMeta> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return postJson<ConversationMeta>(`/api/conversations?${query}`, {});
}

export function listConversations(userId: string): Promise<ConversationMeta[]> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<ConversationMeta[]>(`/api/conversations?${query}`);
}

export function getConversation(id: string, userId: string): Promise<Conversation> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<Conversation>(`/api/conversations/${id}?${query}`);
}

export function saveConversation(
  id: string,
  userId: string,
  title: string,
  messages: Message[],
): Promise<ConversationMeta> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return putJson<ConversationMeta>(`/api/conversations/${id}?${query}`, {
    title,
    messages,
  });
}

export function deleteConversation(id: string, userId: string): Promise<{ ok: boolean }> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return deleteJson<{ ok: boolean }>(`/api/conversations/${id}?${query}`);
}
