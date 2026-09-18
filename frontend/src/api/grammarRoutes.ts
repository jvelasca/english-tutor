import { getJson, postJson, withTimeout } from "./client";
import type {
  GrammarAttempt,
  GrammarLevelItems,
  GrammarQuestion,
  GrammarStats,
} from "../types/api";

// Timeouts de red del bucle MC (misma filosofía que listening/speaking): el
// backend es local, pero en iPad por WiFi una petición puede tardar o caerse.
const TIMEOUT_SUBMIT_MS = 20000;
const TIMEOUT_QUESTION_MS = 15000;
const TIMEOUT_READ_MS = 10000;

export type GrammarQuestionMode = "all" | "failed" | "mastered";

export function getGrammarQuestion(
  _userId: string,
  level?: string | null,
  mode?: GrammarQuestionMode,
): Promise<GrammarQuestion> {
  const params = new URLSearchParams();
  if (level) params.set("level", level);
  if (mode && mode !== "all") params.set("mode", mode);
  const query = params.toString();
  return withTimeout(
    getJson<GrammarQuestion>(
      `/api/grammar/routes/question${query ? `?${query}` : ""}`,
    ),
    TIMEOUT_QUESTION_MS,
    "grammar question",
  );
}

export function getGrammarLevelItems(
  _userId: string,
  level: string,
): Promise<GrammarLevelItems> {
  const params = new URLSearchParams({ level });
  return getJson<GrammarLevelItems>(
    `/api/grammar/routes/items?${params.toString()}`,
  );
}

export function getGrammarStats(_userId: string): Promise<GrammarStats> {
  return withTimeout(
    getJson<GrammarStats>("/api/grammar/routes/stats"),
    TIMEOUT_READ_MS,
    "grammar stats",
  );
}

/**
 * Envía la respuesta de un ítem: la opción elegida (MC) o el texto escrito
 * (producción controlada, V3.13 P1).
 *
 * El backend puntúa al instante (determinista, sin LLM): MC acierta si
 * `selected_index` coincide con la respuesta del currículo; producción
 * controlada si `typed_answer` coincide por normalización con las respuestas
 * aceptadas. En la respuesta se revela la correcta para el feedback.
 */
export function submitGrammarAttempt(
  _userId: string,
  checkId: string,
  selectedIndex: number,
  typedAnswer?: string,
): Promise<GrammarAttempt> {
  return withTimeout(
    postJson<GrammarAttempt>(
      "/api/grammar/routes/attempt",
      typedAnswer
        ? {
            check_id: checkId,
            selected_index: selectedIndex,
            typed_answer: typedAnswer,
          }
        : { check_id: checkId, selected_index: selectedIndex },
    ),
    TIMEOUT_SUBMIT_MS,
    "submit grammar attempt",
  );
}
