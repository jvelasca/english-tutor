import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getListeningAudioUrl,
  getListeningDiagnostic,
  getListeningLevelItems,
  getListeningQuestion,
  getListeningStats,
  submitListeningAnswer,
  submitListeningDictation,
  submitListeningShadowing,
} from "./listening";

function mockFetch(ok: boolean, data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("listening api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getListeningQuestion llama sin user_id en la query", async () => {
    const fn = mockFetch(true, {
      id: "l1",
      skill: "numbers",
      difficulty: 1,
      script: "Hi",
      question: "Q",
      options: ["a", "b"],
    });
    await getListeningQuestion("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/question");
  });

  it("submitListeningAnswer envía question_id, answer_index y métricas", async () => {
    const fn = mockFetch(true, {
      question_id: "l1",
      correct: true,
      correct_index: 1,
      level: "A1",
    });
    await submitListeningAnswer("u1", "l1", 1, 1200, 2);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/answer");
    expect(JSON.parse(init.body as string)).toEqual({
      question_id: "l1",
      answer_index: 1,
      response_time_ms: 1200,
      replay_count: 2,
    });
  });

  it("getListeningStats llama sin user_id en la query", async () => {
    const fn = mockFetch(true, { attempts: 1, correct: 1, accuracy: 100 });
    await getListeningStats("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/stats");
  });

  it("getListeningDiagnostic llama sin user_id en la query", async () => {
    const fn = mockFetch(true, {
      subskills: [],
      weak: [],
      recommendation: "All listening sub-skills look strong.",
    });
    await getListeningDiagnostic("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/diagnostic");
  });

  it("getListeningQuestion añade mode=failed solo cuando se pide", async () => {
    const fn = mockFetch(true, { id: "l1", level: "A1", script: "Hi" });
    await getListeningQuestion("u1", "A1", "failed");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/question?level=A1&mode=failed");
  });

  it("getListeningQuestion con level y sin mode no añade mode (retrocompatible)", async () => {
    const fn = mockFetch(true, { id: "l1", level: "A1", script: "Hi" });
    await getListeningQuestion("u1", "A1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/question?level=A1");
  });

  it("getListeningLevelItems llama a /items solo con level", async () => {
    const fn = mockFetch(true, {
      level: "A1",
      total: 2,
      mastered: 0,
      failed: 1,
      unseen: 1,
      completed: false,
      items: [],
    });
    await getListeningLevelItems("u1", "A1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/items?level=A1");
  });

  it("getListeningAudioUrl construye la URL del audio sin user_id", () => {
    expect(getListeningAudioUrl("l1", "u1")).toBe(
      "/api/listening/audio/l1",
    );
  });

  it("getListeningAudioUrl añade variant cuando se pasa (y omite normal)", () => {
    expect(getListeningAudioUrl("l1", "u1", "fast")).toBe(
      "/api/listening/audio/l1?variant=fast",
    );
    // La variante por defecto no cambia la URL (retrocompatible).
    expect(getListeningAudioUrl("l1", "u1", "normal")).toBe(
      "/api/listening/audio/l1",
    );
  });

  it("submitListeningDictation envía question_id y transcript", async () => {
    const fn = mockFetch(true, {
      question_id: "l18",
      task_type: "dictation",
      correct: true,
      score: 100,
    });
    await submitListeningDictation("u1", "l18", "hello world");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/dictation");
    expect(JSON.parse(init.body as string)).toEqual({
      question_id: "l18",
      transcript: "hello world",
    });
  });

  it("submitListeningShadowing envía question_id y transcript", async () => {
    const fn = mockFetch(true, {
      question_id: "l19",
      task_type: "shadowing",
      correct: true,
      score: 90,
    });
    await submitListeningShadowing("u1", "l19", "could you repeat that");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/shadowing");
    expect(JSON.parse(init.body as string)).toEqual({
      question_id: "l19",
      transcript: "could you repeat that",
    });
  });

  it("submitListeningShadowing envía señales auxiliares cuando existen", async () => {
    const fn = mockFetch(true, {
      question_id: "l19",
      task_type: "shadowing",
      correct: true,
      score: 90,
    });
    await submitListeningShadowing(
      "u1",
      "l19",
      "could you repeat that",
      {},
      { durationMs: 2340, speechRate: 152 },
    );
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/shadowing");
    expect(JSON.parse(init.body as string)).toEqual({
      question_id: "l19",
      transcript: "could you repeat that",
      shadowing_duration_ms: 2340,
      shadowing_speech_rate: 152,
    });
  });

  // V3.93.2: la ruta de producción también viaja con `attempt_id` para que el
  // backend deduplique el intento (y sin él no lo manda: cliente legacy).
  it("submitListeningDictation propaga attemptId cuando existe", async () => {
    const fn = mockFetch(true, {
      question_id: "l18",
      task_type: "dictation",
      correct: true,
      score: 100,
    });
    await submitListeningDictation("u1", "l18", "hello world", {
      attemptId: "uuid-p1",
    });
    const [, init] = fn.mock.calls[0];
    expect(JSON.parse(init.body as string)).toEqual({
      question_id: "l18",
      transcript: "hello world",
      attempt_id: "uuid-p1",
    });
  });

  it("submitListeningShadowing propaga attemptId junto a las señales", async () => {
    const fn = mockFetch(true, {
      question_id: "l19",
      task_type: "shadowing",
      correct: true,
      score: 90,
    });
    await submitListeningShadowing(
      "u1",
      "l19",
      "could you repeat that",
      { attemptId: "uuid-s1" },
      { durationMs: 2340 },
    );
    const [, init] = fn.mock.calls[0];
    expect(JSON.parse(init.body as string)).toEqual({
      question_id: "l19",
      transcript: "could you repeat that",
      shadowing_duration_ms: 2340,
      attempt_id: "uuid-s1",
    });
  });
});

