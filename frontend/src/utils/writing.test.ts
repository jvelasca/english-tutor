import { describe, expect, it } from "vitest";
import type { WritingCriterionProgress } from "../types/api";
import { writingCriterionLabel, writingNextFocus } from "./writing";

function criterion(
  criterion: string,
  overrides: Partial<WritingCriterionProgress> = {},
): WritingCriterionProgress {
  return {
    criterion,
    attempts: 1,
    mean: null,
    min: null,
    max: null,
    review_due: false,
    ...overrides,
  };
}

describe("writingCriterionLabel", () => {
  it("mapea cada criterio a su etiqueta en inglés", () => {
    expect(writingCriterionLabel("task_completion")).toBe("Task completion");
    expect(writingCriterionLabel("grammatical_accuracy")).toBe(
      "Grammatical accuracy",
    );
    expect(writingCriterionLabel("lexical_resource")).toBe("Lexical resource");
    expect(writingCriterionLabel("organization")).toBe("Organization");
    expect(writingCriterionLabel("coherence")).toBe("Coherence");
    expect(writingCriterionLabel("register")).toBe("Register");
  });

  it("devuelve el valor crudo para criterios desconocidos", () => {
    expect(writingCriterionLabel("spelling")).toBe("spelling");
  });
});

describe("writingNextFocus", () => {
  it("prioriza los criterios con review_due, ordenados por menor puntuación", () => {
    const criteria = [
      criterion("register", { recent_score: 0.9 }),
      criterion("organization", { review_due: true, recent_score: 0.8 }),
      criterion("coherence", { review_due: true, recent_score: 0.6 }),
    ];
    expect(writingNextFocus(criteria)).toEqual(["coherence", "organization"]);
  });

  it("sin review_due elige la menor puntuación", () => {
    const criteria = [
      criterion("register", { recent_score: 0.8 }),
      criterion("organization", { recent_score: 0.4 }),
      criterion("coherence", { mean: 0.5 }),
    ];
    expect(writingNextFocus(criteria)).toEqual(["organization", "coherence"]);
  });

  it("usa recent_score antes que mean", () => {
    const criteria = [
      criterion("register", { recent_score: 0.7, mean: 0.3 }),
      criterion("organization", { mean: 0.4 }),
    ];
    expect(writingNextFocus(criteria)).toEqual(["organization", "register"]);
  });

  it("ignora criterios sin evidencia", () => {
    const criteria = [
      criterion("register", { recent_score: 0.7 }),
      criterion("organization"),
    ];
    expect(writingNextFocus(criteria)).toEqual(["register"]);
  });

  it("devuelve vacío si no hay criterios con evidencia", () => {
    expect(writingNextFocus([criterion("register"), criterion("organization")])).toEqual(
      [],
    );
  });
});
