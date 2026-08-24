import { afterEach, describe, expect, it, vi } from "vitest";
import { analyzeText, getEvents, getProfile } from "./learning";

function mockFetch(ok: boolean, data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("learning api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getProfile llama con user_id en la query", async () => {
    const fn = mockFetch(true, { user_id: "u1", cefr_level: "A2" });
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
});
