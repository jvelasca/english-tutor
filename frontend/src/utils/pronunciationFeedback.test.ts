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

  it("une dos palabras con «y»", () => {
    expect(joinWords(["a", "b"])).toBe("a y b");
  });

  it("une tres palabras con comas y «y»", () => {
    expect(joinWords(["a", "b", "c"])).toBe("a, b y c");
  });
});

describe("feedbackHints", () => {
  it("detecta palabras omitidas", () => {
    expect(feedbackHints(breakdown({ missing: ["world"] }))).toEqual([
      "Te faltó: world",
    ]);
  });

  it("detecta sustituciones", () => {
    expect(
      feedbackHints(breakdown({ substituted: [{ expected: "have", heard: "am" }] })),
    ).toEqual(["Sustituiste: have → am"]);
  });

  it("detecta palabras de más", () => {
    expect(feedbackHints(breakdown({ extra: ["world"] }))).toEqual([
      "Añadiste de más: world",
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
    ).toBe("4 de 5 palabras correctas");
  });
});
