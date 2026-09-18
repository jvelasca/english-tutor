import { getJson, postJson } from "./client";
import type { LearningEvent, LearningProfile, ReviewQueue } from "../types/api";

export function getProfile(_userId: string): Promise<LearningProfile> {
  return getJson<LearningProfile>("/api/profile");
}

export function getEvents(_userId: string): Promise<LearningEvent[]> {
  return getJson<LearningEvent[]>("/api/learning/events");
}

export async function analyzeText(text: string, _userId: string): Promise<void> {
  await Promise.all([
    postJson<unknown>("/api/vocabulary/analyze", { text }),
    postJson<unknown>("/api/grammar/analyze", { text }),
  ]);
}

/** Cola de repaso léxico (V3.35, P1-2): cartas FSRS vencidas con la actividad
 * recomendada por hueco de competencia. Sustituye la inyección de FSRS dentro
 * del speaking micro-drill. Señal, nunca puerta. */
export function getReviewQueue(
  _userId: string,
  limit = 20,
): Promise<ReviewQueue> {
  const query = new URLSearchParams({
    limit: String(limit),
  }).toString();
  return getJson<ReviewQueue>(`/api/learning/review?${query}`);
}
