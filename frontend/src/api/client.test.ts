import { afterEach, describe, expect, it, vi } from "vitest";
import { withTimeout } from "./client";

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
