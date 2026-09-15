import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getDrillCandidates,
  getDrillRecallPrompt,
  getDrillSentenceContext,
  getLexicon,
  lookupDictionaryWord,
  markDrillAbandoned,
  markDrillStarted,
  submitDrillAttempt,
  submitDrillRecallAttempt,
  submitDrillSentenceAttempt,
  submitDrillWriteAttempt,
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

  it("lookupDictionaryWord hace POST a /dictionary con user_id, body {word} y dirección", async () => {
    const fn = mockFetch({});
    await lookupDictionaryWord("u1", "travel");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/dictionary?user_id=u1");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/json",
    );
    // V3.39: la dirección por defecto es EN→ES (contrato aditivo).
    expect(JSON.parse(init.body as string)).toEqual({
      word: "travel",
      direction: "en-es",
    });
  });

  it("lookupDictionaryWord envía la dirección inversa ES→EN", async () => {
    const fn = mockFetch({});
    await lookupDictionaryWord("u1", "casa", "es-en");
    const [, init] = fn.mock.calls[0];
    expect(JSON.parse(init.body as string)).toEqual({
      word: "casa",
      direction: "es-en",
    });
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

  it("submitDrillWriteAttempt envía la frase propia, la latencia y la decisión (V3.39/V3.68)", async () => {
    const fn = mockFetch({
      word: "travel",
      used_word: true,
      word_count: 7,
      passed: true,
    });
    await submitDrillWriteAttempt(
      "u1",
      "travel",
      "I usually travel by train in summer.",
      4200,
      "decision-1",
    );
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/drill/write-attempt?user_id=u1");
    expect(init.method).toBe("POST");
    // V3.68 (P1-02): el `decision_id` viaja siempre (vacío sin decisión servida).
    expect(JSON.parse(init.body as string)).toEqual({
      word: "travel",
      text: "I usually travel by train in summer.",
      response_time_ms: 4200,
      decision_id: "decision-1",
    });
  });

  it("el drill marca la decisión servida y cierra el ciclo con el id (V3.68)", async () => {
    const fn = mockFetch({ word: "travel", phrase: "I travel." });
    await getDrillSentenceContext("u1", "travel", "decision-1");
    await getDrillRecallPrompt("u1", "travel", "definition", "decision-1");
    await submitDrillRecallAttempt(
      "u1",
      "travel",
      "travel",
      1000,
      "definition",
      "decision-1",
    );
    // El `decision_id` viaja en los GET (query) y en los POST (body).
    const calls = fn.mock.calls.map(([url, init]) => ({
      url: String(url),
      body: init?.body ? String(init.body) : "",
    }));
    expect(calls[0].url).toContain("decision_id=decision-1");
    expect(calls[1].url).toContain("decision_id=decision-1");
    expect(calls[2].body).toContain("decision-1");
  });

  it("sin decisionId el drill no declara nada (diccionario) (V3.68)", async () => {
    const fn = mockFetch({ word: "travel", phrase: "I travel.", source: "template" });
    await getDrillSentenceContext("u1", "travel");
    const [url] = fn.mock.calls[0];
    expect(String(url)).not.toContain("decision_id");
  });

  it("markDrillStarted/Abandoned postean el evento y tragan el fallo (V3.68)", async () => {
    const fn = mockFetch({ applied: true });
    const applied = await markDrillStarted("u1", "decision-1", {
      targetId: "travel",
    });
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/drill/decision-lifecycle?user_id=u1");
    expect(JSON.parse(init.body as string)).toEqual({
      decision_id: "decision-1",
      event: "started",
      target_id: "travel",
      activity: "",
    });
    expect(applied).toBe(true);
    // Best-effort: el ciclo de vida nunca rompe el drill.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("offline")),
    );
    expect(await markDrillAbandoned("u1", "decision-1")).toBe(false);
    // Sin decisión no hay llamada (drill abierto desde el diccionario).
    const empty = vi.fn();
    vi.stubGlobal("fetch", empty);
    expect(await markDrillStarted("u1", "")).toBe(false);
    expect(empty).not.toHaveBeenCalled();
  });
});
