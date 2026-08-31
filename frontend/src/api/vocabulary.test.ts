import { afterEach, describe, expect, it, vi } from "vitest";
import { getLexicon } from "./vocabulary";

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
});
