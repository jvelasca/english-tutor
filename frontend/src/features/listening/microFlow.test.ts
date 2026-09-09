import { describe, expect, it } from "vitest";
import type {
  ListeningFlowStep,
  ListeningQuestion,
  ListeningTranscriptPolicy,
} from "../../types/api";
import {
  advanceToNext,
  activeSentenceIndex,
  activeWordIndex,
  completeShadowing,
  completeStageWithAnswer,
  currentStep,
  failedWordTiming,
  firstFailedWord,
  flowOf,
  hasFlow,
  initialFlow,
  isAnswering,
  isProductionFlow,
  revealFull,
  revealSentenceIndexes,
  retryStage,
  scaleWordTimings,
  timingsOf,
  variantTimeScale,
  wordTimingsOf,
  wordTokensOf,
  wordsForSentence,
  type SentenceTiming,
  type TranscriptState,
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

describe("microFlow: karaoke palabra a palabra (V3.29, Fase 3)", () => {
  const WORD_TIMINGS = [
    { index: 0, text: "Hello", start: 0, end: 0.4, sentence: 0 },
    { index: 1, text: "world", start: 0.5, end: 0.9, sentence: 0 },
    { index: 2, text: "Nice", start: 1.1, end: 1.5, sentence: 1 },
    { index: 3, text: "day", start: 1.6, end: 2.0, sentence: 1 },
  ];
  const SENTENCE_TIMINGS: SentenceTiming[] = [
    { index: 0, start: 0, end: 1, text: "Hello world.", sync: "coarse_heuristic" },
    { index: 1, start: 1, end: 2, text: "Nice day.", sync: "coarse_heuristic" },
  ];

  it("wordTimingsOf expone las palabras del backend (o lista vacía)", () => {
    expect(wordTimingsOf(question({ flow: receptiveFlow }))).toEqual([]);
    const q = question({ flow: receptiveFlow, wordTimings: WORD_TIMINGS });
    expect(wordTimingsOf(q)).toHaveLength(4);
  });

  it("activeWordIndex: palabra activa según currentTime (regla monótona)", () => {
    expect(activeWordIndex(WORD_TIMINGS, 0)).toBe(0);
    expect(activeWordIndex(WORD_TIMINGS, 0.2)).toBe(0);
    expect(activeWordIndex(WORD_TIMINGS, 0.5)).toBe(1);
    expect(activeWordIndex(WORD_TIMINGS, 1.6)).toBe(3);
    // Tras el final se mantiene la última palabra (resaltado estable).
    expect(activeWordIndex(WORD_TIMINGS, 5)).toBe(3);
    // Sin timings o antes del primer start → null.
    expect(activeWordIndex([], 1)).toBeNull();
    expect(activeWordIndex(WORD_TIMINGS, -1)).toBeNull();
    expect(activeWordIndex(WORD_TIMINGS, Number.NaN)).toBe(0);
  });

  it("wordsForSentence filtra las palabras de una frase", () => {
    expect(wordsForSentence(WORD_TIMINGS, 0).map((w) => w.text)).toEqual([
      "Hello",
      "world",
    ]);
    expect(wordsForSentence(WORD_TIMINGS, 1)).toHaveLength(2);
    expect(wordsForSentence(WORD_TIMINGS, 9)).toEqual([]);
  });

  it("scaleWordTimings escala slow/fast sin mutar el original", () => {
    const slow = scaleWordTimings(WORD_TIMINGS, 1.5);
    expect(slow[0].start).toBe(0);
    expect(slow[1].start).toBe(0.75); // 0.5 * 1.5
    expect(slow[3].end).toBe(3); // 2.0 * 1.5
    // El original queda intacto.
    expect(WORD_TIMINGS[1].start).toBe(0.5);
    // Factor 1 devuelve la misma referencia (sin copia innecesaria).
    expect(scaleWordTimings(WORD_TIMINGS, 1)).toBe(WORD_TIMINGS);
    // Factor inválido → sin escalado.
    expect(scaleWordTimings(WORD_TIMINGS, Number.NaN)).toBe(WORD_TIMINGS);
    expect(scaleWordTimings(WORD_TIMINGS, -2)).toBe(WORD_TIMINGS);
  });

  it("variantTimeScale deriva el factor de las variantes (normal/slow/fast)", () => {
    const variants = [
      { variant: "slow", speech_rate: 105, label: "Slow" },
      { variant: "normal", speech_rate: 140, label: "Normal" },
      { variant: "fast", speech_rate: 175, label: "Fast" },
    ];
    const q = question({ variants });
    expect(variantTimeScale(q, "normal")).toBe(1);
    expect(variantTimeScale(q, "slow")).toBeCloseTo(140 / 105, 5);
    expect(variantTimeScale(q, "fast")).toBeCloseTo(140 / 175, 5);
    // Sin tasas declaradas no hay escalado (1) para cualquier variante.
    const noRates = question({ variants: [{ variant: "slow", speech_rate: 0, label: "Slow" }] });
    expect(variantTimeScale(noRates, "slow")).toBe(1);
    expect(variantTimeScale(question(), "slow")).toBe(1);
  });

  it("revelado por frase funciona con palabras (full → todo, partial → frase)", () => {
    const revealed = (state: TranscriptState, t: number) => {
      const active = activeSentenceIndex(SENTENCE_TIMINGS, t);
      const indexes = revealSentenceIndexes(state, SENTENCE_TIMINGS, active);
      return WORD_TIMINGS.filter((w) => indexes.includes(w.sentence));
    };
    expect(revealed("full", 0.2).map((w) => w.text)).toEqual([
      "Hello",
      "world",
      "Nice",
      "day",
    ]);
    expect(revealed("partial", 0.2).map((w) => w.text)).toEqual([
      "Hello",
      "world",
    ]);
    expect(revealed("partial", 1.8).map((w) => w.text)).toEqual(["Nice", "day"]);
  });
});

describe("microFlow: salto a la palabra fallada (V3.29, Fase 3, P6)", () => {
  const WORD_TIMINGS = [
    { index: 0, text: "Hello", start: 0, end: 0.4, sentence: 0 },
    { index: 1, text: "world", start: 0.5, end: 0.9, sentence: 0 },
    { index: 2, text: "Nice", start: 1.1, end: 1.5, sentence: 1 },
    { index: 3, text: "day", start: 1.6, end: 2.0, sentence: 1 },
  ];
  const SENTENCE_TIMINGS: SentenceTiming[] = [
    { index: 0, start: 0, end: 1, text: "Hello world.", sync: "coarse_heuristic" },
    { index: 1, start: 1, end: 2, text: "Nice day.", sync: "coarse_heuristic" },
  ];

  it("wordTokensOf normaliza grafías (mayúsculas/puntuación, apóstrofo)", () => {
    expect(wordTokensOf("Gonna go?")).toEqual(["gonna", "go"]);
    expect(wordTokensOf("I'm fine!")).toEqual(["i'm", "fine"]);
    expect(wordTokensOf("  ")).toEqual([]);
    expect(wordTokensOf("")).toEqual([]);
  });

  it("firstFailedWord: prioriza missing y cae a substituted.expected", () => {
    expect(
      firstFailedWord({
        missing: ["hello"],
        substituted: [{ expected: "world", heard: "word" }],
      }),
    ).toBe("hello");
    expect(
      firstFailedWord({
        missing: [],
        substituted: [{ expected: "world", heard: "word" }],
      }),
    ).toBe("world");
    // Sin fallos de palabra o breakdown inesperado → null.
    expect(firstFailedWord({ missing: [], substituted: [] })).toBeNull();
    expect(firstFailedWord(null)).toBeNull();
    expect(firstFailedWord(undefined)).toBeNull();
    expect(firstFailedWord({})).toBeNull();
  });

  it("mapea una palabra del dictado a su timing (busca la primera aparición)", () => {
    const ref = failedWordTiming("world", WORD_TIMINGS, SENTENCE_TIMINGS);
    expect(ref).toEqual({ text: "world", start: 0.5, end: 0.9 });
    // Grafía distinta pero mismo token (mayúsculas / puntuación).
    const withPunct = failedWordTiming("World,", WORD_TIMINGS, SENTENCE_TIMINGS);
    expect(withPunct?.start).toBe(0.5);
  });

  it("mapea una frase diana completa como secuencia contigua", () => {
    const ref = failedWordTiming("Nice day", WORD_TIMINGS, SENTENCE_TIMINGS);
    expect(ref).toEqual({ text: "Nice day", start: 1.1, end: 2.0 });
  });

  it("cae a la frase contenedora cuando el token no está en el sidecar", () => {
    // El ASR oyó la reducción "gonna" pero el target usa la expansión
    // canónica "going to": sin par en los timings → aproximación por frase.
    const reducedTimings = [
      { index: 0, text: "I'm", start: 0, end: 0.4, sentence: 0 },
      { index: 1, text: "gonna", start: 0.5, end: 0.9, sentence: 0 },
      { index: 2, text: "leave", start: 1.0, end: 1.4, sentence: 0 },
    ];
    const sentences: SentenceTiming[] = [
      {
        index: 0,
        start: 0,
        end: 1.5,
        text: "I'm going to leave.",
        sync: "coarse_heuristic",
      },
    ];
    const ref = failedWordTiming("going", reducedTimings, sentences);
    expect(ref).toEqual({ text: "I'm going to leave.", start: 0, end: 1.5 });
  });

  it("sin respaldo en palabras ni frases devuelve null (degradación)", () => {
    expect(failedWordTiming("zebra", WORD_TIMINGS, SENTENCE_TIMINGS)).toBeNull();
    expect(failedWordTiming("", WORD_TIMINGS, SENTENCE_TIMINGS)).toBeNull();
    expect(failedWordTiming("world", [], [])).toBeNull();
    expect(failedWordTiming("world", WORD_TIMINGS, [])).toEqual({
      text: "world",
      start: 0.5,
      end: 0.9,
    });
  });
});
