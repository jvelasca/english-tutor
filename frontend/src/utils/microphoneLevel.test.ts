import { describe, expect, it } from "vitest";
import { levelBar, levelPercent } from "./microphoneLevel";

describe("levelPercent", () => {
  it("devuelve 0 para silencio (señal centrada en 128)", () => {
    const silence = new Uint8Array(256).fill(128);
    expect(levelPercent(silence)).toBe(0);
  });

  it("devuelve 0 para señal por debajo del suelo de ruido", () => {
    const quiet = new Uint8Array(256).fill(129);
    expect(levelPercent(quiet, 0.02)).toBe(0);
  });

  it("devuelve 100 para una señal a plena escala", () => {
    const loud = new Uint8Array(256).fill(255);
    expect(levelPercent(loud)).toBe(100);
  });

  it("crece de forma monótona con la energía", () => {
    const low = new Float32Array([0.1, -0.1, 0.1, -0.1]);
    const high = new Float32Array([0.8, -0.8, 0.8, -0.8]);
    expect(levelPercent(high)).toBeGreaterThan(levelPercent(low));
  });
});

describe("levelBar", () => {
  it("genera una barra con la longitud solicitada", () => {
    const bar = levelBar(50, 10);
    expect(bar).toHaveLength(10);
    expect(bar).toBe("█████░░░░░");
  });

  it("genera barra vacía para 0%", () => {
    expect(levelBar(0, 4)).toBe("░░░░");
  });

  it("genera barra llena para 100%", () => {
    expect(levelBar(100, 4)).toBe("████");
  });
});
