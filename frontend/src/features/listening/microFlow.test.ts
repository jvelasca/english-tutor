import { describe, expect, it } from "vitest";
import type {
  ListeningFlowStep,
  ListeningQuestion,
  ListeningTranscriptPolicy,
} from "../../types/api";
import {
  advanceToNext,
  activeSentenceIndex,
  completeShadowing,
  completeStageWithAnswer,
  currentStep,
  flowOf,
  hasFlow,
  initialFlow,
  isAnswering,
  isProductionFlow,
  revealFull,
  revealSentenceIndexes,
  retryStage,
  timingsOf,
  type SentenceTiming,
} from "./microFlow";

const A1_POLICY: ListeningTranscriptPolicy = {
  revelation: "on_first_fail",
  max_attempts_per_stage: 2,
  allow_manual_reveal: true,
  shadowing_optional: true,
};

const B2_POLICY: ListeningTranscriptPolicy = {
  revelation: "never_before_post",
  max_attempts_per_stage: 1,
  allow_manual_reveal: false,
  shadowing_optional: true,
};

function question(overrides: Partial<ListeningQuestion> = {}): ListeningQuestion {
  return {
    id: "q1",
    level: "A1",
    skill: "gist",
    difficulty: 1,
    difficulty_vector: {},
    script: "Where do you usually go on holiday?",
    question: "What is the speaker asking about?",
    options: ["Holidays", "Work", "Food"],
    audio_id: "",
    duration: 0,
    speaker_id: "",
    accent: "neutral",
    speech_rate: 0,
    transcript: "",
    clean_transcript: "",
    noise_level: 0,
    repetition_policy: "none",
    topic: "",
    context: "",
    audio_ready: true,
    audio_type: "tts",
    realized_difficulty: 1,
    realization: {},
    layer: "comprehension",
    variants: [],
    default_variant: "normal",
    ...overrides,
  };
}

const receptiveFlow: ListeningFlowStep[] = [
  { stage: "pre", task: "activate", transcript_state_inicial: "hidden", allow_skip: true, requires_audio: false },
  { stage: "while1", task: "listen_global", transcript_state_inicial: "hidden", allow_skip: true, requires_audio: true },
  { stage: "while2", task: "native_question", transcript_state_inicial: "hidden", allow_skip: false, requires_audio: true },
  { stage: "post", task: "review", transcript_state_inicial: "partial", allow_skip: false, requires_audio: true },
  { stage: "shadowing", task: "shadowing", transcript_state_inicial: "full", allow_skip: true, requires_audio: true },
];

const productionFlow: ListeningFlowStep[] = [
  { stage: "while2", task: "production", transcript_state_inicial: "hidden", allow_skip: false, requires_audio: true },
];

describe("microFlow: helpers", () => {
  it("hasFlow/flowOf detectan la ausencia de flujo (legacy)", () => {
    const q = question();
    expect(hasFlow(q)).toBe(false);
    expect(flowOf(q)).toEqual([]);
    expect(isProductionFlow(q)).toBe(false);
  });

  it("reconoce el flujo de producción de un paso", () => {
    const q = question({ flow: productionFlow });
    expect(isProductionFlow(q)).toBe(true);
    expect(initialFlow(q).stage).toBe("while2");
  });

  it("reconoce el flujo receptivo de cinco pasos", () => {
    const q = question({ flow: receptiveFlow });
    expect(isProductionFlow(q)).toBe(false);
    expect(initialFlow(q).stage).toBe("pre");
  });
});

describe("microFlow: transiciones", () => {
  it("initialFlow arranca en el primer paso y sin estado resuelto", () => {
    const state = initialFlow(question({ flow: receptiveFlow }));
    expect(state.stepIndex).toBe(0);
    expect(state.stage).toBe("pre");
    expect(state.transcript).toBe("hidden");
    expect(state.revealed).toBe(false);
    expect(state.attemptCount).toBe(0);
    expect(state.finished).toBe(false);
  });

  it("advanceToNext recorre pre → while1 → while2 → post → shadowing", () => {
    let state = initialFlow(question({ flow: receptiveFlow }));
    state = advanceToNext(state, receptiveFlow); // → while1
    expect(state.stage).toBe("while1");
    state = advanceToNext(state, receptiveFlow); // → while2
    expect(state.stage).toBe("while2");
    state = advanceToNext(state, receptiveFlow); // → post
    expect(state.stage).toBe("post");
    expect(state.transcript).toBe("partial");
    state = advanceToNext(state, receptiveFlow); // → shadowing
    expect(state.stage).toBe("shadowing");
    state = advanceToNext(state, receptiveFlow); // → finished
    expect(state.finished).toBe(true);
    expect(state.stage).toBeNull();
  });

  it("no muta el estado (funciones puras)", () => {
    const state = initialFlow(question({ flow: receptiveFlow }));
    advanceToNext(state, receptiveFlow);
    expect(state.stage).toBe("pre");
  });
});

