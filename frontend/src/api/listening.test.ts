import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getListeningDiagnostic,
  getListeningQuestion,
  getListeningStats,
  submitListeningAnswer,
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
});