// --- V3.92: el ítem servido llega en snake_case y la UI lo lee en camelCase ---
// Sin esta traga, `transcriptPolicy` era `undefined` y con él se caía la tarjeta
// de fallo de V3.89 (tres acciones) y el karaoke de V3.29. Aquí se fija contra la
// forma EXACTA que sirve el backend (`flow_for_question` + `coarse_sentence_timings`
// + `word_timings_for`), no contra un mock complaciente.
describe("getListeningQuestion normaliza el contrato del backend (V3.92)", () => {
  afterEach(() => vi.unstubAllGlobals());

  const RAW = {
    id: "l1",
    level: "A1",
    skill: "numbers",
    script: "It's a quarter past eight.",
    question: "Which time did you hear?",
    options: ["8:45", "8:15"],
    flow: [
      {
        stage: "while2",
        task: "native_question",
        transcript_state_inicial: "hidden",
        allow_skip: false,
        requires_audio: true,
      },
    ],
    transcript_policy: {
      revelation: "on_first_fail",
      max_attempts_per_stage: 2,
      allow_manual_reveal: true,
      shadowing_optional: true,
    },
    sentence_timings: [
      { index: 0, start: 0, end: 2.5, text: "It's a quarter past eight.", sync: "coarse_heuristic" },
    ],
    word_timings: [
      { index: 0, text: "It's", start: 0, end: 0.4, sentence: 0 },
    ],
  };

  it("traduce transcript_policy, sentence_timings y word_timings", async () => {
    mockFetch(true, RAW);
    const q = await getListeningQuestion("u1", "A1");

    expect(q.transcriptPolicy).toEqual({
      revelation: "on_first_fail",
      max_attempts_per_stage: 2,
      allow_manual_reveal: true,
      shadowing_optional: true,
    });
    // La política es lo que decide si quedan reintentos: sin ella la tarjeta de
    // fallo no se pinta y el alumno no ve «Continuar / Repasar ahora / Después».
    expect(q.transcriptPolicy?.max_attempts_per_stage).toBe(2);
    expect(q.sentenceTimings).toHaveLength(1);
    expect(q.wordTimings).toHaveLength(1);
    // `flow` ya venía con el nombre correcto y no se toca.
    expect(q.flow).toHaveLength(1);
  });

  it("no deja las claves crudas en el objeto que ve la UI", async () => {
    mockFetch(true, RAW);
    const q = (await getListeningQuestion("u1", "A1")) as unknown as Record<
      string,
      unknown
    >;
    expect("transcript_policy" in q).toBe(false);
    expect("sentence_timings" in q).toBe(false);
    expect("word_timings" in q).toBe(false);
  });

  it("un ítem sin flow ni timings no inventa política", async () => {
    mockFetch(true, { id: "l1", level: "A1", script: "Hi" });
    const q = await getListeningQuestion("u1", "A1");
    expect(q.transcriptPolicy).toBeUndefined();
    expect(q.sentenceTimings).toBeUndefined();
    expect(q.wordTimings).toBeUndefined();
  });
});
