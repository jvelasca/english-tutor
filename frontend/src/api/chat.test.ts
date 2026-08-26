import { afterEach, describe, expect, it, vi } from "vitest";
import { sendChat, streamChat } from "./chat";
import type { Message } from "../types/api";

const MSG: Message = { role: "user", content: "hi" };

function mockJsonFetch(data: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok: true, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

function mockStreamFetch() {
  const encoder = new TextEncoder();
  const data = encoder.encode('data: {"content":"Hi"}\n\ndata: {"done": true}\n\n');
  let sent = false;
  const reader = {
    read: vi.fn(() => {
      if (sent) return Promise.resolve({ value: undefined, done: true });
      sent = true;
      return Promise.resolve({ value: data, done: false });
    }),
    cancel: vi.fn().mockResolvedValue(undefined),
  };
  const fn = vi.fn().mockResolvedValue({
    ok: true,
    body: { getReader: () => reader },
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("chat api", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("sendChat incluye user_id en la query", async () => {
    const fn = mockJsonFetch({ model: "m", content: "x" });
    await sendChat([MSG], "m", "conversation", "u1");
    const url = fn.mock.calls[0][0] as string;
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(url).toBe("/api/chat?user_id=u1");
    expect(body.user_id).toBeUndefined();
  });

  it("sendChat no incluye user_id cuando no hay usuario", async () => {
    const fn = mockJsonFetch({ model: "m", content: "x" });
    await sendChat([MSG], "m", "conversation");
    const url = fn.mock.calls[0][0] as string;
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(url).toBe("/api/chat");
    expect(body.user_id).toBeUndefined();
  });

  it("streamChat incluye user_id en la query", async () => {
    const fn = mockStreamFetch();
    const onDelta = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();
    await streamChat(
      [MSG],
      "m",
      "conversation",
      { onDelta, onDone, onError },
      "u1",
    );
    const url = fn.mock.calls[0][0] as string;
    expect(url).toBe("/api/chat/stream?user_id=u1");
    expect(onDelta).toHaveBeenCalledWith("Hi");
    expect(onDone).toHaveBeenCalled();
  });

  it("streamChat incluye objective_id cuando hay lección activa", async () => {
    const fn = mockStreamFetch();
    await streamChat(
      [MSG],
      "m",
      "conversation",
      { onDelta: () => {}, onDone: () => {}, onError: () => {} },
      "u1",
      "a1-m01-u01-l01-o01",
    );
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(body.objective_id).toBe("a1-m01-u01-l01-o01");
  });

  it("streamChat omite objective_id cuando no hay lección", async () => {
    const fn = mockStreamFetch();
    await streamChat(
      [MSG],
      "m",
      "conversation",
      { onDelta: () => {}, onDone: () => {}, onError: () => {} },
      "u1",
    );
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(body.objective_id).toBeUndefined();
  });

  it("streamChat incluye conversation_id y message_id cuando se pasan", async () => {
    const fn = mockStreamFetch();
    await streamChat(
      [MSG],
      "m",
      "conversation",
      { onDelta: () => {}, onDone: () => {}, onError: () => {} },
      "u1",
      undefined,
      "conv-1",
      "msg-1",
    );
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(body.conversation_id).toBe("conv-1");
    expect(body.message_id).toBe("msg-1");
  });

  it("streamChat omite conversation_id y message_id cuando no se pasan", async () => {
    const fn = mockStreamFetch();
    await streamChat(
      [MSG],
      "m",
      "conversation",
      { onDelta: () => {}, onDone: () => {}, onError: () => {} },
      "u1",
    );
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(body.conversation_id).toBeUndefined();
    expect(body.message_id).toBeUndefined();
  });
});
