import { afterEach, describe, expect, it, vi } from "vitest";
import {
  addVocabularyBulk,
  addVocabularyItem,
  enrollVocabCollection,
  getDrillCandidates,
  getDrillRecallPrompt,
  getDrillSentenceContext,
  getLexicon,
  getRetentionDue,
  listVocabCollections,
  lookupDictionaryWord,
  markDrillAbandoned,
  markDrillStarted,
  reviewRetentionCard,
  setVocabularyTranslation,
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

  it("getLexicon llama sin user_id en la query", async () => {
    const fn = mockFetch({ summary: { total: 0 }, items: [] });
    await getLexicon("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/lexicon");
  });

  it("lookupDictionaryWord hace POST a /dictionary, body {word} y dirección", async () => {
    const fn = mockFetch({});
    await lookupDictionaryWord("u1", "travel");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/dictionary");
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

  it("getDrillCandidates llama con limit", async () => {
    const fn = mockFetch({ words: [] });
    await getDrillCandidates("u1", 6);
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/drill/candidates?limit=6");
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
    expect(url).toBe("/api/vocabulary/drill/attempt");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    const form = init.body as FormData;
    expect(form.get("word")).toBe("travel");
    expect(form.get("file")).not.toBeNull();
  });

  it("getDrillSentenceContext llama con word", async () => {
    const fn = mockFetch({ word: "travel", phrase: "x", source: "template" });
    await getDrillSentenceContext("u1", "travel");
    const [url] = fn.mock.calls[0];
    expect(url).toBe(
      "/api/vocabulary/drill/sentence-context?word=travel",
    );
  });

  it("submitDrillSentenceAttempt sube word + audio en multipart", async () => {
    const fn = mockFetch({ word: "travel", passed: true });
    const blob = new Blob(["fake"], { type: "audio/webm" });
    await submitDrillSentenceAttempt("u1", "travel", blob);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/drill/sentence-attempt");
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
    expect(url).toBe("/api/vocabulary/drill/write-attempt");
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
    expect(url).toBe("/api/vocabulary/drill/decision-lifecycle");
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

  it("addVocabularyItem POST /items", async () => {
    const fn = mockFetch({ added: ["ticket"], item: { word: "ticket" } });
    await addVocabularyItem("u1", "ticket", { translation: "billete" });
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/items");
    expect(JSON.parse(init.body as string)).toEqual({
      word: "ticket",
      translation: "billete",
      collection_id: null,
    });
  });

  it("addVocabularyBulk POST /items/bulk", async () => {
    const fn = mockFetch({ added: ["a"], count: 1, collection_id: 1 });
    await addVocabularyBulk("u1", "a\nb", { title: "Basics" });
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/items/bulk");
    expect(JSON.parse(init.body as string).title).toBe("Basics");
  });

  it("setVocabularyTranslation PATCH /items con {word, translation} (V3.80.0)", async () => {
    const fn = mockFetch({ word: "anchor", translation: "ancla", updated: true });
    const out = await setVocabularyTranslation("u1", "anchor", "ancla");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/items");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({
      word: "anchor",
      translation: "ancla",
    });
    // El resultado se devuelve tal cual: el llamante necesita saber si se
    // actualizó de verdad para no pintar una corrección que no se guardó.
    expect(out.updated).toBe(true);
  });

  it("setVocabularyTranslation admite borrar la propia con '' (V3.80.0)", async () => {
    const fn = mockFetch({ word: "anchor", translation: "", updated: true });
    await setVocabularyTranslation("u1", "anchor", "");
    const [, init] = fn.mock.calls[0];
    expect(JSON.parse(init.body as string).translation).toBe("");
  });

  it("listVocabCollections y enrollVocabCollection", async () => {
    const listFn = mockFetch({ collections: [] });
    await listVocabCollections("u1");
    expect(listFn.mock.calls[0][0]).toBe("/api/vocabulary/collections");

    const enrollFn = mockFetch({ collection_id: 3, added: [], count: 0 });
    await enrollVocabCollection("u1", 3);
    expect(enrollFn.mock.calls[0][0]).toBe(
      "/api/vocabulary/collections/3/enroll",
    );
  });

  it("getRetentionDue y reviewRetentionCard", async () => {
    const dueFn = mockFetch({ due_count: 0, items: [], limit: 15 });
    await getRetentionDue("u1", { limit: 15, collectionId: 2 });
    expect(dueFn.mock.calls[0][0]).toBe(
      "/api/vocabulary/retention/due?limit=15&collection_id=2",
    );

    const reviewFn = mockFetch({ word: "ticket", grade: 3, reps: 1 });
    await reviewRetentionCard("u1", "ticket", 3);
    const [url, init] = reviewFn.mock.calls[0];
    expect(url).toBe("/api/vocabulary/retention/review");
    expect(JSON.parse(init.body as string)).toEqual({
      word: "ticket",
      grade: 3,
    });
  });
});
