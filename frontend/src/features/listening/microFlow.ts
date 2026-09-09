import type {
  ListeningFlowStage,
  ListeningFlowStep,
  ListeningQuestion,
  ListeningTranscriptPolicy,
  ListeningTranscriptState,
} from "../../types/api";

// Timings gruesos de frase (V3.28, Bloque D): el backend reparte `duration` por
// peso textual de cada frase (`sync: "coarse_heuristic"`). NO es alineación
// acústica: la UI lo trata como referencia aproximada para resaltar la frase
// activa mientras suena el audio, nunca como karaoke palabra a palabra (Fase 3).
export interface SentenceTiming {
  index: number;
  start: number;
  end: number;
  text: string;
  sync: string;
}

/**
 * Máquina de estados del micro-flujo por ítem (V3.27, Listening Engine 4.0).
 *
 * Es una máquina de *presentación*: NO contiene reglas pedagógicas propias. El
 * backend sirve en cada pregunta el `flow` (pasos) y la `transcriptPolicy`
 * (contrato de revelado); este módulo solo los ejecuta (§3.1 del plan V3.27).
 *
 * Etapas receptivas: pre → while1 (escucha global) → while2 (pregunta nativa)
 * → post (revisión) → shadowing (opcional) → finished.
 * Ítems de producción (dictation/shadowing) llegan con un único paso `while2`
 * (task production): al completarlo con respuesta se acaba el flujo.
 */

export type Stage = ListeningFlowStage;
export type TranscriptState = ListeningTranscriptState;

export interface MicroFlowState {
  /** Índice del paso actual dentro de `flow`; -1 si no hay flujo. */
  stepIndex: number;
  stage: Stage | null;
  transcript: TranscriptState;
  /** Ya se mostró la transcripción completa (se registra `transcript_used`). */
  revealed: boolean;
  /** Reintentos consumidos en la etapa de respuesta actual (while2). */
  attemptCount: number;
  shadowingDone: boolean;
  finished: boolean;
}

export function flowOf(question: ListeningQuestion): ListeningFlowStep[] {
  return question.flow ?? [];
}

export function hasFlow(question: ListeningQuestion): boolean {
  return (question.flow?.length ?? 0) > 0;
}

/** True si el flujo de este ítem es la tarea de producción directa. */
export function isProductionFlow(question: ListeningQuestion): boolean {
  const flow = flowOf(question);
  return (
    flow.length === 1 &&
    flow[0].stage === "while2" &&
    flow[0].task === "production"
  );
}

export function currentStep(
  state: MicroFlowState,
  flow: ListeningFlowStep[],
): ListeningFlowStep | null {
  if (state.stepIndex < 0 || state.stepIndex >= flow.length) return null;
  return flow[state.stepIndex];
}

export function initialFlow(question: ListeningQuestion): MicroFlowState {
  const flow = flowOf(question);
  if (flow.length === 0) {
    return {
      stepIndex: -1,
      stage: null,
      transcript: "hidden",
      revealed: false,
      attemptCount: 0,
      shadowingDone: false,
      finished: false,
    };
  }
  const first = flow[0];
  return {
    stepIndex: 0,
    stage: first.stage,
    transcript: first.transcript_state_inicial,
    revealed: false,
    attemptCount: 0,
    shadowingDone: false,
    finished: false,
  };
}

/** Avanza al siguiente paso del flujo (sin resolver respuesta). Usado para
 * completar pre/while1/post/shadowing. */
export function advanceToNext(
  state: MicroFlowState,
  flow: ListeningFlowStep[],
): MicroFlowState {
  const nextIndex = state.stepIndex + 1;
  const next = nextIndex < flow.length ? flow[nextIndex] : null;
  if (!next) {
    return {
      ...state,
      stepIndex: flow.length,
      stage: null,
      finished: true,
    };
  }
  return {
    stepIndex: nextIndex,
    stage: next.stage,
    transcript: next.transcript_state_inicial,
    revealed: false,
    attemptCount: 0,
    shadowingDone: state.shadowingDone,
    finished: false,
  };
}

/** Revela la transcripción completa (toggle del post / reintento con apoyo).
 * Solo si la política lo permite (`allowManualReveal`) y aún no está revelada. */
export function revealFull(
  state: MicroFlowState,
  policy: ListeningTranscriptPolicy,
): MicroFlowState {
  if (state.revealed || state.transcript === "full") return state;
  if (!policy.allow_manual_reveal) return state;
  return { ...state, transcript: "full", revealed: true };
}

