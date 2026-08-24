import { afterEach, describe, expect, it, vi } from "vitest";
import { deleteConversation, getConversation, saveConversation } from "./conversations";

function mockFetch(ok: boolean, data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("conversations api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getConversation llama con user_id en la query", async () => {
    const fn = mockFetch(true, { id: "c1", messages: [] });
    await getConversation("c1", "u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/conversations/c1?user_id=u1");
  });

  it("saveConversation usa PUT con el body correcto", async () => {
    const fn = mockFetch(true, { id: "c1", title: "T", messages: [] });
    await saveConversation("c1", "u1", "T", [{ role: "user", content: "hi" }]);
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/conversations/c1?user_id=u1");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({
      title: "T",
      messages: [{ role: "user", content: "hi" }],
    });
  });

  it("deleteConversation usa DELETE con user_id", async () => {
    const fn = mockFetch(true, { ok: true });
    await deleteConversation("c1", "u1");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/conversations/c1?user_id=u1");
    expect(init.method).toBe("DELETE");
  });
});
