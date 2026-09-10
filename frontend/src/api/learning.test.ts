import { afterEach, describe, expect, it, vi } from "vitest";
import { analyzeText, getEvents, getProfile, getReviewQueue } from "./learning";
import type { ReviewQueue } from "../types/api";

function mockFetch(ok: boolean, data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

const QUEUE: ReviewQueue = {
  due_count: 1,
  fsrs_version: "2.11.0-lite",
  items: [
    {
      word: "river",
      lexical_unit: "river",
      cefr: "A1",
      kind: "word",
      due_at: "2026-09-09T10:00:00+00:00",
      state: "review",
      stability: 3.0,
      retrievability: 0.6,
      elapsed_days: 4.0,
      activity: "recall",
      reason: "no_recall_evidence",
      competence: null,
      evidence: {
        attempts: 1,
        successes: 0,
        distinct_success_days: 0,
        intervals: [],
        success_rate: 0,
        independent_successes: 0,
        independent_success_days: 0,
        recall_rungs: {},
        support_levels: {},
        error_types: { wrong_word: 1 },
        mean_response_time_ms: null,
      },
    },
  ],
};

describe("learning api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getProfile llama con user_id en la query", async () => {
    const fn = mockFetch(true, { user_id: "u1", estimated_level: "A2" });
    await getProfile("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/profile?user_id=u1");
  });

  it("analyzeText llama a vocabulario y gramática con el texto", async () => {
    const fn = mockFetch(true, { words: [] });
    await analyzeText("hi", "u1");
    const urls = fn.mock.calls.map((c) => c[0] as string);
    expect(urls).toContain("/api/vocabulary/analyze?user_id=u1");
    expect(urls).toContain("/api/grammar/analyze?user_id=u1");

    const bodies = fn.mock.calls.map((c) => JSON.parse(c[1].body as string));
    expect(bodies.every((b) => b.text === "hi")).toBe(true);
  });

  it("getEvents llama con user_id en la query", async () => {
    const fn = mockFetch(true, []);
    await getEvents("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/learning/events?user_id=u1");
  });

  it("getReviewQueue pide la cola de repaso con user_id y límite", async () => {
    const fn = mockFetch(true, QUEUE);
    const out = await getReviewQueue("u1", 5);
    expect(fn.mock.calls[0][0]).toBe(
      "/api/learning/review?user_id=u1&limit=5",
    );
    expect(out).toEqual(QUEUE);
  });

  it("getReviewQueue usa 20 como límite por defecto", async () => {
    const fn = mockFetch(true, { due_count: 0, items: [], fsrs_version: "" });
    await getReviewQueue("u1");
    expect(fn.mock.calls[0][0]).toBe(
      "/api/learning/review?user_id=u1&limit=20",
    );
  });
});
