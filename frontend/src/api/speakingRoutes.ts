import { deleteJson, getJson, postForm, postJson, withTimeout } from "./client";
import type {
  SpeakingAttempt,
  SpeakingExtrasJob,
  SpeakingLevelItems,
  SpeakingPhrase,
  SpeakingRouteExtras,
  SpeakingStats,
} from "../types/api";

// Timeouts de red del bucle de micro-conversación (misma filosofía que
// listening): el backend es local, pero en iPad por WiFi una petición puede
// tardar o caerse a medias. Sin timeout, una llamada colgada dejaría la pantalla
// sin el botón "Continuar" (obligando a refrescar).
const TIMEOUT_SUBMIT_MS = 150000; // Whisper + evaluación LLM local (CPU)
const TIMEOUT_QUESTION_MS = 15000;
const TIMEOUT_READ_MS = 10000;

export type SpeakingQuestionMode = "all" | "failed" | "mastered";
export type SpeakingAudioKind = "opening" | "model";

export function getSpeakingQuestion(
  _userId: string,
  level?: string | null,
  mode?: SpeakingQuestionMode,
): Promise<SpeakingPhrase> {
  const params = new URLSearchParams();
  if (level) params.set("level", level);
  if (mode && mode !== "all") params.set("mode", mode);
  const query = params.toString();
  return withTimeout(
    getJson<SpeakingPhrase>(`/api/speaking/question${query ? `?${query}` : ""}`),
    TIMEOUT_QUESTION_MS,
    "get question",
  );
}

export function getSpeakingLevelItems(
  _userId: string,
  level: string,
): Promise<SpeakingLevelItems> {
  const params = new URLSearchParams({ level });
  return getJson<SpeakingLevelItems>(`/api/speaking/items?${params.toString()}`);
}

export function getSpeakingStats(_userId: string): Promise<SpeakingStats> {
  return withTimeout(
    getJson<SpeakingStats>("/api/speaking/stats"),
    TIMEOUT_READ_MS,
    "speaking stats",
  );
}

/**
 * Envía la grabación de la respuesta a una tarjeta de micro-conversación.
 *
 * El backend transcribe el audio (Whisper local) y evalúa la respuesta abierta
 * con el pipeline LLM + `scores_from_evidence` (mismo que misiones/assessment).
 */
export function submitSpeakingAttempt(
  _userId: string,
  phraseId: string,
  blob: Blob,
): Promise<SpeakingAttempt> {
  const form = new FormData();
  form.append("file", blob, "audio.webm");
  form.append("phrase_id", phraseId);
  return withTimeout(
    postForm<SpeakingAttempt>("/api/speaking/attempt", form),
    TIMEOUT_SUBMIT_MS,
    "submit attempt",
  );
}

export function getSpeakingAudioUrl(
  phraseId: string,
  _userId: string,
  kind: SpeakingAudioKind = "opening",
): string {
  const params = new URLSearchParams({ kind });
  return `/api/speaking/audio/${phraseId}?${params.toString()}`;
}

// --- Práctica extra generada (V3.7) ------------------------------------------

export function addSpeakingRouteExtras(
  _userId: string,
  level: string,
  count: number,
): Promise<SpeakingExtrasJob> {
  return postJson<SpeakingExtrasJob>(
    `/api/speaking/routes/${level}/extras`,
    { count },
  );
}

export function getSpeakingRouteExtrasJob(
  _userId: string,
  level: string,
  jobId: string,
): Promise<SpeakingExtrasJob> {
  return withTimeout(
    getJson<SpeakingExtrasJob>(
      `/api/speaking/routes/${level}/extras/jobs/${jobId}`,
    ),
    TIMEOUT_READ_MS,
    "extras job",
  );
}

export function listSpeakingRouteExtras(
  _userId: string,
  level: string,
): Promise<SpeakingRouteExtras> {
  return getJson<SpeakingRouteExtras>(
    `/api/speaking/routes/${level}/extras`,
  );
}

export function removeSpeakingRouteExtra(
  _userId: string,
  level: string,
  phraseId: string,
): Promise<SpeakingRouteExtras> {
  return deleteJson<SpeakingRouteExtras>(
    `/api/speaking/routes/${level}/extras/${phraseId}`,
  );
}
