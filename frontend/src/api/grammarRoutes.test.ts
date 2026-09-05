import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getGrammarLevelItems,
  getGrammarQuestion,
  getGrammarStats,
  submitGrammarAttempt,
} from "./grammarRoutes";

function mockFetch(ok: boolean, data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("grammarRoutes api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getGrammarQuestion llama con user_id en la query", async () => {
    const fn = mockFetch(true, {
      check_id: "a1-m01-u01-l01-o01-c01",
      level: "A1",
      topic: "Introductions",
      prompt: "Choose the correct sentence:",
      options: ["I am from Spain.", "I is from Spain."],
    });
    await getGrammarQuestion("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/grammar/routes/question?user_id=u1");
  });

  it("getGrammarQuestion añade level y mode=failed solo cuando se piden", async () => {
    const fn = mockFetch(true, {
      check_id: "a1-m01-u01-l01-o01-c01",
      level: "A1",
      prompt: "P",
      options: ["a", "b"],
    });
    await getGrammarQuestion("u1", "A1", "failed");
    const [url] = fn.mock.calls[0];
    expect(url).toBe(
      "/api/grammar/routes/question?user_id=u1&level=A1&mode=failed",
    );
  });

  it("getGrammarQuestion con mode all omite el parámetro", async () => {
    const fn = mockFetch(true, {
      check_id: "a1-m01-u01-l01-o01-c01",
      level: "A1",
      prompt: "P",
      options: ["a", "b"],
    });
    await getGrammarQuestion("u1", "A1", "all");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/grammar/routes/question?user_id=u1&level=A1");
  });

  it("getGrammarStats llama con user_id en la query", async () => {
    const fn = mockFetch(true, { attempts: 1, passed: 1, accuracy: 100 });
    await getGrammarStats("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/grammar/routes/stats?user_id=u1");
  });

  it("getGrammarLevelItems llama a /items con user_id y level", async () => {
    const fn = mockFetch(true, {
      level: "A1",
      total: 2,
      mastered: 0,
      failed: 1,
      unseen: 1,
      completed: false,
      items: [],
    });
    await getGrammarLevelItems("u1", "A1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/grammar/routes/items?user_id=u1&level=A1");
  });

  it("submitGrammarAttempt envía JSON con check_id y selected_index", async () => {
    const fn = mockFetch(true, {
      check_id: "a1-m01-u01-l01-o01-c01",
      level: "A1",
      topic: "Introductions",
      prompt: "Choose the correct sentence:",
      options: ["I am from Spain.", "I is from Spain."],
      correct_index: 0,
      selected_index: 0,
      passed: true,
      score: 100,
    });
    await submitGrammarAttempt("u1", "a1-m01-u01-l01-o01-c01", 0);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/grammar/routes/attempt?user_id=u1");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      check_id: "a1-m01-u01-l01-o01-c01",
      selected_index: 0,
    });
  });
});
