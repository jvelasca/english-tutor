import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getConversationLevelItems,
  getConversationQuestion,
  getConversationStats,
  submitConversationAttempt,
} from "./conversationRoutes";

function mockFetch(ok: boolean, data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("conversationRoutes api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("getConversationQuestion llama con user_id en la query", async () => {
    const fn = mockFetch(true, { id: "cv-A1-0001", level: "A1", topic: "x" });
    await getConversationQuestion("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/conversation/routes/question?user_id=u1");
  });

  it("getConversationQuestion añade level y mode=failed solo cuando se piden", async () => {
    const fn = mockFetch(true, { id: "cv-A1-0001", level: "A1", topic: "x" });
    await getConversationQuestion("u1", "A1", "failed");
    const [url] = fn.mock.calls[0];
    expect(url).toBe(
      "/api/conversation/routes/question?user_id=u1&level=A1&mode=failed",
    );
  });

  it("getConversationQuestion con mode all omite el parámetro", async () => {
    const fn = mockFetch(true, { id: "cv-A1-0001", level: "A1", topic: "x" });
    await getConversationQuestion("u1", "A1", "all");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/conversation/routes/question?user_id=u1&level=A1");
  });

  it("getConversationStats llama con user_id en la query", async () => {
    const fn = mockFetch(true, { attempts: 1, passed: 1, accuracy: 100 });
    await getConversationStats("u1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/conversation/routes/stats?user_id=u1");
  });

  it("getConversationLevelItems llama a /items con user_id y level", async () => {
    const fn = mockFetch(true, {
      level: "A1",
      total: 2,
      mastered: 0,
      failed: 1,
      unseen: 1,
      completed: false,
      items: [],
    });
    await getConversationLevelItems("u1", "A1");
    const [url] = fn.mock.calls[0];
    expect(url).toBe("/api/conversation/routes/items?user_id=u1&level=A1");
  });

  it("submitConversationAttempt envía dialogue_id y conversation_id en JSON", async () => {
    const fn = mockFetch(true, {
      dialogue_id: "cv-A1-0001",
      level: "A1",
      opening_line: "Hi!",
      heard: "Hello",
      overall: 0.9,
      passed: true,
      criteria: { content: 0.9, fluency: 0.8, interaction: 0.7 },
      observed: {},
      topic: "Intro",
      communicative_goals: [],
    });
    await submitConversationAttempt("u1", "cv-A1-0001", "conv-123");
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/conversation/routes/attempt?user_id=u1");
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({
      "Content-Type": "application/json",
    });
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({
      dialogue_id: "cv-A1-0001",
      conversation_id: "conv-123",
    });
  });
});
