import { afterEach, describe, expect, it, vi } from "vitest";
import { getJson, withTimeout } from "./client";

function fakeResponse(payload: unknown, status: number): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as unknown as Response;
}

describe("withTimeout", () => {
  afterEach(() => vi.useRealTimers());

  it("resuelve con el valor cuando la promesa termina a tiempo", async () => {
    await expect(withTimeout(Promise.resolve("ok"), 1000, "x")).resolves.toBe(
      "ok",
    );
  });

  it("rechaza con error legible cuando la promesa nunca responde", async () => {
    vi.useFakeTimers();
    const pending = withTimeout(
      new Promise<never>(() => {}),
      1000,
      "submit answer",
    );
    const assertion = expect(pending).rejects.toThrow("submit answer");
    vi.advanceTimersByTime(1001);
    await assertion;
  });

  it("descarta el temporizador cuando la promesa se resuelve antes", async () => {
    vi.useFakeTimers();
    const spy = vi.spyOn(globalThis, "clearTimeout");
    await withTimeout(Promise.resolve("fast"), 5000, "x");
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });
});

describe("request: 429 RATE_LIMITED localizado (V3.6.2)", () => {
  afterEach(() => vi.unstubAllGlobals());

  function stubLang(lang: string | null) {
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (key: string) => (key === "english-tutor.lang" ? lang : null),
      },
    });
  }

  it("traduce el mensaje a la lengua de la UI (es)", async () => {
    stubLang("es");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        fakeResponse({ code: "RATE_LIMITED", detail: "texto interno" }, 429),
      ),
    );
    await expect(getJson<unknown>("/x")).rejects.toThrow(/saturado/);
  });

  it("usa el idioma por defecto (en) si no hay preferencia guardada", async () => {
    stubLang(null);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => fakeResponse({ code: "RATE_LIMITED" }, 429)),
    );
    await expect(getJson<unknown>("/x")).rejects.toThrow(/busy/);
  });

  it("sin code RATE_LIMITED conserva el detail del backend", async () => {
    stubLang("es");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => fakeResponse({ detail: "otro error" }, 500)),
    );
    await expect(getJson<unknown>("/x")).rejects.toThrow("otro error");
  });
});
