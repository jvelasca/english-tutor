import type {
  ListeningFlowStage,
  ListeningFlowStep,
  ListeningQuestion,
  ListeningTranscriptPolicy,
  ListeningTranscriptState,
  ListeningWordTiming,
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

// ---------------------------------------------------------------------------
// Karaoke palabra a palabra (V3.29, Fase 3): helpers puros sobre los word
// timings del sidecar `word_alignment_proxy` servidos por el backend.
// ---------------------------------------------------------------------------

/** Timings por palabra del ítem (vacío si el backend no sirvió sidecar). */
export function wordTimingsOf(question: ListeningQuestion): ListeningWordTiming[] {
  return question.wordTimings ?? [];
}

/** Índice global de la palabra activa según `currentTime`.

 * Regla monótona análoga a `activeSentenceIndex`: la palabra activa es la última
 * cuyo `start` ya se alcanzó (si el audio terminó se mantiene la última; si aún
 * no empezó ninguna, `null`). Los intervalos no solapan y van en orden de tiempo.
 */
export function activeWordIndex(
  timings: ListeningWordTiming[],
  currentTime: number,
): number | null {
  if (timings.length === 0) return null;
  const time = Number.isFinite(currentTime) ? currentTime : 0;
  let active: number | null = null;
  for (const word of timings) {
    if (time < word.start) break;
    active = word.index;
    if (time < word.end) break;
  }
  return active;
}

/** Palabras que pertenecen a una frase (`sentence` = índice en sentenceTimings). */
export function wordsForSentence(
  timings: ListeningWordTiming[],
  sentence: number,
): ListeningWordTiming[] {
  return timings.filter((word) => word.sentence === sentence);
}

/** Escala tiempos por palabra por un factor (`start`/`end` multiplicados).

 * Slow/fast se reproducen con la misma voz pero distinto `length_scale` de
 * Piper: la duración del audio (y cada palabra) escala ~inversamente a la tasa.
 * El factor se deriva de las `variants` del ítem
 * (`variantTimeScale(question, variant)`) y es 1 para la variante `normal`
 * (los timings del payload ya corresponden a ella). Aproximación documentada:
 * `sync` pasa a ser `scaled_word_proxy` conceptualmente, nunca verdad acústica.
 */
export function scaleWordTimings(
  timings: ListeningWordTiming[],
  factor: number,
): ListeningWordTiming[] {
  const scale = Number.isFinite(factor) && factor > 0 ? factor : 1;
  if (scale === 1) return timings;
  return timings.map((word) => ({
    ...word,
    start: Math.round(word.start * scale * 1000) / 1000,
    end: Math.round(word.end * scale * 1000) / 1000,
  }));
}

/** Factor de tiempo de una variante respecto a `normal` (ver `scaleWordTimings`).

 * Con `speech_rate` declarada: ratio `normal_rate / variant_rate` (slow > 1,
 * fast < 1). Sin tasas fiables devuelve 1 (sin escalado).
 */
export function variantTimeScale(
  question: ListeningQuestion,
  variant: string,
): number {
  if (variant === "normal") return 1;
  const variants = question.variants ?? [];
  const normal = variants.find((v) => v.variant === "normal");
  const chosen = variants.find((v) => v.variant === variant);
  if (
    normal &&
    chosen &&
    normal.speech_rate > 0 &&
    chosen.speech_rate > 0
  ) {
    return normal.speech_rate / chosen.speech_rate;
  }
  return 1;
}

// ---------------------------------------------------------------------------
// Salto a la palabra fallada (V3.29, Fase 3, P6): helpers puros sobre los word
// timings y el resultado (dictation/ MC cloze incorrecto) para "repetir la
// palabra fallada" en normal o slow. El resultado se escala ANTES de localizar
// (misma voz, slow/fast con distinta duración) con `scaleWordTimings`.
// ---------------------------------------------------------------------------

/** Ref acotada de una palabra (o frase) fallada para seek + loop. */
export interface FailedWordRef {
  text: string;
  start: number;
  end: number;
}

/** Tokens normalizados de un texto (minúsculas; apóstrofo interno conservado),
 * análogo a `tokenize` del backend para comparar grafías. */
export function wordTokensOf(text: string): string[] {
  return (text ?? "").toLowerCase().match(/[a-z0-9']+/g) ?? [];
}

/** Primera palabra que el alumno no oyó en el breakdown de una producción
 * (dictado): primer token de `missing` o, si no, `expected` del primer
 * `substituted`. `null` si no hay fallo de palabra (o el breakdown no es el
 * esperado). */
export function firstFailedWord(
  breakdown: Record<string, unknown> | null | undefined,
): string | null {
  if (!breakdown || typeof breakdown !== "object") return null;
  const missing = breakdown.missing;
  if (Array.isArray(missing)) {
    for (const word of missing) {
      if (typeof word === "string" && word.trim()) return word.trim();
    }
  }
  const substituted = breakdown.substituted;
  if (Array.isArray(substituted)) {
    for (const entry of substituted) {
      if (entry && typeof entry === "object") {
        const expected = (entry as { expected?: unknown }).expected;
        if (typeof expected === "string" && expected.trim()) {
          return expected.trim();
        }
      }
    }
  }
  return null;
}

/**
 * Localiza por tiempo la palabra/frase fallada para el salto con repetición.
 *
 * `targetText` es el texto que el alumno no oyó bien: en dictado, la palabra
 * devuelta por `firstFailedWord(breakdown)`; en un MCQ cloze/segmentation
 * incorrecto, la opción correcta (la frase diana). `wordTimings` deben venir ya
 * escalados a la variante que se va a reproducir (ver `scaleWordTimings`).
 *
 * Búsqueda honesta y en cascada:
 * 1. Aparición como secuencia contigua de tokens normalizados en `wordTimings`
 *    (primera ocurrencia en orden de tiempo).
 * 2. Si no aparece (p. ej. reducción/expansión: `going to` → `gonna`, o la
 *    opción correcta es una frase completa), la frase de `sentenceTimings`
 *    cuyo texto la contiene como secuencia contigua; se devuelve su intervalo
 *    como aproximación honesta.
 * 3. Sin respaldo: `null` (el llamador oculta el botón, no hay salto fiable).
 */
export function failedWordTiming(
  targetText: string,
  wordTimings: ListeningWordTiming[],
  sentenceTimings: SentenceTiming[],
): FailedWordRef | null {
  const target = wordTokensOf(targetText);
  if (target.length === 0 || wordTimings.length === 0) return null;
  const tokens = wordTimings.map((word) => wordTokensOf(word.text)[0] ?? "");

  // 1. Secuencia contigua en los word timings (primera aparición).
  for (let i = 0; i + target.length <= tokens.length; i += 1) {
    let matches = true;
    for (let k = 0; k < target.length; k += 1) {
      if (tokens[i + k] !== target[k]) {
        matches = false;
        break;
      }
    }
    if (!matches) continue;
    const first = wordTimings[i];
    const last = wordTimings[i + target.length - 1];
    return {
      text: wordTimings.slice(i, i + target.length).map((w) => w.text).join(" "),
      start: first.start,
      end: last.end,
    };
  }

  // 2. Aproximación por frase contenedora (el token no está en el sidecar).
  for (const sentence of sentenceTimings) {
    const sentenceTokens = wordTokensOf(sentence.text);
    if (sentenceTokens.length < target.length) continue;
    for (let i = 0; i + target.length <= sentenceTokens.length; i += 1) {
      let matches = true;
      for (let k = 0; k < target.length; k += 1) {
        if (sentenceTokens[i + k] !== target[k]) {
          matches = false;
          break;
        }
      }
      if (matches) {
        return { text: sentence.text, start: sentence.start, end: sentence.end };
      }
    }
  }

  // 3. Sin respaldo fiable.
  return null;
}
