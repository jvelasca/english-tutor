import { getJson, postJson, withTimeout } from "./client";
import type {
  VocabularyAttempt,
  VocabularyLevelItems,
  VocabularyQuestion,
  VocabularyStats,
} from "../types/api";

// Timeouts de red del bucle MC (misma filosofía que listening/speaking): el
// backend es local, pero en iPad por WiFi una petición puede tardar o caerse.
const TIMEOUT_SUBMIT_MS = 20000;
const TIMEOUT_QUESTION_MS = 15000;
const TIMEOUT_READ_MS = 10000;

export type VocabularyQuestionMode = "all" | "failed" | "mastered";

export function getVocabularyQuestion(
  userId: string,
  level?: string | null,
  mode?: VocabularyQuestionMode,
): Promise<VocabularyQuestion> {
  const params = new URLSearchParams({ user_id: userId });
  if (level) params.set("level", level);
  if (mode && mode !== "all") params.set("mode", mode);
  return withTimeout(
    getJson<VocabularyQuestion>(
      `/api/vocabulary/routes/question?${params.toString()}`,
    ),
    TIMEOUT_QUESTION_MS,
    "vocabulary question",
  );
}

export function getVocabularyLevelItems(
  userId: string,
  level: string,
): Promise<VocabularyLevelItems> {
  const params = new URLSearchParams({ user_id: userId, level });
  return getJson<VocabularyLevelItems>(
    `/api/vocabulary/routes/items?${params.toString()}`,
  );
}

export function getVocabularyStats(userId: string): Promise<VocabularyStats> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return withTimeout(
    getJson<VocabularyStats>(`/api/vocabulary/routes/stats?${query}`),
    TIMEOUT_READ_MS,
    "vocabulary stats",
  );
}

/**
 * Envía la opción elegida de un check MC.
 *
 * El backend puntúa al instante (determinista, sin LLM): acierto si
 * `selected_index` coincide con la respuesta del currículo, y en la respuesta
 * se revela la correcta para el feedback.
 */
export function submitVocabularyAttempt(
  userId: string,
  checkId: string,
  selectedIndex: number,
): Promise<VocabularyAttempt> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return withTimeout(
    postJson<VocabularyAttempt>(
      `/api/vocabulary/routes/attempt?${query}`,
      { check_id: checkId, selected_index: selectedIndex },
    ),
    TIMEOUT_SUBMIT_MS,
    "submit vocabulary attempt",
  );
}
