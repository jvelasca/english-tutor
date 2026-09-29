import { deleteJson, getJson, postJson, withTimeout } from "./client";
import type {
  ListeningAnswerResponse,
  ListeningDiagnostic,
  ListeningExtrasJob,
  ListeningLevelItems,
  ListeningProductionResult,
  ListeningQuestion,
  ListeningReviewEntry,
  ListeningReviewQueue,
  ListeningRouteExtras,
  ListeningStats,
  ListeningSupportMetadata,
  ListeningTranscriptPolicy,
  ListeningWordTiming,
  SentenceTiming,
} from "../types/api";

// Timeouts de red del bucle de práctica: el backend es local, pero en iPad por
// WiFi (o con otra sesión abierta en el PC) una petición puede tardar o caerse a
// medias. Si una de estas llamadas no responde, falla con un error legible en vez
// de dejar la pantalla sin el botón "Continuar" (obligando a refrescar).
const TIMEOUT_SUBMIT_MS = 20000;
const TIMEOUT_QUESTION_MS = 15000;
const TIMEOUT_READ_MS = 10000;

export type ListeningQuestionMode = "all" | "failed" | "mastered";

/**
 * Forma CRUDA del ítem tal como la sirve el backend.
 *
 * V3.92: `transcript_policy`, `sentence_timings` y `word_timings` viajan en
 * snake_case (el contrato de Pydantic), pero el cliente los consume en camelCase
 * (V3.27/V3.28/V3.29). Sin esta traga, `question.transcriptPolicy` llegaba
 * `undefined` y con él se caía la tarjeta de fallo de V3.89 (las tres acciones
 * «Continuar / Repasar ahora / Repasar después» nunca se pintaban) y el karaoke
 * de V3.29 servía siempre lista vacía. Se normaliza en el BORDE, una vez, para
 * que ninguna pantalla tenga que conocer las dos formas.
 */
interface RawListeningQuestion extends ListeningQuestion {
  transcript_policy?: ListeningTranscriptPolicy;
  sentence_timings?: SentenceTiming[];
  word_timings?: ListeningWordTiming[];
}

/** Traduce el ítem servido (snake_case) a la forma que consume la UI. */
export function toListeningQuestion(raw: RawListeningQuestion): ListeningQuestion {
  const {
    transcript_policy: policy,
    sentence_timings: sentences,
    word_timings: words,
    ...rest
  } = raw;
  const out: ListeningQuestion = { ...rest };
  // El camelCase manda si ya viniera (mocks, consumidores nuevos): solo se
  // rellena lo que falte, nunca se pisa un valor explícito.
  if (out.transcriptPolicy === undefined && policy !== undefined) {
    out.transcriptPolicy = policy;
  }
  if (out.sentenceTimings === undefined && sentences !== undefined) {
    out.sentenceTimings = sentences;
  }
  if (out.wordTimings === undefined && words !== undefined) {
    out.wordTimings = words;
  }
  return out;
}

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
    getJson<RawListeningQuestion>(
      `/api/listening/question${query ? `?${query}` : ""}`,
    ).then(toListeningQuestion),
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
      // V3.89 (Listening robusto): desenlace del intento (hecho, no política).
      ...(opts.attemptNumber !== undefined
        ? { attempt_number: opts.attemptNumber }
        : {}),
      ...(opts.hintUsed !== undefined ? { hint_used: opts.hintUsed } : {}),
      ...(opts.solutionShown !== undefined
        ? { solution_shown: opts.solutionShown }
        : {}),
    }),
    TIMEOUT_SUBMIT_MS,
    "submit answer",
  );
}

// --- Cola de repaso de frases (V3.89, Listening robusto) ---------------------
// El fallo de comprensión auditiva se reabre más tarde con una cola propia (no
// es FSRS: el objeto es una frase, no una flashcard). El alumno puede consultar
// la cola y posponer una entrada («repasar después») en vez de ignorarla.

export function getListeningReviewQueue(
  _userId: string,
  onlyDue = false,
): Promise<ListeningReviewQueue> {
  const query = onlyDue ? "?only_due=true" : "";
  return withTimeout(
    getJson<ListeningReviewQueue>(`/api/listening/review-queue${query}`),
    TIMEOUT_READ_MS,
    "review queue",
  );
}

export function deferListeningReview(
  _userId: string,
  questionId: string,
  hours = 24,
): Promise<ListeningReviewEntry> {
  return postJson<ListeningReviewEntry>(
    `/api/listening/review-queue/${questionId}/defer`,
    { hours },
  );
}

export function resolveListeningReview(
  _userId: string,
  questionId: string,
): Promise<void> {
  return deleteJson<void>(`/api/listening/review-queue/${questionId}`);
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
