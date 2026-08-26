import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getListeningAudioUrl,
  getListeningDiagnostic,
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

  it("getListeningQuestion llama con user_id en la query", async () => {
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
    expect(url).toBe("/api/listening/question?user_id=u1");
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
    expect(url).toBe("/api/listening/answer?user_id=u1");
    expect(JSON.parse(init.body as string)).toEqual({
      question_id: "l1",
      answer_index: 1,
      response_time_ms: 1200,
      replay_count: 2,
    });
  });

  it("getListeningStats llama con user_id en la query", async () => {
    const fn = mockFetch(true, { attempts: 1, correct: 1, accuracy: 100 });
    await getListeningStats("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/stats?user_id=u1");
  });

  it("getListeningDiagnostic llama con user_id en la query", async () => {
    const fn = mockFetch(true, {
      subskills: [],
      weak: [],
      recommendation: "All listening sub-skills look strong.",
    });
    await getListeningDiagnostic("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/diagnostic?user_id=u1");
  });

  it("getListeningAudioUrl construye la URL del audio con user_id", () => {
    expect(getListeningAudioUrl("l1", "u1")).toBe(
      "/api/listening/audio/l1?user_id=u1",
    );
  });

  it("getListeningAudioUrl añade variant cuando se pasa (y omite normal)", () => {
    expect(getListeningAudioUrl("l1", "u1", "fast")).toBe(
      "/api/listening/audio/l1?user_id=u1&variant=fast",
    );
    // La variante por defecto no cambia la URL (retrocompatible).
    expect(getListeningAudioUrl("l1", "u1", "normal")).toBe(
      "/api/listening/audio/l1?user_id=u1",
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
    expect(url).toBe("/api/listening/dictation?user_id=u1");
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
    expect(url).toBe("/api/listening/shadowing?user_id=u1");
    expect(JSON.parse(init.body as string)).toEqual({
      question_id: "l19",
      transcript: "could you repeat that",
    });
  });
});
