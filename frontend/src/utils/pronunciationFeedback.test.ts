import { describe, expect, it } from "vitest";
import {
  feedbackHints,
  joinWords,
  wordsCorrectLabel,
} from "./pronunciationFeedback";
import type { PronunciationBreakdown } from "../types/api";

function breakdown(partial: Partial<PronunciationBreakdown>): PronunciationBreakdown {
  return {
    correct: [],
    missing: [],
    extra: [],
    substituted: [],
    total: 0,
    ...partial,
  };
}

describe("joinWords", () => {
  it("devuelve vacío para una lista vacía", () => {
    expect(joinWords([])).toBe("");
  });

  it("devuelve la única palabra", () => {
    expect(joinWords(["world"])).toBe("world");
  });

  it("une dos palabras con «and»", () => {
    expect(joinWords(["a", "b"])).toBe("a and b");
  });

  it("une tres palabras con comas y «and»", () => {
    expect(joinWords(["a", "b", "c"])).toBe("a, b and c");
  });
});

describe("feedbackHints", () => {
  it("detecta palabras omitidas", () => {
    expect(feedbackHints(breakdown({ missing: ["world"] }))).toEqual([
      "You missed: world",
    ]);
  });

  it("detecta sustituciones", () => {
    expect(
      feedbackHints(breakdown({ substituted: [{ expected: "have", heard: "am" }] })),
    ).toEqual(["You substituted: have → am"]);
  });

  it("detecta palabras de más", () => {
    expect(feedbackHints(breakdown({ extra: ["world"] }))).toEqual([
      "You added extra: world",
    ]);
  });

  it("sin errores devuelve vacío", () => {
    expect(feedbackHints(breakdown({}))).toEqual([]);
  });
});

describe("wordsCorrectLabel", () => {
  it("resume aciertos", () => {
    expect(
      wordsCorrectLabel(breakdown({ correct: ["a", "b", "c", "d"], total: 5 })),
    ).toBe("4 of 5 words correct");
  });
});
