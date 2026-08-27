import { describe, expect, it } from "vitest";
import {
  KIND_LABELS,
  SKILL_LABELS,
  stepTitle,
} from "./learningLabels";
import type { SessionStep } from "../types/api";

function step(partial: Partial<SessionStep>): SessionStep {
  return {
    kind: "new",
    step_key: "k",
    skill: null,
    subskill: null,
    objective_id: null,
    level_id: null,
    skills: [],
    title: "Task",
    reason: "reason",
    minutes: 5,
    ...partial,
  };
}

describe("learningLabels", () => {
  it("expone las etiquetas canónicas de destrezas en inglés", () => {
    expect(SKILL_LABELS.listening).toBe("Listening");
    expect(SKILL_LABELS.speaking).toBe("Speaking");
    expect(KIND_LABELS.review).toBe("Review");
  });

  it("stepTitle prioriza el subskill en pasos de listening", () => {
    expect(
      stepTitle(step({ kind: "listening", subskill: "connected_speech" })),
    ).toBe("Connected speech");
  });

  it("stepTitle describe repaso y refuerzo", () => {
    expect(stepTitle(step({ kind: "review", skill: "grammar" }))).toBe(
      "Review Grammar",
    );
    expect(stepTitle(step({ kind: "easy_wins", skill: "speaking" }))).toBe(
      "Boost: Speaking",
    );
  });

  it("stepTitle devuelve el título tal cual para el resto", () => {
    expect(stepTitle(step({ kind: "new", title: "Present perfect" }))).toBe(
      "Present perfect",
    );
  });
});
