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

  it("sendChat incluye user_id en el body", async () => {
    const fn = mockJsonFetch({ model: "m", content: "x" });
    await sendChat([MSG], "m", "conversation", "u1");
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(body.user_id).toBe("u1");
  });

  it("sendChat manda user_id null cuando no hay usuario", async () => {
    const fn = mockJsonFetch({ model: "m", content: "x" });
    await sendChat([MSG], "m", "conversation");
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(body.user_id).toBeNull();
  });

  it("streamChat incluye user_id en el body", async () => {
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
    const body = JSON.parse(fn.mock.calls[0][1].body as string);
    expect(body.user_id).toBe("u1");
    expect(onDelta).toHaveBeenCalledWith("Hi");
    expect(onDone).toHaveBeenCalled();
  });
});
