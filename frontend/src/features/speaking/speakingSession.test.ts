import { describe, expect, it } from "vitest";
import {
  drillAnswered,
  drillDone,
  isSessionFinished,
  sessionDone,
} from "./speakingSession";

describe("speakingSession", () => {
  it("drillAnswered elimina el id solo si la frase se superó", () => {
    const remaining = ["a", "b", "c"];
    // Frase superada: sale del pool pendiente.
    expect(drillAnswered(remaining, "b", true)).toEqual(["a", "c"]);
    // No superada: sigue pendiente (se repite hasta dominarla).
    expect(drillAnswered(remaining, "b", false)).toEqual(["a", "b", "c"]);
    // Id que ya no está en el pool: no cambia nada.
    expect(drillAnswered(remaining, "z", true)).toEqual(["a", "b", "c"]);
  });

  it("drillAnswered no muta el array original", () => {
    const remaining = ["a", "b"];
    const out = drillAnswered(remaining, "a", true);
    expect(out).not.toBe(remaining);
    expect(remaining).toEqual(["a", "b"]);
  });

  it("drillDone cuenta las frases dominadas del drill", () => {
    expect(drillDone({ mode: "drill", level: "A1", total: 5, remaining: ["a"] })).toBe(4);
    expect(drillDone({ mode: "drill", level: "A1", total: 5, remaining: [] })).toBe(5);
  });

  it("sessionDone devuelve done en modo level y dominadas en drill", () => {
    expect(
      sessionDone({ mode: "level", level: "A1", total: 10, done: 3 }),
    ).toBe(3);
    expect(
      sessionDone({ mode: "drill", level: "A1", total: 3, remaining: ["x"] }),
    ).toBe(2);
  });

  it("mastered (repasar lo aprendido) se comporta como rotación de nivel", () => {
    const mastered = { mode: "mastered" as const, level: "A1", total: 12, done: 0 };
    expect(sessionDone(mastered)).toBe(0);
    expect(isSessionFinished(mastered)).toBe(false);
    const finished = { ...mastered, done: 12 };
    expect(sessionDone(finished)).toBe(12);
    expect(isSessionFinished(finished)).toBe(true);
    const partial = { ...mastered, done: 7 };
    expect(isSessionFinished(partial)).toBe(false);
  });

  it("isSessionFinished respeta el objetivo de cada modo", () => {
    expect(
      isSessionFinished({ mode: "level", level: "A1", total: 4, done: 4 }),
    ).toBe(true);
    expect(
      isSessionFinished({ mode: "level", level: "A1", total: 4, done: 2 }),
    ).toBe(false);
    expect(
      isSessionFinished({ mode: "drill", level: "A1", total: 2, remaining: [] }),
    ).toBe(true);
    expect(
      isSessionFinished({ mode: "drill", level: "A1", total: 2, remaining: ["a"] }),
    ).toBe(false);
  });
});
