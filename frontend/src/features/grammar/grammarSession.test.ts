import { describe, expect, it } from "vitest";
import {
  drillAnswered,
  isSessionFinished,
  sessionDone,
  type GrammarSession,
} from "./grammarSession";

describe("grammarSession", () => {
  it("drillAnswered elimina el id solo si el check se acertó", () => {
    const remaining = ["a", "b", "c"];
    expect(drillAnswered(remaining, "b", true)).toEqual(["a", "c"]);
    expect(drillAnswered(remaining, "b", false)).toEqual(["a", "b", "c"]);
    expect(drillAnswered(remaining, "z", true)).toEqual(["a", "b", "c"]);
  });

  it("drillAnswered no muta el array original", () => {
    const remaining = ["a", "b", "c"];
    const out = drillAnswered(remaining, "a", true);
    expect(remaining).toEqual(["a", "b", "c"]);
    expect(out).not.toBe(remaining);
  });

  it("sessionDone devuelve done en modo level y aciertos en drill", () => {
    expect(
      sessionDone({ mode: "level", level: "A1", total: 10, done: 3 }),
    ).toBe(3);
    expect(
      sessionDone({ mode: "drill", level: "A1", total: 3, remaining: ["x"] }),
    ).toBe(2);
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
      isSessionFinished({
        mode: "drill",
        level: "A1",
        total: 2,
        remaining: ["a"],
      }),
    ).toBe(false);
    const mastered: GrammarSession = {
      mode: "mastered",
      level: "B1",
      total: 12,
      done: 0,
    };
    expect(sessionDone(mastered)).toBe(0);
    expect(isSessionFinished(mastered)).toBe(false);
    const finished: GrammarSession = {
      ...mastered,
      done: 12,
    };
    expect(sessionDone(finished)).toBe(12);
    expect(isSessionFinished(finished)).toBe(true);
    const partial: GrammarSession = {
      ...mastered,
      done: 7,
    };
    expect(isSessionFinished(partial)).toBe(false);
  });
});