/** El alumno completa el paso `shadowing` (grabación realizada o saltada). */
export function completeShadowing(state: MicroFlowState): MicroFlowState {
  return { ...state, shadowingDone: true };
}

/**
 * Resuelve la respuesta de la etapa actual (while2) y decide la transición.
 *
 * - Correcta → avanza al siguiente paso (post), con su transcript inicial.
 * - Incorrecta y quedan reintentos (`max_attempts_per_stage`) → reintento en la
 *   misma etapa con `attemptCount+1`; si la política es `on_first_fail`, el
 *   reintento se hace con la transcripción ya visible (apoyo).
 * - Incorrecta y sin reintentos → avanza a post y revela la transcripción
 *   (en post se revisa el resultado con `transcript_used=full`).
 *
 * En etapas que no son de respuesta (pre/while1/post) simplemente avanza.
 */
export function completeStageWithAnswer(
  state: MicroFlowState,
  correct: boolean,
  policy: ListeningTranscriptPolicy,
  flow: ListeningFlowStep[],
): MicroFlowState {
  if (state.stage !== "while2" || state.finished) {
    return advanceToNext(state, flow);
  }
  const maxAttempts = policy.max_attempts_per_stage;
  if (!correct) {
    if (state.attemptCount + 1 < maxAttempts) {
      // Reintento en la misma etapa. En `on_first_fail` (A1) el apoyo se
      // muestra en el reintento: la tarea deja de ser "a ciegas".
      const withSupport =
        policy.revelation === "on_first_fail" &&
        !state.revealed &&
        state.transcript !== "full";
      return {
        ...state,
        attemptCount: state.attemptCount + 1,
        transcript: withSupport ? "full" : state.transcript,
        revealed: withSupport || state.revealed,
      };
    }
    // Sin reintentos: se cierra la fase de respuesta revelando el resultado.
    const next = advanceToNext(state, flow);
    return { ...next, transcript: "full", revealed: true };
  }
  // Correcta: se avanza; la transcripción se podrá revelar en post.
  return advanceToNext(state, flow);
}

/** Reintento explícito solicitado por la UI cuando quedan intentos. */
export function retryStage(state: MicroFlowState): MicroFlowState {
  return { ...state, attemptCount: state.attemptCount + 1 };
}

/** True mientras el alumno está contestando la pregunta (etapa with2). */
export function isAnswering(state: MicroFlowState): boolean {
  return state.stage === "while2" && !state.finished;
}

// ---------------------------------------------------------------------------
// Sync grueso del transcript (V3.28, Bloque D): helpers puros de resaltado.
// ---------------------------------------------------------------------------

/** Timings de frase del ítem servidos por el backend (vacío si no hay flow o
 * el ítem no declara `duration`). */
export function timingsOf(question: ListeningQuestion): SentenceTiming[] {
  return question.sentenceTimings ?? [];
}

/** Índice de la frase activa según `currentTime` del elemento de audio.

 * Regla monótona: la frase activa es la última cuyo `start` ya se alcanzó (si el
 * audio terminó se mantiene la última frase; si aún no empezó ninguna, -1). Los
 * timings son heurísticos y no solapan entre sí, así que basta recorrerlos en
 * orden y cortar en cuanto el tiempo no alcanza el siguiente `start`.
 */
export function activeSentenceIndex(
  timings: SentenceTiming[],
  currentTime: number,
): number {
  if (timings.length === 0) return -1;
  const time = Number.isFinite(currentTime) ? currentTime : 0;
  let active = -1;
  for (const segment of timings) {
    if (time < segment.start) break;
    active = segment.index;
    if (time < segment.end) break;
  }
  return active;
}

/** Frases visibles según el estado de revelado (`transcript_state_inicial`).

 * - `full` → todas las frases (revelado completo).
 * - `partial` → solo la frase activa (la transcripción parcial muestra el
 *   segmento/frase permitido en cada etapa, no el texto entero).
 * - `hidden` → ninguna.
 * Devuelve índices de `timings` (que con `repetition_policy=twice` pueden
 * repetir texto); vacío ⇒ la UI no muestra transcripción.
 */
export function revealSentenceIndexes(
  state: TranscriptState,
  timings: SentenceTiming[],
  activeIndex: number,
): number[] {
  if (state === "full") return timings.map((segment) => segment.index);
  if (state === "partial" && activeIndex >= 0) {
    return [activeIndex];
  }
  return [];
}
