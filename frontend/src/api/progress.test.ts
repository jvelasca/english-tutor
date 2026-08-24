import { afterEach, describe, expect, it, vi } from "vitest";
import { getProgress, getProgressHistory } from "./progress";

function mockFetch(ok: boolean, data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("progress api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getProgressHistory llama con user_id y bucket en la query", async () => {
    const fn = mockFetch(true, { user_id: "u1", bucket: "week", series: [] });
    await getProgressHistory("u1", "week");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/progress/history?user_id=u1&bucket=week");
  });

  it("getProgress llama con user_id en la query", async () => {
    const fn = mockFetch(true, { user_id: "u1", conversations: 0 });
    await getProgress("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/progress?user_id=u1");
  });
});
