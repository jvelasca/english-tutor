import { getJson, postJson, withTimeout } from "./client";
import type {
  ConversationAttempt,
  ConversationDialogue,
  ConversationLevelItems,
  ConversationStats,
} from "../types/api";

// Timeouts de red de las rutas de conversación guiada: la evaluación del
// transcripto corre el pipeline LLM local sobre toda la conversación, así que
// puede tardar más que una tarjeta de speaking.
const TIMEOUT_SUBMIT_MS = 180000;
const TIMEOUT_QUESTION_MS = 15000;
const TIMEOUT_READ_MS = 10000;

export type ConversationQuestionMode = "all" | "failed" | "mastered";

export function getConversationQuestion(
  _userId: string,
  level?: string | null,
  mode?: ConversationQuestionMode,
): Promise<ConversationDialogue> {
  const params = new URLSearchParams();
  if (level) params.set("level", level);
  if (mode && mode !== "all") params.set("mode", mode);
  const query = params.toString();
  return withTimeout(
    getJson<ConversationDialogue>(`/api/conversation/routes/question${query ? `?${query}` : ""}`),
    TIMEOUT_QUESTION_MS,
    "get conversation question",
  );
}

export function getConversationLevelItems(
  _userId: string,
  level: string,
): Promise<ConversationLevelItems> {
  const params = new URLSearchParams({ level });
  return getJson<ConversationLevelItems>(
    `/api/conversation/routes/items?${params.toString()}`,
  );
}

export function getConversationStats(_userId: string): Promise<ConversationStats> {
  return withTimeout(
    getJson<ConversationStats>("/api/conversation/routes/stats"),
    TIMEOUT_READ_MS,
    "conversation stats",
  );
}

/**
 * Entrega una conversación guiada terminada para evaluar su transcripto.
 *
 * El backend recupera los turnos persistidos de `conversationId`, extrae la
 * evidencia del transcripto del alumno con el LLM local y puntúa por criterios
 * (task_type conversation) fusionando la señal objetiva de interacción.
 */
export function submitConversationAttempt(
  _userId: string,
  dialogueId: string,
  conversationId: string,
): Promise<ConversationAttempt> {
  return withTimeout(
    postJson<ConversationAttempt>(
      "/api/conversation/routes/attempt",
      { dialogue_id: dialogueId, conversation_id: conversationId },
    ),
    TIMEOUT_SUBMIT_MS,
    "submit conversation",
  );
}
