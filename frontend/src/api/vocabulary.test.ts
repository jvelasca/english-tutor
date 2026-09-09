import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getDrillCandidates,
  getDrillSentenceContext,
  getLexicon,
  lookupDictionaryWord,
  submitDrillAttempt,
  submitDrillSentenceAttempt,
} from "./vocabulary";

function mockFetch(data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok: true, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("vocabulary api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getLexicon llama con user_id en la query", async () => {
    const fn = mockFetch({ summary: { total: 0 }, items: [] });
    await getLexicon("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/lexicon?user_id=u1");
  });

  it("lookupDictionaryWord hace POST a /dictionary con user_id y body {word}", async () => {
    const fn = mockFetch({});
    await lookupDictionaryWord("u1", "travel");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/dictionary?user_id=u1");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/json",
    );
    expect(JSON.parse(init.body as string)).toEqual({ word: "travel" });
  });

  it("getDrillCandidates llama con user_id y limit", async () => {
    const fn = mockFetch({ words: [] });
    await getDrillCandidates("u1", 6);
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/drill/candidates?user_id=u1&limit=6");
  });

  it("submitDrillAttempt sube word + audio en multipart", async () => {
    const fn = mockFetch({
      word: "travel",
      produced: true,
      heard: "travel",
      score: 100,
    });
    const blob = new Blob(["fake"], { type: "audio/webm" });
    await submitDrillAttempt("u1", "travel", blob);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/drill/attempt?user_id=u1");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    const form = init.body as FormData;
    expect(form.get("word")).toBe("travel");
    expect(form.get("file")).not.toBeNull();
  });

  it("getDrillSentenceContext llama con user_id y word", async () => {
    const fn = mockFetch({ word: "travel", phrase: "x", source: "template" });
    await getDrillSentenceContext("u1", "travel");
    const [url] = fn.mock.calls[0];
    expect(url).toBe(
      "/api/vocabulary/drill/sentence-context?user_id=u1&word=travel",
    );
  });

  it("submitDrillSentenceAttempt sube word + audio en multipart", async () => {
    const fn = mockFetch({ word: "travel", passed: true });
    const blob = new Blob(["fake"], { type: "audio/webm" });
    await submitDrillSentenceAttempt("u1", "travel", blob);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/drill/sentence-attempt?user_id=u1");
    expect(init.method).toBe("POST");
    const form = init.body as FormData;
    expect(form.get("word")).toBe("travel");
    expect(form.get("file")).not.toBeNull();
  });
});
