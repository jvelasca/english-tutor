import { describe, expect, it } from "vitest";
import {
  KIND_LABELS,
  SKILL_LABELS,
  kindKey,
  stepTitle,
} from "./learningLabels";
import { translate } from "./i18n";
import type { SessionStep } from "../types/api";

// Traductor de test: devuelve los textos EN para las claves de frases.
const t = (k: string) => translate("en", k);

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

  it("kindKey apunta a la clave i18n de cada tipo", () => {
    expect(kindKey("review")).toBe("today.kind.review");
    expect(kindKey("easy_wins")).toBe("today.kind.easy_wins");
    expect(kindKey("weakness")).toBe("today.kind.weakness");
    expect(kindKey("desconocido")).toBeNull();
  });

  it("stepTitle prioriza el subskill en pasos de listening", () => {
    expect(
      stepTitle(step({ kind: "listening", subskill: "connected_speech" }), t),
    ).toBe("Connected speech");
  });

  it("stepTitle describe repaso y refuerzo", () => {
    expect(stepTitle(step({ kind: "review", skill: "grammar" }), t)).toBe(
      "Review Grammar",
    );
    expect(stepTitle(step({ kind: "easy_wins", skill: "speaking" }), t)).toBe(
      "Boost: Speaking",
    );
  });

  it("stepTitle devuelve el título tal cual para el resto", () => {
    expect(stepTitle(step({ kind: "new", title: "Present perfect" }), t)).toBe(
      "Present perfect",
    );
  });
});
