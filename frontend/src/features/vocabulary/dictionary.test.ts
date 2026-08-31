import { describe, expect, it } from "vitest";
import {
  cefrBarValue,
  recognizedNotProduced,
  sortLexicalItems,
} from "./dictionary";
import type { LexicalItem } from "../../types/api";

function item(partial: Partial<LexicalItem>): LexicalItem {
  return {
    word: "word",
    lemma: "word",
    cefr: "A1",
    kind: "word",
    source: "curriculum",
    status: "learning",
    recall: 0.5,
    next_review_days: 3,
    exposures: 0,
    appearances: 0,
    ...partial,
  };
}

describe("dictionary helpers", () => {
  it("ordena por estado (weak → learning → known → mastered) y luego por recall", () => {
    const items = [
      item({ word: "a", status: "mastered", recall: 0.9 }),
      item({ word: "b", status: "weak", recall: 0.6 }),
      item({ word: "c", status: "weak", recall: 0.2 }),
      item({ word: "d", status: "known", recall: 0.4 }),
      item({ word: "e", status: "learning", recall: 0.8 }),
    ];
    const sorted = sortLexicalItems(items).map((i) => i.word);
    // weak primero (menor recall antes), luego learning, known, mastered.
    expect(sorted).toEqual(["c", "b", "e", "d", "a"]);
  });

  it("recognizedNotProduced devuelve solo input sin producción", () => {
    const items = [
      item({ word: "travel", exposures: 3, appearances: 0 }),
      item({ word: "cat", exposures: 0, appearances: 2 }),
      item({ word: "culture", exposures: 0, appearances: 0 }),
    ];
    expect(recognizedNotProduced(items)).toEqual(["travel"]);
  });

  it("recognizedNotProduced está vacío sin datos", () => {
    expect(recognizedNotProduced([])).toEqual([]);
  });

  it("cefrBarValue normaliza respecto al máximo", () => {
    expect(cefrBarValue(0, 0)).toBe(0);
    expect(cefrBarValue(2, 4)).toBe(0.5);
    expect(cefrBarValue(4, 4)).toBe(1);
  });
});
