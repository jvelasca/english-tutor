import type {
  ListeningFlowStage,
  ListeningFlowStep,
  ListeningQuestion,
  ListeningTranscriptPolicy,
  ListeningTranscriptState,
} from "../../types/api";

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
