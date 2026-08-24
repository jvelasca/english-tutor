import { getJson, postJson } from "./client";
import type { LearningProfile } from "../types/api";

export function getProfile(userId: string): Promise<LearningProfile> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<LearningProfile>(`/api/profile?${query}`);
}

export async function analyzeText(text: string, userId: string): Promise<void> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  await Promise.all([
    postJson<unknown>(`/api/vocabulary/analyze?${query}`, { text }),
    postJson<unknown>(`/api/grammar/analyze?${query}`, { text }),
  ]);
}
