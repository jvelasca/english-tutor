import { deleteJson, getJson, postJson, withTimeout } from "./client";
import type {
  ListeningAnswerResponse,
  ListeningDiagnostic,
  ListeningExtrasJob,
  ListeningLevelItems,
  ListeningProductionResult,
  ListeningQuestion,
  ListeningRouteExtras,
  ListeningStats,
} from "../types/api";

// Timeouts de red del bucle de práctica: el backend es local, pero en iPad por
// WiFi (o con otra sesión abierta en el PC) una petición puede tardar o caerse a
// medias. Si una de estas llamadas no responde, falla con un error legible en vez
// de dejar la pantalla sin el botón "Continuar" (obligando a refrescar).
const TIMEOUT_SUBMIT_MS = 20000;
const TIMEOUT_QUESTION_MS = 15000;
const TIMEOUT_READ_MS = 10000;

export type ListeningQuestionMode = "all" | "failed" | "mastered";

export function getListeningQuestion(
  userId: string,
  level?: string | null,
  mode?: ListeningQuestionMode,
): Promise<ListeningQuestion> {
  const params = new URLSearchParams({ user_id: userId });
  // `level` entra en juego en el repaso de un nivel ya completado: el selector
  // rota por las frases del nivel en lugar de seguir al Student Model.
  if (level) params.set("level", level);
  // `mode="failed"` (drill) restringe el selector a las frases del nivel que se
  // han intentado pero nunca acertado. `mode="mastered"` (repasar lo aprendido)
  // lo restringe a las acertadas alguna vez. Solo se envían cuando se indica.
  if (mode && mode !== "all") params.set("mode", mode);
  return withTimeout(
    getJson<ListeningQuestion>(`/api/listening/question?${params.toString()}`),
    TIMEOUT_QUESTION_MS,
    "get question",
  );
}

export function getListeningLevelItems(
  userId: string,
  level: string,
): Promise<ListeningLevelItems> {
  const params = new URLSearchParams({ user_id: userId, level });
  return getJson<ListeningLevelItems>(`/api/listening/items?${params.toString()}`);
}

export function submitListeningAnswer(
  userId: string,
  questionId: string,
  answerIndex: number,
  responseTimeMs: number | null = null,
  replayCount = 0,
): Promise<ListeningAnswerResponse> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return withTimeout(
    postJson<ListeningAnswerResponse>(`/api/listening/answer?${query}`, {
      question_id: questionId,
      answer_index: answerIndex,
      response_time_ms: responseTimeMs,
      replay_count: replayCount,
    }),
    TIMEOUT_SUBMIT_MS,
    "submit answer",
  );
}

export function getListeningStats(userId: string): Promise<ListeningStats> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return withTimeout(
    getJson<ListeningStats>(`/api/listening/stats?${query}`),
    TIMEOUT_READ_MS,
    "listening stats",
  );
}

export function submitListeningDictation(
  userId: string,
  questionId: string,
  transcript: string,
): Promise<ListeningProductionResult> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return withTimeout(
    postJson<ListeningProductionResult>(
      `/api/listening/dictation?${query}`,
      { question_id: questionId, transcript },
    ),
    TIMEOUT_SUBMIT_MS,
    "submit dictation",
  );
}

export function submitListeningShadowing(
  userId: string,
  questionId: string,
  transcript: string,
): Promise<ListeningProductionResult> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return withTimeout(
    postJson<ListeningProductionResult>(
      `/api/listening/shadowing?${query}`,
      { question_id: questionId, transcript },
    ),
    TIMEOUT_SUBMIT_MS,
    "submit shadowing",
  );
}

export function getListeningDiagnostic(
  userId: string,
): Promise<ListeningDiagnostic> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return withTimeout(
    getJson<ListeningDiagnostic>(`/api/listening/diagnostic?${query}`),
    TIMEOUT_READ_MS,
    "listening diagnostic",
  );
}

export function getListeningAudioUrl(
  questionId: string,
  userId: string,
  variant = "normal",
): string {
  const params = new URLSearchParams({ user_id: userId });
  // Retrocompatible: sin `variant` (o con "normal") la URL es la misma de antes.
  if (variant !== "normal") {
    params.set("variant", variant);
  }
  return `/api/listening/audio/${questionId}?${params.toString()}`;
}

// --- Práctica extra generada (V3.6) ------------------------------------------
// La generación corre en un trabajo en segundo plano del backend (el modelo
// local tarda minutos): `addRouteExtras` devuelve el trabajo y `getRouteExtrasJob`
// permite hacer polling hasta `done`/`error`.

export function addRouteExtras(
  userId: string,
  level: string,
  count: number,
): Promise<ListeningExtrasJob> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return postJson<ListeningExtrasJob>(
    `/api/listening/routes/${level}/extras?${query}`,
    { count },
  );
}

export function getRouteExtrasJob(
  userId: string,
  level: string,
  jobId: string,
): Promise<ListeningExtrasJob> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return withTimeout(
    getJson<ListeningExtrasJob>(
      `/api/listening/routes/${level}/extras/jobs/${jobId}?${query}`,
    ),
    TIMEOUT_READ_MS,
    "extras job",
  );
}

export function listRouteExtras(
  userId: string,
  level: string,
): Promise<ListeningRouteExtras> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return getJson<ListeningRouteExtras>(
    `/api/listening/routes/${level}/extras?${query}`,
  );
}

export function removeRouteExtra(
  userId: string,
  level: string,
  questionId: string,
): Promise<ListeningRouteExtras> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return deleteJson<ListeningRouteExtras>(
    `/api/listening/routes/${level}/extras/${questionId}?${query}`,
  );
}