describe("microFlow: respuesta correcta/incorrecta en while2", () => {
  it("respuesta correcta avanza a post sin revelar", () => {
    let state = initialFlow(question({ flow: receptiveFlow }));
    state = advanceToNext(state, receptiveFlow); // pre
    state = advanceToNext(state, receptiveFlow); // while1
    expect(state.stage).toBe("while2");
    const next = completeStageWithAnswer(state, true, A1_POLICY, receptiveFlow);
    expect(next.stage).toBe("post");
    expect(next.revealed).toBe(false);
    expect(next.attemptCount).toBe(0);
  });

  it("fallo con reintentos restantes reintenta en la misma fase (A1)", () => {
    let state = initialFlow(question({ flow: receptiveFlow }));
    state = advanceToNext(state, receptiveFlow);
    state = advanceToNext(state, receptiveFlow); // while2
    const retry = completeStageWithAnswer(state, false, A1_POLICY, receptiveFlow);
    expect(retry.stage).toBe("while2");
    expect(retry.attemptCount).toBe(1);
    // A1 (on_first_fail): el reintento se hace con el apoyo visible.
    expect(retry.transcript).toBe("full");
    expect(retry.revealed).toBe(true);
  });

  it("fallo agotado en A1 (2º fallo) revela y pasa a post", () => {
    let state = initialFlow(question({ flow: receptiveFlow }));
    state = advanceToNext(state, receptiveFlow);
    state = advanceToNext(state, receptiveFlow);
    const first = completeStageWithAnswer(state, false, A1_POLICY, receptiveFlow);
    const second = completeStageWithAnswer(first, false, A1_POLICY, receptiveFlow);
    expect(second.stage).toBe("post");
    expect(second.revealed).toBe(true);
    expect(second.transcript).toBe("full");
  });

  it("fallo en B2+ (sin reintentos) cierra la fase y revela", () => {
    let state = initialFlow(question({ flow: receptiveFlow }));
    state = advanceToNext(state, receptiveFlow);
    state = advanceToNext(state, receptiveFlow);
    const next = completeStageWithAnswer(state, false, B2_POLICY, receptiveFlow);
    expect(next.stage).toBe("post");
    expect(next.revealed).toBe(true);
    expect(next.transcript).toBe("full");
  });

  it("B2+ nunca ofrece reintento", () => {
    let state = initialFlow(question({ flow: receptiveFlow }));
    state = advanceToNext(state, receptiveFlow);
    state = advanceToNext(state, receptiveFlow);
    const next = completeStageWithAnswer(state, false, B2_POLICY, receptiveFlow);
    expect(next.stage).not.toBe("while2");
  });
});

