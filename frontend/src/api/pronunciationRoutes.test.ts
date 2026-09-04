import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getPronunciationLevelItems,
  getPronunciationQuestion,
  getPronunciationStats,
  submitPronunciationAttempt,
} from "./pronunciationRoutes";

function mockFetch(ok: boolean, data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("pronunciationRoutes api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getPronunciationQuestion llama con user_id en la query", async () => {
    const fn = mockFetch(true, { id: "pr-A1-0001", level: "A1", script: "Hi" });
    await getPronunciationQuestion("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/pronunciation/routes/question?user_id=u1");
  });

  it("getPronunciationQuestion añade level y mode=failed solo cuando se piden", async () => {
    const fn = mockFetch(true, { id: "pr-A1-0001", level: "A1", script: "Hi" });
    await getPronunciationQuestion("u1", "A1", "failed");
    const [url] = fn.mock.calls[0];
    expect(url).toBe(
      "/api/pronunciation/routes/question?user_id=u1&level=A1&mode=failed",
    );
  });

  it("getPronunciationQuestion con mode all omite el parámetro", async () => {
    const fn = mockFetch(true, { id: "pr-A1-0001", level: "A1", script: "Hi" });
    await getPronunciationQuestion("u1", "A1", "all");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/pronunciation/routes/question?user_id=u1&level=A1");
  });

  it("getPronunciationStats llama con user_id en la query", async () => {
    const fn = mockFetch(true, { attempts: 1, passed: 1, accuracy: 100 });
    await getPronunciationStats("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/pronunciation/routes/stats?user_id=u1");
  });

  it("getPronunciationLevelItems llama a /items con user_id y level", async () => {
    const fn = mockFetch(true, {
      level: "A1",
      total: 2,
      mastered: 0,
      failed: 1,
      unseen: 1,
      completed: false,
      items: [],
    });
    await getPronunciationLevelItems("u1", "A1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/pronunciation/routes/items?user_id=u1&level=A1");
  });

  it("submitPronunciationAttempt envía FormData con file y phrase_id", async () => {
    const fn = mockFetch(true, {
      phrase_id: "pr-A1-0001",
      level: "A1",
      script: "Hello, nice to meet you.",
      heard: "Hello, nice to meet you",
      score: 100,
      grade: "good",
      passed: true,
      word_accuracy: 100,
      phonetic_score: 100,
      phoneme_accuracy_proxy: 100,
      prosody_proxy: 100,
      pronunciation_source: "transcript",
      breakdown: { correct: [], missing: [], extra: [], substituted: [], total: 0 },
      phoneme_breakdown: {
        correct: [],
        missing: [],
        extra: [],
        substituted: [],
        total: 0,
      },
      fluency: { word_count: 4, duration_seconds: 2, wpm: 120, level: "good" },
      topic: "Greetings",
      difficulty: 1,
    });
    const blob = new Blob(["audio"], { type: "audio/webm" });
    await submitPronunciationAttempt("u1", "pr-A1-0001", blob);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/pronunciation/routes/attempt?user_id=u1");
    expect(init.body).toBeInstanceOf(FormData);
    const form = init.body as FormData;
    expect(form.get("phrase_id")).toBe("pr-A1-0001");
    const file = form.get("file");
    expect(file).toBeInstanceOf(File);
    expect((file as File).name).toBe("audio.webm");
    expect((file as Blob).type).toBe("audio/webm");
    expect(await (file as Blob).text()).toBe("audio");
  });
});
