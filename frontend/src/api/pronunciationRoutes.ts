import { getJson, postForm, withTimeout } from "./client";
import type {
  PronunciationAttempt,
  PronunciationLevelItems,
  PronunciationPhrase,
  PronunciationStats,
} from "../types/api";

// Timeouts de red del bucle de read-aloud (misma filosofía que listening/
// speaking): el backend es local, pero en iPad por WiFi una petición puede
// tardar o caerse a medias.
const TIMEOUT_SUBMIT_MS = 60000; // Whisper local (CPU) sobre una frase corta
const TIMEOUT_QUESTION_MS = 15000;
const TIMEOUT_READ_MS = 10000;

export type PronunciationQuestionMode = "all" | "failed" | "mastered";

export function getPronunciationQuestion(
  userId: string,
  level?: string | null,
  mode?: PronunciationQuestionMode,
): Promise<PronunciationPhrase> {
  const params = new URLSearchParams({ user_id: userId });
  if (level) params.set("level", level);
  if (mode && mode !== "all") params.set("mode", mode);
  return withTimeout(
    getJson<PronunciationPhrase>(
      `/api/pronunciation/routes/question?${params.toString()}`,
    ),
    TIMEOUT_QUESTION_MS,
    "get question",
  );
}

export function getPronunciationLevelItems(
  userId: string,
  level: string,
): Promise<PronunciationLevelItems> {
  const params = new URLSearchParams({ user_id: userId, level });
  return getJson<PronunciationLevelItems>(
    `/api/pronunciation/routes/items?${params.toString()}`,
  );
}

export function getPronunciationStats(
  userId: string,
): Promise<PronunciationStats> {
  const query = new URLSearchParams({ user_id: userId }).toString();
  return withTimeout(
    getJson<PronunciationStats>(`/api/pronunciation/routes/stats?${query}`),
    TIMEOUT_READ_MS,
    "pronunciation stats",
  );
}

/**
 * Envía la grabación de la lectura de una frase modelo.
 *
 * El backend transcribe el audio (Whisper local) y evalúa la lectura con el
 * scorer determinista `score_pronunciation` (sin LLM por intento).
 */
export function submitPronunciationAttempt(
  userId: string,
  phraseId: string,
  blob: Blob,
): Promise<PronunciationAttempt> {
  const form = new FormData();
  form.append("file", blob, "audio.webm");
  form.append("phrase_id", phraseId);
  const query = new URLSearchParams({ user_id: userId }).toString();
  return withTimeout(
    postForm<PronunciationAttempt>(
      `/api/pronunciation/routes/attempt?${query}`,
      form,
    ),
    TIMEOUT_SUBMIT_MS,
    "submit attempt",
  );
}