describe("microFlow: revelado manual y shadowing", () => {
  it("revealFull requiere allow_manual_reveal", () => {
    let state = initialFlow(question({ flow: receptiveFlow }));
    state = advanceToNext(state, receptiveFlow);
    state = advanceToNext(state, receptiveFlow);
    // En B2+ el toggle manual está bloqueado.
    expect(revealFull(state, B2_POLICY).revealed).toBe(false);
    // En A1 se permite.
    const revealed = revealFull(state, A1_POLICY);
    expect(revealed.revealed).toBe(true);
    expect(revealed.transcript).toBe("full");
    // Idempotente: ya revelado no cambia.
    expect(revealFull(revealed, A1_POLICY)).toBe(revealed);
  });

  it("shadowing se completa y luego finaliza el flujo", () => {
    let state = initialFlow(question({ flow: receptiveFlow }));
    for (let i = 0; i < 4; i += 1) state = advanceToNext(state, receptiveFlow);
    expect(state.stage).toBe("shadowing");
    const done = completeShadowing(state);
    expect(done.shadowingDone).toBe(true);
    const end = advanceToNext(done, receptiveFlow);
    expect(end.finished).toBe(true);
  });

  it("isAnswering solo es true en while2 sin finalizar", () => {
    const state = initialFlow(question({ flow: receptiveFlow }));
    expect(isAnswering(state)).toBe(false);
    const atWhile2 = advanceToNext(advanceToNext(state, receptiveFlow), receptiveFlow);
    expect(isAnswering(atWhile2)).toBe(true);
  });

  it("retryStage incrementa el contador sin avanzar", () => {
    let state = initialFlow(question({ flow: receptiveFlow }));
    state = advanceToNext(state, receptiveFlow);
    state = advanceToNext(state, receptiveFlow);
    expect(retryStage(state).attemptCount).toBe(1);
  });

  it("currentStep devuelve el paso actual o null", () => {
    const state = initialFlow(question({ flow: receptiveFlow }));
    expect(currentStep(state, receptiveFlow)?.stage).toBe("pre");
    const end = { ...state, finished: true, stepIndex: 5 };
    expect(currentStep(end, receptiveFlow)).toBeNull();
  });
});

describe("microFlow: sync grueso del transcript (Bloque D)", () => {
  const TIMINGS: SentenceTiming[] = [
    { index: 0, start: 0, end: 2, text: "First sentence.", sync: "coarse_heuristic" },
    { index: 1, start: 2, end: 4, text: "Second sentence.", sync: "coarse_heuristic" },
    { index: 2, start: 4, end: 6, text: "Third sentence.", sync: "coarse_heuristic" },
  ];

  it("activeSentenceIndex: frase activa según currentTime", () => {
    expect(activeSentenceIndex(TIMINGS, 0)).toBe(0);
    expect(activeSentenceIndex(TIMINGS, 1.2)).toBe(0);
    expect(activeSentenceIndex(TIMINGS, 2)).toBe(1);
    expect(activeSentenceIndex(TIMINGS, 3.5)).toBe(1);
    expect(activeSentenceIndex(TIMINGS, 5.9)).toBe(2);
    // Tras el final del audio se mantiene la última frase (reveal estable).
    expect(activeSentenceIndex(TIMINGS, 6)).toBe(2);
    expect(activeSentenceIndex(TIMINGS, 20)).toBe(2);
  });

  it("activeSentenceIndex: antes del primer start no hay frase activa", () => {
    expect(activeSentenceIndex(TIMINGS, -1)).toBe(-1);
    // Timings vacíos → sin frase activa (nunca rompe).
    expect(activeSentenceIndex([], 3)).toBe(-1);
    // Tiempo no numérico → se trata como 0 (primera frase, comienzo del audio).
    expect(activeSentenceIndex(TIMINGS, Number.NaN)).toBe(0);
  });

  it("revealSentenceIndexes: hidden → nada, full → todo, partial → frase activa", () => {
    expect(revealSentenceIndexes("hidden", TIMINGS, 1)).toEqual([]);
    expect(revealSentenceIndexes("full", TIMINGS, 1)).toEqual([0, 1, 2]);
    expect(revealSentenceIndexes("partial", TIMINGS, 1)).toEqual([1]);
    // Partial sin frase activa (aún no suena nada) no muestra transcripción.
    expect(revealSentenceIndexes("partial", TIMINGS, -1)).toEqual([]);
  });

  it("revealSentenceIndexes: partial aislada en timings con repetición (twice)", () => {
    const twice: SentenceTiming[] = [
      { index: 0, start: 0, end: 1.5, text: "Go.", sync: "coarse_heuristic" },
      { index: 1, start: 1.5, end: 3, text: "Where?", sync: "coarse_heuristic" },
      { index: 2, start: 3, end: 4.5, text: "Go.", sync: "coarse_heuristic" },
      { index: 3, start: 4.5, end: 6, text: "Where?", sync: "coarse_heuristic" },
    ];
    // Mientras suena la primera pasada de "Go." (t=0.8) la frase activa es la 0.
    expect(activeSentenceIndex(twice, 0.8)).toBe(0);
    expect(revealSentenceIndexes("partial", twice, 0)).toEqual([0]);
    // En la segunda pasada (t=4) la frase activa es la copia index 2.
    expect(activeSentenceIndex(twice, 4.2)).toBe(2);
    expect(revealSentenceIndexes("partial", twice, 2)).toEqual([2]);
  });

  it("timingsOf: expone los timings servidos por el backend (o lista vacía)", () => {
    expect(timingsOf(question({ flow: receptiveFlow }))).toEqual([]);
    expect(timingsOf(question({ flow: receptiveFlow, sentenceTimings: TIMINGS }))).toHaveLength(3);
  });
});

