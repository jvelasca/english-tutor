import { afterEach, describe, expect, it, vi } from "vitest";
import {
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
      script: "Hi",
      question: "Q",
      options: ["a", "b"],
    });
    await getListeningQuestion("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/question?user_id=u1");
  });

  it("submitListeningAnswer envía question_id y answer_index", async () => {
    const fn = mockFetch(true, {
      question_id: "l1",
      correct: true,
      correct_index: 1,
      level: "A1",
    });
    await submitListeningAnswer("u1", "l1", 1);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/answer?user_id=u1");
    expect(JSON.parse(init.body as string)).toEqual({
      question_id: "l1",
      answer_index: 1,
    });
  });

  it("getListeningStats llama con user_id en la query", async () => {
    const fn = mockFetch(true, { attempts: 1, correct: 1, accuracy: 100 });
    await getListeningStats("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/listening/stats?user_id=u1");
  });
});
