import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getVocabularyLevelItems,
  getVocabularyQuestion,
  getVocabularyStats,
  submitVocabularyAttempt,
} from "./vocabularyRoutes";

function mockFetch(ok: boolean, data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("vocabularyRoutes api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getVocabularyQuestion llama con user_id en la query", async () => {
    const fn = mockFetch(true, {
      check_id: "a1-m01-u01-l01-o01-c01",
      level: "A1",
      topic: "Introductions",
      prompt: "Which word means 'país'?",
      options: ["name", "country", "city"],
    });
    await getVocabularyQuestion("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/routes/question?user_id=u1");
  });

  it("getVocabularyQuestion añade level y mode=failed solo cuando se piden", async () => {
    const fn = mockFetch(true, {
      check_id: "a1-m01-u01-l01-o01-c01",
      level: "A1",
      prompt: "P",
      options: ["a", "b"],
    });
    await getVocabularyQuestion("u1", "A1", "failed");
    const [url] = fn.mock.calls[0];
    expect(url).toBe(
      "/api/vocabulary/routes/question?user_id=u1&level=A1&mode=failed",
    );
  });

  it("getVocabularyQuestion con mode all omite el parámetro", async () => {
    const fn = mockFetch(true, {
      check_id: "a1-m01-u01-l01-o01-c01",
      level: "A1",
      prompt: "P",
      options: ["a", "b"],
    });
    await getVocabularyQuestion("u1", "A1", "all");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/routes/question?user_id=u1&level=A1");
  });

  it("getVocabularyStats llama con user_id en la query", async () => {
    const fn = mockFetch(true, { attempts: 1, passed: 1, accuracy: 100 });
    await getVocabularyStats("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/routes/stats?user_id=u1");
  });

  it("getVocabularyLevelItems llama a /items con user_id y level", async () => {
    const fn = mockFetch(true, {
      level: "A1",
      total: 2,
      mastered: 0,
      failed: 1,
      unseen: 1,
      completed: false,
      items: [],
    });
    await getVocabularyLevelItems("u1", "A1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/routes/items?user_id=u1&level=A1");
  });

  it("submitVocabularyAttempt envía JSON con check_id y selected_index", async () => {
    const fn = mockFetch(true, {
      check_id: "a1-m01-u01-l01-o01-c01",
      level: "A1",
      topic: "Introductions",
      prompt: "Which word means 'país'?",
      options: ["name", "country", "city"],
      correct_index: 1,
      selected_index: 1,
      passed: true,
      score: 100,
    });
    await submitVocabularyAttempt("u1", "a1-m01-u01-l01-o01-c01", 1);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/routes/attempt?user_id=u1");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      check_id: "a1-m01-u01-l01-o01-c01",
      selected_index: 1,
    });
  });
});