describe("microFlow: tareas derivadas bottom-up en el flujo (Bloque F)", () => {
  // Flujo receptivo completo cuyo while2 es un cloze auditivo o segmentación
  // derivada (V3.28, Bloque C): se ejecutan igual que la pregunta nativa.
  function derivedMcqFlow(task: "cloze" | "segmentation"): ListeningFlowStep[] {
    return [
      { stage: "pre", task: "activate", transcript_state_inicial: "hidden", allow_skip: true, requires_audio: false },
      { stage: "while1", task: "listen_global", transcript_state_inicial: "hidden", allow_skip: true, requires_audio: true },
      { stage: "while2", task, transcript_state_inicial: "hidden", allow_skip: false, requires_audio: true },
      { stage: "post", task: "review", transcript_state_inicial: "partial", allow_skip: false, requires_audio: true },
      { stage: "shadowing", task: "shadowing", transcript_state_inicial: "full", allow_skip: true, requires_audio: true },
    ];
  }

  it("cloze y segmentación no se confunden con producción", () => {
    for (const task of ["cloze", "segmentation"] as const) {
      const q = question({ flow: derivedMcqFlow(task) });
      expect(isProductionFlow(q)).toBe(false);
      expect(hasFlow(q)).toBe(true);
    }
  });

  it("cloze: respuesta correcta avanza a post (review con partial)", () => {
    let state = initialFlow(question({ flow: derivedMcqFlow("cloze") }));
    state = advanceToNext(state, derivedMcqFlow("cloze")); // pre
    state = advanceToNext(state, derivedMcqFlow("cloze")); // while1
    expect(state.stage).toBe("while2");
    const next = completeStageWithAnswer(
      state,
      true,
      A1_POLICY,
      derivedMcqFlow("cloze"),
    );
    expect(next.stage).toBe("post");
    expect(next.transcript).toBe("partial"); // revisión con transcript parcial
    expect(next.attemptCount).toBe(0);
  });

  it("segmentación: fallo sin reintentos en B2 cierra y revela en post", () => {
    let state = initialFlow(question({ flow: derivedMcqFlow("segmentation") }));
    state = advanceToNext(state, derivedMcqFlow("segmentation"));
    state = advanceToNext(state, derivedMcqFlow("segmentation"));
    const next = completeStageWithAnswer(
      state,
      false,
      B2_POLICY,
      derivedMcqFlow("segmentation"),
    );
    expect(next.stage).toBe("post");
    expect(next.revealed).toBe(true);
    expect(next.transcript).toBe("full");
  });

  it("dictado parcial derivado se sirve como tarea directa de producción", () => {
    const partialDictationFlow: ListeningFlowStep[] = [
      { stage: "while2", task: "production", transcript_state_inicial: "hidden", allow_skip: false, requires_audio: true },
    ];
    const q = question({ flow: partialDictationFlow });
    expect(isProductionFlow(q)).toBe(true);
    expect(initialFlow(q).stage).toBe("while2");
    // Al igual que un dictado: al completar la tarea de producción finaliza.
    const done = advanceToNext(initialFlow(q), partialDictationFlow);
    expect(done.finished).toBe(true);
  });

  it("reintento con apoyo tras fallo en cloze (política A1 on_first_fail)", () => {
    let state = initialFlow(question({ flow: derivedMcqFlow("cloze") }));
    state = advanceToNext(state, derivedMcqFlow("cloze"));
    state = advanceToNext(state, derivedMcqFlow("cloze"));
    const retry = completeStageWithAnswer(
      state,
      false,
      A1_POLICY,
      derivedMcqFlow("cloze"),
    );
    expect(retry.stage).toBe("while2");
    expect(retry.attemptCount).toBe(1);
    expect(retry.transcript).toBe("full"); // apoyo visible en el reintento
  });
});
