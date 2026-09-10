import { getJson, postJson } from "./client";
import type { LearningEvent, LearningProfile, ReviewQueue } from "../types/api";

export function getProfile(userId: string): Promise<LearningProfile> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<LearningProfile>(`/api/profile?${query}`);
}

export function getEvents(userId: string): Promise<LearningEvent[]> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<LearningEvent[]>(`/api/learning/events?${query}`);
}

export async function analyzeText(text: string, userId: string): Promise<void> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  await Promise.all([
    postJson<unknown>(`/api/vocabulary/analyze?${query}`, { text }),
    postJson<unknown>(`/api/grammar/analyze?${query}`, { text }),
  ]);
}

/** Cola de repaso léxico (V3.35, P1-2): cartas FSRS vencidas con la actividad
 * recomendada por hueco de competencia. Sustituye la inyección de FSRS dentro
 * del speaking micro-drill. Señal, nunca puerta. */
export function getReviewQueue(
  userId: string,
  limit = 20,
): Promise<ReviewQueue> {
  const query = new URLSearchParams({
    user_id: userId,
    limit: String(limit),
  }).toString();
  return getJson<ReviewQueue>(`/api/learning/review?${query}`);
}
