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
  ListeningSupportMetadata,
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
  _userId: string,
  level?: string | null,
  mode?: ListeningQuestionMode,
): Promise<ListeningQuestion> {
  const params = new URLSearchParams();
  // `level` entra en juego en el repaso de un nivel ya completado: el selector
  // rota por las frases del nivel en lugar de seguir al Student Model.
  if (level) params.set("level", level);
  // `mode="failed"` (drill) restringe el selector a las frases del nivel que se
  // han intentado pero nunca acertado. `mode="mastered"` (repasar lo aprendido)
  // lo restringe a las acertadas alguna vez. Solo se envían cuando se indica.
  if (mode && mode !== "all") params.set("mode", mode);
  const query = params.toString();
  return withTimeout(
    getJson<ListeningQuestion>(`/api/listening/question${query ? `?${query}` : ""}`),
    TIMEOUT_QUESTION_MS,
    "get question",
  );
}

export function getListeningLevelItems(
  _userId: string,
  level: string,
): Promise<ListeningLevelItems> {
  const params = new URLSearchParams({ level });
  return getJson<ListeningLevelItems>(`/api/listening/items?${params.toString()}`);
}

export function submitListeningAnswer(
  _userId: string,
  questionId: string,
  answerIndex: number,
  responseTimeMs: number | null = null,
  replayCount = 0,
  opts: ListeningSupportMetadata = {},
): Promise<ListeningAnswerResponse> {
  return withTimeout(
    postJson<ListeningAnswerResponse>("/api/listening/answer", {
      question_id: questionId,
      answer_index: answerIndex,
      response_time_ms: responseTimeMs,
      replay_count: replayCount,
      // Evidencia ampliada (V3.27): se envían solo los campos presentes.
      ...(opts.layer !== undefined ? { layer: opts.layer } : {}),
      ...(opts.speedUsed !== undefined ? { speed_used: opts.speedUsed } : {}),
      ...(opts.stage !== undefined ? { stage: opts.stage } : {}),
      ...(opts.transcriptUsed !== undefined
        ? { transcript_used: opts.transcriptUsed }
        : {}),
      ...(opts.segmentsReplayed !== undefined
        ? { segments_replayed: opts.segmentsReplayed }
        : {}),
    }),
    TIMEOUT_SUBMIT_MS,
    "submit answer",
  );
}

export function getListeningStats(_userId: string): Promise<ListeningStats> {
  return withTimeout(
    getJson<ListeningStats>("/api/listening/stats"),
    TIMEOUT_READ_MS,
    "listening stats",
  );
}

function submitProduction(
  endpoint: string,
  _userId: string,
  questionId: string,
  transcript: string,
  opts: ListeningSupportMetadata = {},
  aux: ListeningShadowingAux = {},
): Promise<ListeningProductionResult> {
  return withTimeout(
    postJson<ListeningProductionResult>(endpoint, {
      question_id: questionId,
      transcript,
      ...(opts.stage !== undefined ? { stage: opts.stage } : {}),
      ...(opts.transcriptUsed !== undefined
        ? { transcript_used: opts.transcriptUsed }
        : {}),
      ...(opts.speedUsed !== undefined ? { speed_used: opts.speedUsed } : {}),
      // Señales auxiliares del Shadowing 2.0 (V3.28, Bloque E): informativas,
      // calculadas por el cliente desde el audio grabado; solo viajan cuando el
      // llamador las aporta (dictation nunca las envía).
      ...(aux.durationMs !== undefined
        ? { shadowing_duration_ms: aux.durationMs }
        : {}),
      ...(aux.speechRate !== undefined
        ? { shadowing_speech_rate: aux.speechRate }
        : {}),
    }),
    TIMEOUT_SUBMIT_MS,
    "submit production",
  );
}

export function submitListeningDictation(
  _userId: string,
  questionId: string,
  transcript: string,
  opts: ListeningSupportMetadata = {},
): Promise<ListeningProductionResult> {
  return submitProduction(
    "/api/listening/dictation",
    _userId,
    questionId,
    transcript,
    opts,
  );
}

export function submitListeningShadowing(
  _userId: string,
  questionId: string,
  transcript: string,
  opts: ListeningSupportMetadata = {},
  aux: ListeningShadowingAux = {},
): Promise<ListeningProductionResult> {
  return submitProduction(
    "/api/listening/shadowing",
    _userId,
    questionId,
    transcript,
    opts,
    aux,
  );
}

// Señales auxiliares del Shadowing 2.0 (V3.28, Bloque E): informativas y
// opcionales. El cliente las calcula de forma determinista desde el audio
// grabado (duración real de la grabación y velocidad proxy de habla en wpm).
// Nunca tienen peso de mastery: el backend las persiste solo en intentos de
// shadowing y el scoring sigue siendo la comparación del texto oído.
export interface ListeningShadowingAux {
  durationMs?: number;
  speechRate?: number;
}

export function getListeningDiagnostic(
  _userId: string,
): Promise<ListeningDiagnostic> {
  return withTimeout(
    getJson<ListeningDiagnostic>("/api/listening/diagnostic"),
    TIMEOUT_READ_MS,
    "listening diagnostic",
  );
}

/**
 * URL del audio cacheado del ítem. `variant` selecciona la variante de velocidad
 * (la `normal` preserva la URL histórica) y `voice` (V3.75.5) pide una voz
 * concreta —la B del comparador de acentos— sin cambiar la preferencia del
 * perfil. Sin `voice` la URL es idéntica a la de antes, así que la caché del
 * navegador y el controlador de audio no se invalidan por abrir el código nuevo.
 */
export function getListeningAudioUrl(
  questionId: string,
  _userId: string,
  variant = "normal",
  voice?: string | null,
): string {
  const params = new URLSearchParams();
  if (variant && variant !== "normal") params.set("variant", variant);
  if (voice) params.set("voice", voice);
  const query = params.toString();
  return `/api/listening/audio/${questionId}${query ? `?${query}` : ""}`;
}

// --- Práctica extra generada (V3.6) ------------------------------------------
// La generación corre en un trabajo en segundo plano del backend (el modelo
// local tarda minutos): `addRouteExtras` devuelve el trabajo y `getRouteExtrasJob`
// permite hacer polling hasta `done`/`error`.

export function addRouteExtras(
  _userId: string,
  level: string,
  count: number,
): Promise<ListeningExtrasJob> {
  return postJson<ListeningExtrasJob>(
    `/api/listening/routes/${level}/extras`,
    { count },
  );
}

export function getRouteExtrasJob(
  _userId: string,
  level: string,
  jobId: string,
): Promise<ListeningExtrasJob> {
  return withTimeout(
    getJson<ListeningExtrasJob>(
      `/api/listening/routes/${level}/extras/jobs/${jobId}`,
    ),
    TIMEOUT_READ_MS,
    "extras job",
  );
}

export function listRouteExtras(
  _userId: string,
  level: string,
): Promise<ListeningRouteExtras> {
  return getJson<ListeningRouteExtras>(
    `/api/listening/routes/${level}/extras`,
  );
}

export function removeRouteExtra(
  _userId: string,
  level: string,
  questionId: string,
): Promise<ListeningRouteExtras> {
  return deleteJson<ListeningRouteExtras>(
    `/api/listening/routes/${level}/extras/${questionId}`,
  );
}
