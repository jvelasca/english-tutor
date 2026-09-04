import { describe, expect, it } from "vitest";
import {
  drillAnswered,
  drillDone,
  isSessionFinished,
  sessionDone,
  type ConversationSession,
} from "./conversationSession";

describe("conversationSession", () => {
  it("drillAnswered elimina el id solo si el diálogo se superó", () => {
    const remaining = ["cv-A1-0001", "cv-A1-0002", "cv-A1-0003"];
    expect(drillAnswered(remaining, "cv-A1-0002", true)).toEqual([
      "cv-A1-0001",
      "cv-A1-0003",
    ]);
    expect(drillAnswered(remaining, "cv-A1-0002", false)).toEqual(remaining);
    expect(drillAnswered(remaining, "cv-X1-9999", true)).toEqual(remaining);
  });

  it("drillAnswered no muta el array original", () => {
    const remaining = ["a", "b", "c"];
    const out = drillAnswered(remaining, "a", true);
    expect(remaining).toEqual(["a", "b", "c"]);
    expect(out).not.toBe(remaining);
  });

  it("sessionDone/drillDone devuelven done en level y dominados en drill", () => {
    const level: ConversationSession = {
      mode: "level",
      level: "A1",
      total: 10,
      done: 3,
    };
    expect(drillDone(level)).toBe(3);
    expect(sessionDone(level)).toBe(3);
    const drill: ConversationSession = {
      mode: "drill",
      level: "A1",
      total: 3,
      remaining: ["x"],
    };
    expect(drillDone(drill)).toBe(2);
    expect(sessionDone(drill)).toBe(2);
  });

  it("isSessionFinished respeta el objetivo de cada modo", () => {
    expect(
      isSessionFinished({ mode: "level", level: "A1", total: 4, done: 4 }),
    ).toBe(true);
    expect(
      isSessionFinished({ mode: "level", level: "A1", total: 4, done: 2 }),
    ).toBe(false);
    expect(
      isSessionFinished({
        mode: "drill",
        level: "A1",
        total: 2,
        remaining: [],
      }),
    ).toBe(true);
    expect(
      isSessionFinished({
        mode: "drill",
        level: "A1",
        total: 2,
        remaining: ["a"],
      }),
    ).toBe(false);
    const mastered: ConversationSession = {
      mode: "mastered",
      level: "B1",
      total: 12,
      done: 0,
    };
    expect(sessionDone(mastered)).toBe(0);
    expect(isSessionFinished(mastered)).toBe(false);
    const finished: ConversationSession = { ...mastered, done: 12 };
    expect(sessionDone(finished)).toBe(12);
    expect(isSessionFinished(finished)).toBe(true);
    const partial: ConversationSession = { ...mastered, done: 7 };
    expect(isSessionFinished(partial)).toBe(false);
  });
});
